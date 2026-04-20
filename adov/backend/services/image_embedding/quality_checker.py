from __future__ import annotations

from typing import Any

from .config_loader import ImageEmbeddingConfig


def evaluate_quality(
    result: dict[str, Any],
    image_meta: dict[str, Any],
    config: ImageEmbeddingConfig,
) -> dict[str, Any]:
    weights = config.quality.weights
    width = int(image_meta.get("width", 0) or 0)
    height = int(image_meta.get("height", 0) or 0)
    extracted_text = result.get("extractedText") or ""
    confidence = float(result.get("confidence") or 0.0)
    signal_count = sum(len(items) for items in (result.get("travelSignals") or {}).values())
    keyword_bonus = 1.0 if signal_count >= config.quality.min_detected_signal_items else 0.0

    dimensions_score = min(width / config.quality.min_width, 1.0) * min(
        height / config.quality.min_height, 1.0
    )
    text_length_score = min(len(extracted_text.strip()) / config.quality.min_text_length, 1.0)
    confidence_score = min(confidence / max(config.quality.min_average_confidence, 0.01), 1.0)
    travel_signal_score = min(
        signal_count / max(config.quality.min_detected_signal_items, 1), 1.0
    )

    score = (
        dimensions_score * weights.get("dimensions", 0.0)
        + text_length_score * weights.get("text_length", 0.0)
        + confidence_score * weights.get("confidence", 0.0)
        + travel_signal_score * weights.get("travel_signals", 0.0)
        + keyword_bonus * weights.get("keyword_bonus", 0.0)
    )

    passed = score >= config.quality.pass_score and (
        signal_count >= config.quality.min_detected_signal_items
        or (
            len(extracted_text.strip()) >= config.quality.min_text_length
            and confidence >= config.quality.min_average_confidence
        )
    )

    return {
        "passed": passed,
        "quality_score": round(score, 4),
        "factors": {
            "width": width,
            "height": height,
            "text_length": len(extracted_text.strip()),
            "average_confidence": confidence,
            "signal_count": signal_count,
        },
    }
