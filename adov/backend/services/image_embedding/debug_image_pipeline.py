from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = BACKEND_ROOT / ".env"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.image_embedding import CONTENT_CATEGORY_VALUES, normalize_image_analysis
from services.image_embedding.config_loader import load_config
from services.image_embedding.local_embedder import analyze_image as analyze_local_image
from services.image_embedding.quality_checker import evaluate_quality
from services.image_embedding.remote_embedder import analyze_image as analyze_remote_image

EXPECTED_TOP_LEVEL_KEYS = {
    "processor",
    "contentCategory",
    "summary",
    "extractedText",
    "confidence",
    "qualityScore",
    "travelSignals",
    "error",
}

EXPECTED_TRAVEL_SIGNAL_KEYS = {
    "locations",
    "dates",
    "prices",
    "lodging",
    "transport",
    "bookingSignals",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Debug the local-first screenshot pipeline without Firebase or chat integration."
    )
    parser.add_argument("image_path", help="Path to a local image file")
    parser.add_argument(
        "--mime-type",
        dest="mime_type",
        default=None,
        help="Optional explicit MIME type override, for example image/png",
    )
    parser.add_argument(
        "--force-remote",
        action="store_true",
        help="Call the remote embedder even if local quality passes",
    )
    return parser


def _load_backend_env() -> None:
    load_dotenv(BACKEND_ENV_FILE)


def _resolve_mime_type(image_path: Path, override: str | None) -> str:
    if override:
        return override.strip()
    guessed, _ = mimetypes.guess_type(str(image_path))
    return guessed or "application/octet-stream"


def _validate_schema(result: dict[str, Any]) -> dict[str, Any]:
    actual_top_level_keys = set(result.keys())
    actual_signal_keys = set((result.get("travelSignals") or {}).keys())
    top_level_valid = actual_top_level_keys == EXPECTED_TOP_LEVEL_KEYS
    travel_signals_valid = actual_signal_keys == EXPECTED_TRAVEL_SIGNAL_KEYS
    content_category = result.get("contentCategory")
    content_category_valid = content_category in CONTENT_CATEGORY_VALUES
    non_travel_empty_signals = True
    if content_category in {"non_travel_text", "non_travel_image", "unknown"}:
        non_travel_empty_signals = all(
            not result.get("travelSignals", {}).get(key, [])
            for key in EXPECTED_TRAVEL_SIGNAL_KEYS
        )

    return {
        "valid": top_level_valid and travel_signals_valid and content_category_valid and non_travel_empty_signals,
        "topLevelKeysValid": top_level_valid,
        "travelSignalsValid": travel_signals_valid,
        "contentCategoryValid": content_category_valid,
        "nonTravelSignalsEmpty": non_travel_empty_signals,
        "expectedTopLevelKeys": sorted(EXPECTED_TOP_LEVEL_KEYS),
        "actualTopLevelKeys": sorted(actual_top_level_keys),
        "expectedTravelSignalKeys": sorted(EXPECTED_TRAVEL_SIGNAL_KEYS),
        "actualTravelSignalKeys": sorted(actual_signal_keys),
        "contentCategory": content_category,
        "allowedContentCategories": sorted(CONTENT_CATEGORY_VALUES),
    }


def main() -> int:
    _load_backend_env()

    parser = _build_parser()
    args = parser.parse_args()

    image_path = Path(args.image_path).expanduser()
    if not image_path.exists() or not image_path.is_file():
        print(f"Error: image file not found: {image_path}", file=sys.stderr)
        return 1

    try:
        config = load_config()
        image_bytes = image_path.read_bytes()
        mime_type = _resolve_mime_type(image_path, args.mime_type)

        local_result, image_meta = analyze_local_image(image_bytes, mime_type, config)
        quality_result = evaluate_quality(local_result, image_meta, config)
        local_result["qualityScore"] = quality_result["quality_score"]

        remote_enabled = bool(config.screenshot_remote_fallback_enabled)
        local_passed = bool(quality_result["passed"])
        local_evidence_sufficient = local_result["contentCategory"] != "unknown"
        remote_called = False

        if args.force_remote:
            remote_called = True
            final_result = analyze_remote_image(image_bytes, mime_type, config)
        elif local_passed and local_evidence_sufficient:
            final_result = normalize_image_analysis(local_result, processor="local_ocr")
        elif remote_enabled:
            remote_called = True
            final_result = analyze_remote_image(image_bytes, mime_type, config)
        else:
            fallback_error = None if local_passed else "quality_check_failed"
            final_result = normalize_image_analysis({**local_result, "error": fallback_error}, processor="local_ocr")

        decision_summary = {
            "local_passed": local_passed,
            "local_evidence_sufficient": local_evidence_sufficient,
            "remote_enabled": remote_enabled,
            "remote_called": remote_called,
            "local_content_category": local_result["contentCategory"],
            "final_content_category": final_result["contentCategory"],
            "non_travel_signals_empty": (
                final_result["contentCategory"] == "travel_related"
                or all(not final_result["travelSignals"].get(key, []) for key in EXPECTED_TRAVEL_SIGNAL_KEYS)
            ),
            "final_processor": final_result["processor"],
        }
        schema_validation = _validate_schema(final_result)
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("=== LOCAL ANALYSIS ===")
    print(json.dumps(local_result, indent=2, ensure_ascii=False))
    print()
    print("=== QUALITY CHECK ===")
    print(json.dumps(quality_result, indent=2, ensure_ascii=False))
    print()
    print("=== PIPELINE DECISION ===")
    print(json.dumps(decision_summary, indent=2, ensure_ascii=False))
    print()
    print("=== FINAL RESULT ===")
    print(json.dumps(final_result, indent=2, ensure_ascii=False))
    print()
    print("=== SCHEMA VALIDATION ===")
    print(json.dumps(schema_validation, indent=2, ensure_ascii=False))

    return 0 if schema_validation["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
