from __future__ import annotations

import logging
import re
import time
from typing import Any

from . import TRAVEL_SIGNAL_KEYS, normalize_image_analysis
from .config_loader import (
    ImageEmbeddingConfig,
    load_config,
    validate_runtime_configuration,
)
from .claude_vision import analyze_image as analyze_image_with_claude
from services.activity_log import log_event
from services.firebase import (
    create_message_with_id,
    finalize_image_message_failure,
    finalize_image_message_success,
    get_message,
    get_trip,
    reserve_message_id,
)

logger = logging.getLogger(__name__)

_FILENAME_SANITIZER = re.compile(r"[^a-zA-Z0-9._-]+")


class ImageProcessingDisabledError(RuntimeError):
    pass


class ImageUploadValidationError(RuntimeError):
    pass


class ImageMessagePersistenceError(RuntimeError):
    pass


def validate_startup() -> ImageEmbeddingConfig:
    return validate_runtime_configuration()


def _sanitize_image_name(filename: str) -> str:
    safe_name = filename.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].strip() or "upload.png"
    sanitized = _FILENAME_SANITIZER.sub("-", safe_name).strip(".-_")
    return sanitized or "upload.png"


def _empty_failure_result(processor: str, error: str) -> dict[str, Any]:
    return normalize_image_analysis(
        {
            "contentCategory": "unknown",
            "summary": None,
            "extractedText": None,
            "confidence": None,
            "qualityScore": None,
            "travelSignals": {key: [] for key in TRAVEL_SIGNAL_KEYS},
            "error": error,
        },
        processor=processor,  # type: ignore[arg-type]
    )


def _build_ai_summary_text(result: dict[str, Any], config: ImageEmbeddingConfig) -> str:
    parts = [result.get("summary") or config.reply.fallback_summary]

    if result.get("contentCategory") == "travel_related":
        for key in TRAVEL_SIGNAL_KEYS:
            label = config.reply.section_labels.get(key)
            if not label:
                continue
            values = [item["value"] for item in result["travelSignals"].get(key, [])[:3]]
            if values:
                parts.append(f"**{label}:** {', '.join(values)}")

    extracted_text = result.get("extractedText")
    if extracted_text and len(parts) == 1:
        preview = extracted_text[: config.reply.extracted_text_preview_chars].strip()
        if len(extracted_text) > len(preview):
            preview += "..."
        parts.append(f"**{config.reply.extracted_text_label}:** {preview}")

    return "\n\n".join(part for part in parts if part)



def get_feature_flags() -> dict[str, bool]:
    config = load_config()
    return {
        "screenshotProcessingEnabled": config.screenshot_processing_enabled,
    }


def create_pending_image_message(
    *,
    trip_id: str,
    sender_id: str,
    sender_name: str,
    caption_text: str,
    image_bytes: bytes,
    image_name: str,
    image_mime_type: str,
) -> dict[str, Any]:
    config = load_config()
    if not config.screenshot_processing_enabled:
        raise ImageProcessingDisabledError("Screenshot processing is disabled")

    if not get_trip(trip_id):
        raise LookupError("Trip not found")

    if image_mime_type not in config.upload.allowed_mime_types:
        raise ImageUploadValidationError("Unsupported image MIME type")

    if not image_bytes:
        raise ImageUploadValidationError("Uploaded image is empty")

    if len(image_bytes) > config.upload.max_file_size_bytes:
        raise ImageUploadValidationError("Uploaded image exceeds the configured size limit")

    message_id = reserve_message_id(trip_id)
    safe_image_name = _sanitize_image_name(image_name)

    payload = {
        "senderId": sender_id,
        "senderName": sender_name,
        "text": caption_text.strip(),
        "type": "user",
        "imageMimeType": image_mime_type,
        "imageName": safe_image_name,
        "analysisStatus": "pending",
        "imageAnalysis": None,
        "analysisReplyMessageId": None,
    }

    try:
        return create_message_with_id(trip_id, message_id, payload)
    except Exception as exc:
        raise ImageMessagePersistenceError("Failed to persist screenshot message") from exc


def process_image_message(
    *,
    trip_id: str,
    message_id: str,
    image_bytes: bytes,
    image_mime_type: str,
) -> None:
    config = load_config()
    started_at = time.perf_counter()
    processor = "claude_haiku"
    status = "skipped"
    error_type: str | None = None
    _analysis_category: str | None = None

    current_message = get_message(trip_id, message_id)
    if not current_message:
        return

    if current_message.get("analysisStatus") == "completed":
        return

    if current_message.get("analysisReplyMessageId"):
        return

    if current_message.get("analysisStatus") != "pending":
        return

    try:
        result = analyze_image_with_claude(image_bytes, image_mime_type)
        processor = result.get("processor", "claude_haiku")
        _analysis_category = result.get("contentCategory")
        reply_text = _build_ai_summary_text(result, config)
        finalize_image_message_success(
            trip_id=trip_id,
            message_id=message_id,
            image_analysis=result,
            reply_text=reply_text,
        )
        status = "completed"
    except Exception:
        error_type = "claude_vision_failure"
        failure_result = _empty_failure_result("claude_haiku", error_type)
        finalize_image_message_failure(
            trip_id=trip_id,
            message_id=message_id,
            image_analysis=failure_result,
        )
        status = "failed"
    finally:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "image_analysis trip_id=%s message_id=%s processor=%s status=%s duration_ms=%s error_type=%s",
            trip_id,
            message_id,
            processor,
            status,
            duration_ms,
            error_type,
        )
        log_event(
            "image_analyzed",
            trip_id=trip_id,
            message_id=message_id,
            status=status,
            category=_analysis_category,
            duration_ms=duration_ms,
        )
