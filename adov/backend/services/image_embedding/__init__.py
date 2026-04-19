"""Compatibility package name for screenshot analysis.

The ``image_embedding`` directory name is retained to satisfy the current
project naming requirement. In v1 this package is responsible for screenshot
analysis, OCR, quality-gated remote fallback, and AI reply generation. It is
not a vector embedding subsystem.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

ProcessorName = Literal["local_ocr", "openai_vision"]
ContentCategoryName = Literal[
    "travel_related",
    "non_travel_text",
    "non_travel_image",
    "unknown",
]

CONTENT_CATEGORY_VALUES = {
    "travel_related",
    "non_travel_text",
    "non_travel_image",
    "unknown",
}

TRAVEL_SIGNAL_KEYS = (
    "locations",
    "dates",
    "prices",
    "lodging",
    "transport",
    "bookingSignals",
)


def empty_travel_signals() -> dict[str, list[dict[str, float | str | None]]]:
    return {key: [] for key in TRAVEL_SIGNAL_KEYS}


def normalize_signal_item(item: Any) -> dict[str, str | float | None] | None:
    if isinstance(item, str):
        value = item.strip()
        if not value:
            return None
        return {"value": value, "confidence": None}

    if not isinstance(item, dict):
        return None

    value = str(item.get("value", "")).strip()
    if not value:
        return None

    confidence = item.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None

    return {"value": value, "confidence": confidence}


def normalize_travel_signals(raw: Any) -> dict[str, list[dict[str, str | float | None]]]:
    if not isinstance(raw, dict):
        return empty_travel_signals()

    normalized = empty_travel_signals()
    for key in TRAVEL_SIGNAL_KEYS:
        items = raw.get(key, [])
        if not isinstance(items, list):
            items = []
        cleaned = []
        seen: set[tuple[str, float | None]] = set()
        for item in items:
            normalized_item = normalize_signal_item(item)
            if normalized_item is None:
                continue
            dedupe_key = (
                str(normalized_item["value"]).lower(),
                normalized_item["confidence"],
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned.append(normalized_item)
        normalized[key] = cleaned
    return normalized


def normalize_content_category(raw: Any) -> ContentCategoryName:
    if isinstance(raw, str):
        value = raw.strip()
        if value in CONTENT_CATEGORY_VALUES:
            return value  # type: ignore[return-value]
    return "unknown"


def normalize_image_analysis(
    raw: Any,
    *,
    processor: ProcessorName,
    error: str | None = None,
    content_category: ContentCategoryName | None = None,
) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}

    confidence = payload.get("confidence")
    quality_score = payload.get("qualityScore")

    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None

    try:
        quality_score = float(quality_score) if quality_score is not None else None
    except (TypeError, ValueError):
        quality_score = None

    summary = payload.get("summary")
    if summary is not None:
        summary = str(summary).strip() or None

    extracted_text = payload.get("extractedText")
    if extracted_text is not None:
        extracted_text = str(extracted_text).strip() or None

    normalized_error = error if error is not None else payload.get("error")
    if normalized_error is not None:
        normalized_error = str(normalized_error).strip() or None

    normalized_category = normalize_content_category(
        content_category if content_category is not None else payload.get("contentCategory")
    )
    normalized_travel_signals = normalize_travel_signals(payload.get("travelSignals"))
    if normalized_category != "travel_related":
        normalized_travel_signals = empty_travel_signals()

    return {
        "processor": processor,
        "contentCategory": normalized_category,
        "summary": summary,
        "extractedText": extracted_text,
        "confidence": confidence,
        "qualityScore": quality_score,
        "travelSignals": normalized_travel_signals,
        "error": normalized_error,
    }


def clone_image_analysis(result: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(normalize_image_analysis(result, processor=result["processor"]))
