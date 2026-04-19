from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.image_embedding import service
from services.image_embedding.remote_embedder import RemoteEmbedderError


def _config(*, remote_enabled: bool = False):
    return SimpleNamespace(
        screenshot_processing_enabled=True,
        screenshot_remote_fallback_enabled=remote_enabled,
        storage=SimpleNamespace(storage_prefix="chat_screenshots", sanitize_filenames=True),
        upload=SimpleNamespace(
            max_file_size_bytes=5_000_000,
            allowed_mime_types=("image/png", "image/jpeg"),
        ),
        reply=SimpleNamespace(
            fallback_summary="Fallback summary",
            extracted_text_label="Text",
            extracted_text_preview_chars=120,
            section_labels={
                "locations": "Locations",
                "dates": "Dates",
                "prices": "Prices",
                "lodging": "Lodging",
                "transport": "Transport",
                "bookingSignals": "Booking",
            },
        ),
    )


def test_create_pending_image_message_rolls_back_storage_on_persistence_error(monkeypatch):
    deleted_paths: list[str] = []

    monkeypatch.setattr(service, "load_config", lambda: _config())
    monkeypatch.setattr(service, "get_trip", lambda trip_id: {"id": trip_id})
    monkeypatch.setattr(service, "reserve_message_id", lambda trip_id: "msg-1")
    monkeypatch.setattr(service, "upload_image_to_storage", lambda **kwargs: "https://example.com/file.png")
    monkeypatch.setattr(service, "create_message_with_id", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db failed")))
    monkeypatch.setattr(service, "delete_storage_object", lambda image_path: deleted_paths.append(image_path))

    with pytest.raises(service.ImageMessagePersistenceError):
        service.create_pending_image_message(
            trip_id="trip-1",
            sender_id="user-1",
            sender_name="Alice",
            caption_text="caption",
            image_bytes=b"image-bytes",
            image_name="Paris shot!.png",
            image_mime_type="image/png",
        )

    assert deleted_paths == ["chat_screenshots/trip-1/msg-1/Paris-shot-.png"]


def test_process_image_message_uses_local_result_when_quality_passes(monkeypatch):
    finalized: dict = {}

    monkeypatch.setattr(service, "load_config", lambda: _config())
    monkeypatch.setattr(service, "get_message", lambda trip_id, message_id: {"id": message_id, "analysisStatus": "pending"})
    monkeypatch.setattr(
        service,
        "analyze_image_locally",
        lambda *args, **kwargs: (
            {
                "processor": "local_ocr",
                "summary": "Found travel details",
                "extractedText": "Flight to Paris",
                "confidence": 0.91,
                "qualityScore": None,
                "travelSignals": {
                    "locations": [{"value": "Paris", "confidence": 0.91}],
                    "dates": [],
                    "prices": [],
                    "lodging": [],
                    "transport": [{"value": "Flight", "confidence": 0.91}],
                    "bookingSignals": [],
                },
                "error": None,
            },
            {"width": 1080, "height": 1920},
        ),
    )
    monkeypatch.setattr(service, "evaluate_quality", lambda *args, **kwargs: {"passed": True, "quality_score": 0.88})
    monkeypatch.setattr(service, "analyze_image_remotely", lambda *args, **kwargs: pytest.fail("remote fallback should not run"))
    monkeypatch.setattr(service, "finalize_image_message_success", lambda **kwargs: finalized.update(kwargs) or "reply-1")

    service.process_image_message(
        trip_id="trip-1",
        message_id="msg-1",
        image_bytes=b"image-bytes",
        image_mime_type="image/png",
    )

    assert finalized["trip_id"] == "trip-1"
    assert finalized["message_id"] == "msg-1"
    assert finalized["image_analysis"]["processor"] == "local_ocr"
    assert finalized["image_analysis"]["qualityScore"] == 0.88
    assert "Paris" in finalized["reply_text"]


def test_process_image_message_marks_failed_when_remote_response_is_invalid(monkeypatch):
    finalized: dict = {}

    monkeypatch.setattr(service, "load_config", lambda: _config(remote_enabled=True))
    monkeypatch.setattr(service, "get_message", lambda trip_id, message_id: {"id": message_id, "analysisStatus": "pending"})
    monkeypatch.setattr(
        service,
        "analyze_image_locally",
        lambda *args, **kwargs: (
            {
                "processor": "local_ocr",
                "summary": None,
                "extractedText": "blurry text",
                "confidence": 0.2,
                "qualityScore": None,
                "travelSignals": {
                    "locations": [],
                    "dates": [],
                    "prices": [],
                    "lodging": [],
                    "transport": [],
                    "bookingSignals": [],
                },
                "error": None,
            },
            {"width": 400, "height": 600},
        ),
    )
    monkeypatch.setattr(service, "evaluate_quality", lambda *args, **kwargs: {"passed": False, "quality_score": 0.12})
    monkeypatch.setattr(
        service,
        "analyze_image_remotely",
        lambda *args, **kwargs: (_ for _ in ()).throw(RemoteEmbedderError("invalid_response", "bad json")),
    )
    monkeypatch.setattr(service, "finalize_image_message_failure", lambda **kwargs: finalized.update(kwargs) or True)

    service.process_image_message(
        trip_id="trip-1",
        message_id="msg-2",
        image_bytes=b"image-bytes",
        image_mime_type="image/png",
    )

    assert finalized["image_analysis"]["processor"] == "openai_vision"
    assert finalized["image_analysis"]["error"] == "invalid_response"


def test_process_image_message_skips_completed_messages(monkeypatch):
    monkeypatch.setattr(service, "load_config", lambda: _config())
    monkeypatch.setattr(service, "get_message", lambda trip_id, message_id: {"id": message_id, "analysisStatus": "completed"})
    monkeypatch.setattr(service, "analyze_image_locally", lambda *args, **kwargs: pytest.fail("local OCR should be skipped"))

    service.process_image_message(
        trip_id="trip-1",
        message_id="msg-3",
        image_bytes=b"image-bytes",
        image_mime_type="image/png",
    )
