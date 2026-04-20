from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

from services.image_embedding.config_loader import load_config
from services.image_embedding.local_embedder import analyze_image
from services.image_embedding.quality_checker import evaluate_quality


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local screenshot OCR and quality checks without chat integration."
    )
    parser.add_argument("image_path", help="Path to a local image file")
    parser.add_argument(
        "--mime-type",
        dest="mime_type",
        default=None,
        help="Optional explicit MIME type override (for example image/png)",
    )
    return parser


def _resolve_mime_type(image_path: Path, override: str | None) -> str:
    if override:
        return override.strip()
    guessed, _ = mimetypes.guess_type(str(image_path))
    return guessed or "application/octet-stream"


def main() -> int:
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
        analysis_result, image_meta = analyze_image(image_bytes, mime_type, config)
        quality_result = evaluate_quality(analysis_result, image_meta, config)
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("=== LOCAL ANALYSIS ===")
    print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
    print()
    print("=== QUALITY CHECK ===")
    print(json.dumps(quality_result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
