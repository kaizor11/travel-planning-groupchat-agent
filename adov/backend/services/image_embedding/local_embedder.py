from __future__ import annotations

import importlib
import io
import re
from typing import Any

from . import normalize_image_analysis
from .config_loader import ImageEmbeddingConfig

DATE_PATTERNS = (
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),
    re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
)
PRICE_PATTERN = re.compile(r"(?:[$€£]\s?\d[\d,]*(?:\.\d{2})?|\b\d[\d,]*(?:\.\d{2})?\s?(?:usd|eur|gbp)\b)", re.IGNORECASE)
LOCATION_PATTERN = re.compile(
    r"\b(?:to|from|in|at)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b"
)
NON_TRAVEL_TEXT_HINTS = (
    "meeting",
    "invoice",
    "minutes",
    "assignment",
    "contract",
    "policy",
    "report",
    "statement",
    "receipt",
    "email",
    "document",
    "spreadsheet",
    "notes",
    "agenda",
    "class",
    "lesson",
)


def _load_pillow():
    image_module = importlib.import_module("PIL.Image")
    image_ops = importlib.import_module("PIL.ImageOps")
    return image_module, image_ops


def _load_ocr_engine():
    module = importlib.import_module("rapidocr_onnxruntime")
    return getattr(module, "RapidOCR")


def _dedupe_signal_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen: set[str] = set()
    for item in items:
        value = str(item["value"]).strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        deduped.append({"value": value, "confidence": item.get("confidence")})
    return deduped


def _extract_keyword_signals(
    text: str,
    keywords: tuple[str, ...],
    *,
    confidence: float | None,
) -> list[dict[str, Any]]:
    lower_text = text.lower()
    matches = []
    for keyword in keywords:
        if keyword.lower() in lower_text:
            matches.append({"value": keyword, "confidence": confidence})
    return _dedupe_signal_items(matches)


def _extract_travel_signals(
    text: str,
    *,
    confidence: float | None,
    config: ImageEmbeddingConfig,
) -> dict[str, list[dict[str, Any]]]:
    locations = [
        {"value": match.group(1).strip(), "confidence": confidence}
        for match in LOCATION_PATTERN.finditer(text)
    ]
    dates = []
    for pattern in DATE_PATTERNS:
        dates.extend({"value": match.group(0).strip(), "confidence": confidence} for match in pattern.finditer(text))

    prices = [
        {"value": match.group(0).strip(), "confidence": confidence}
        for match in PRICE_PATTERN.finditer(text)
    ]

    keyword_hints = config.local_ocr.keyword_hints
    return {
        "locations": _dedupe_signal_items(locations),
        "dates": _dedupe_signal_items(dates),
        "prices": _dedupe_signal_items(prices),
        "lodging": _extract_keyword_signals(text, keyword_hints.get("lodging", ()), confidence=confidence),
        "transport": _extract_keyword_signals(text, keyword_hints.get("transport", ()), confidence=confidence),
        "bookingSignals": _extract_keyword_signals(
            text,
            keyword_hints.get("bookingSignals", ()),
            confidence=confidence,
        ),
    }


def _build_summary(
    content_category: str,
    extracted_text: str | None,
    travel_signals: dict[str, list[dict[str, Any]]],
    config: ImageEmbeddingConfig,
) -> str | None:
    if content_category == "non_travel_text":
        if not extracted_text:
            return "This looks like non-travel text content, but the extracted text is limited."
        preview = extracted_text.splitlines()[0].strip()
        if len(preview) > 120:
            preview = preview[:117].rstrip() + "..."
        return f"This looks like non-travel text content. It appears to discuss: {preview}"

    if content_category == "unknown":
        if extracted_text:
            return "I extracted text from the screenshot, but couldn't confidently determine whether it is travel-related."
        return None

    section_bits = []
    for key, label in (
        ("locations", "locations"),
        ("dates", "dates"),
        ("prices", "prices"),
        ("lodging", "lodging"),
        ("transport", "transport"),
    ):
        values = [item["value"] for item in travel_signals.get(key, [])[:2]]
        if values:
            section_bits.append(f"{label}: {', '.join(values)}")

    if section_bits:
        return f"{config.local_ocr.messages.summary_prefix} I found " + "; ".join(section_bits) + "."

    if extracted_text:
        return config.local_ocr.messages.summary_fallback

    return None


