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
from .local_embedder import analyze_image as analyze_image_locally
from .quality_checker import evaluate_quality
from .remote_embedder import RemoteEmbedderError, analyze_image as analyze_image_remotely
from services.firebase import (
    create_message_with_id,
    delete_storage_object,
    finalize_image_message_failure,
    finalize_image_message_success,
    get_message,
    get_trip,
    reserve_message_id,
    upload_image_to_storage,
)

logger = logging.getLogger(__name__)

_FILENAME_SANITIZER = re.compile(r"[^a-zA-Z0-9._-]+")


class ImageProcessingDisabledError(RuntimeError):
    pass


class ImageUploadValidationError(RuntimeError):
    pass


class ImageStorageError(RuntimeError):
    pass


class ImageMessagePersistenceError(RuntimeError):
    pass


def validate_startup() -> ImageEmbeddingConfig:
    return validate_runtime_configuration()


def _sanitize_image_name(filename: str, config: ImageEmbeddingConfig) -> str:
    safe_name = filename.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].strip() or "upload.png"
    if not config.storage.sanitize_filenames:
        return safe_name
    sanitized = _FILENAME_SANITIZER.sub("-", safe_name).strip(".-_")
    return sanitized or "upload.png"


def _storage_path_for_message(
    trip_id: str,
    message_id: str,
    image_name: str,
    config: ImageEmbeddingConfig,
) -> str:
    return "/".join(
        [
            config.storage.storage_prefix.strip("/"),
            trip_id,
            message_id,
            image_name,
        ]
    )


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


def _local_result_needs_remote(result: dict[str, Any]) -> bool:
    return result.get("contentCategory") == "unknown"


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
    safe_image_name = _sanitize_image_name(image_name, config)
    image_path = _storage_path_for_message(trip_id, message_id, safe_image_name, config)

    try:
        image_url = upload_image_to_storage(
            image_path=image_path,
            payload=image_bytes,
            content_type=image_mime_type,
        )
    except Exception as exc:
        raise ImageStorageError("Failed to upload screenshot to storage") from exc

    payload = {
        "senderId": sender_id,
        "senderName": sender_name,
        "text": caption_text.strip(),
        "type": "user",
        "imageUrl": image_url,
        "imagePath": image_path,
        "imageMimeType": image_mime_type,
        "imageName": safe_image_name,
        "analysisStatus": "pending",
        "imageAnalysis": None,
        "analysisReplyMessageId": None,
    }

    try:
        return create_message_with_id(trip_id, message_id, payload)
    except Exception as exc:
        delete_storage_object(image_path)
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
    fallback_used = False
    processor = "local_ocr"
    status = "skipped"
    error_type: str | None = None

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
        local_result, image_meta = analyze_image_locally(image_bytes, image_mime_type, config)
        quality = evaluate_quality(local_result, image_meta, config)
        local_result["qualityScore"] = quality["quality_score"]
        local_needs_remote = _local_result_needs_remote(local_result)

        if quality["passed"] and not local_needs_remote:
            reply_text = _build_ai_summary_text(local_result, config)
            finalize_image_message_success(
                trip_id=trip_id,
                message_id=message_id,
                image_analysis=local_result,
                reply_text=reply_text,
            )
            processor = "local_ocr"
            status = "completed"
            return

        if not config.screenshot_remote_fallback_enabled:
            if quality["passed"]:
                reply_text = _build_ai_summary_text(local_result, config)
                finalize_image_message_success(
                    trip_id=trip_id,
                    message_id=message_id,
                    image_analysis=local_result,
                    reply_text=reply_text,
                )
                processor = "local_ocr"
                status = "completed"
                return

            local_result["error"] = "quality_check_failed"
            finalize_image_message_failure(
                trip_id=trip_id,
                message_id=message_id,
                image_analysis=local_result,
            )
            processor = "local_ocr"
            status = "failed"
            error_type = "quality_check_failed"
            return

        fallback_used = True
        processor = "openai_vision"
        remote_result = analyze_image_remotely(image_bytes, image_mime_type, config)
        reply_text = _build_ai_summary_text(remote_result, config)
        finalize_image_message_success(
            trip_id=trip_id,
            message_id=message_id,
            image_analysis=remote_result,
            reply_text=reply_text,
        )
        status = "completed"
    except RemoteEmbedderError as exc:
        error_type = exc.error_type
        failure_result = _empty_failure_result("openai_vision", exc.error_type)
        finalize_image_message_failure(
            trip_id=trip_id,
            message_id=message_id,
            image_analysis=failure_result,
        )
        status = "failed"
    except Exception:
        error_type = "local_processing_failure"
        failure_result = _empty_failure_result("local_ocr", error_type)
        finalize_image_message_failure(
            trip_id=trip_id,
            message_id=message_id,
            image_analysis=failure_result,
        )
        status = "failed"
    finally:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "image_analysis trip_id=%s message_id=%s processor=%s status=%s fallback_used=%s duration_ms=%s error_type=%s",
            trip_id,
            message_id,
            processor,
            status,
            fallback_used,
            duration_ms,
            error_type,
        )
