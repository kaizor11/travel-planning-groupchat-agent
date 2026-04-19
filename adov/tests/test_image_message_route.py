from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from routes import chat
from services.auth import get_current_user


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[get_current_user] = lambda: {"uid": "user-1", "name": "Alice"}
    return app


def test_send_image_message_returns_created_message(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(
        chat,
        "create_pending_image_message",
        lambda **kwargs: {
            "id": "msg-1",
            "type": "user",
            "senderId": kwargs["sender_id"],
            "senderName": kwargs["sender_name"],
            "text": kwargs["caption_text"],
            "imageUrl": "https://example.com/file.png",
            "imagePath": "chat_screenshots/trip-1/msg-1/file.png",
            "imageMimeType": kwargs["image_mime_type"],
            "imageName": "file.png",
            "analysisStatus": "pending",
            "imageAnalysis": None,
            "analysisReplyMessageId": None,
        },
    )
    monkeypatch.setattr(chat, "process_image_message", lambda **kwargs: captured.update(kwargs))

    client = TestClient(_build_app())
    response = client.post(
        "/api/trips/trip-1/messages/image",
        files={"file": ("file.png", b"image-bytes", "image/png")},
        data={"text": "caption", "sender_name": "Alice"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "msg-1"
    assert body["analysisStatus"] == "pending"
    assert body["imageUrl"] == "https://example.com/file.png"
    assert captured["message_id"] == "msg-1"


def test_send_image_message_returns_400_on_validation_error(monkeypatch):
    monkeypatch.setattr(
        chat,
        "create_pending_image_message",
        lambda **kwargs: (_ for _ in ()).throw(chat.ImageUploadValidationError("bad image")),
    )

    client = TestClient(_build_app())
    response = client.post(
        "/api/trips/trip-1/messages/image",
        files={"file": ("file.png", b"image-bytes", "image/png")},
        data={"text": "caption", "sender_name": "Alice"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bad image"