def _classify_content_category(
    extracted_text: str | None,
    travel_signals: dict[str, list[dict[str, Any]]],
    average_confidence: float | None,
    config: ImageEmbeddingConfig,
) -> str:
    text = (extracted_text or "").strip()
    if not text:
        return "unknown"

    travel_indicators = (
        len(travel_signals.get("lodging", []))
        + len(travel_signals.get("transport", []))
        + len(travel_signals.get("bookingSignals", []))
    )
    supporting_indicators = (
        len(travel_signals.get("locations", []))
        + len(travel_signals.get("dates", []))
        + len(travel_signals.get("prices", []))
    )
    lower_text = text.lower()
    non_travel_hint_count = sum(1 for hint in NON_TRAVEL_TEXT_HINTS if hint in lower_text)
    min_text_length = max(config.quality.min_text_length, 20)

    if travel_indicators >= 1 and supporting_indicators >= 1:
        return "travel_related"
    if travel_indicators >= 2:
        return "travel_related"
    if travel_indicators >= 1 and len(text) >= min_text_length and (average_confidence or 0.0) >= 0.3:
        return "travel_related"
    if non_travel_hint_count >= 1 and len(text) >= min_text_length:
        return "non_travel_text"
    if len(text) >= min_text_length and travel_indicators == 0:
        return "non_travel_text"
    return "unknown"


def analyze_image(
    image_bytes: bytes,
    mime_type: str,
    config: ImageEmbeddingConfig,
) -> tuple[dict[str, Any], dict[str, Any]]:
    image_module, image_ops = _load_pillow()
    rapid_ocr_cls = _load_ocr_engine()

    with image_module.open(io.BytesIO(image_bytes)) as image:
        image = image_ops.exif_transpose(image)
        width, height = image.size
        working = image.convert("RGB")

        if config.local_ocr.grayscale:
            working = image_ops.grayscale(working)

        max_dim = config.local_ocr.max_dimension_px
        if max(working.size) > max_dim:
            ratio = max_dim / max(working.size)
            working = working.resize(
                (max(1, int(working.size[0] * ratio)), max(1, int(working.size[1] * ratio)))
            )

        buffer = io.BytesIO()
        working.save(buffer, format="PNG")
        prepared_bytes = buffer.getvalue()

    ocr_engine = rapid_ocr_cls()
    ocr_output = ocr_engine(prepared_bytes)
    raw_results = ocr_output[0] if isinstance(ocr_output, tuple) else ocr_output

    lines: list[str] = []
    confidences: list[float] = []
    for item in raw_results or []:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        text = str(item[1]).strip()
        if not text:
            continue
        lines.append(text)
        try:
            confidences.append(float(item[2]))
        except (TypeError, ValueError):
            continue

    extracted_text = "\n".join(lines).strip() or None
    average_confidence = (
        round(sum(confidences) / len(confidences), 4) if confidences else None
    )
    travel_signals = _extract_travel_signals(
        extracted_text or "",
        confidence=average_confidence,
        config=config,
    )
    content_category = _classify_content_category(
        extracted_text,
        travel_signals,
        average_confidence,
        config,
    )

    if content_category != "travel_related":
        travel_signals = {
            "locations": [],
            "dates": [],
            "prices": [],
            "lodging": [],
            "transport": [],
            "bookingSignals": [],
        }

    normalized = normalize_image_analysis(
        {
            "contentCategory": content_category,
            "summary": _build_summary(content_category, extracted_text, travel_signals, config),
            "extractedText": extracted_text,
            "confidence": average_confidence,
            "qualityScore": None,
            "travelSignals": travel_signals,
            "error": None,
        },
        processor="local_ocr",
    )

    return normalized, {"width": width, "height": height, "mime_type": mime_type}
