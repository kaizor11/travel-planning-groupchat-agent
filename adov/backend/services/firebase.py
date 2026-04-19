# Firebase service: lazy Admin SDK initialization, Firestore CRUD helpers, and SSE-compatible message streaming.
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from urllib.parse import quote

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1.base_document import DocumentSnapshot

logger = logging.getLogger(__name__)

_app: firebase_admin.App | None = None


def _get_app() -> firebase_admin.App:
    global _app
    if _app is not None:
        return _app
    if firebase_admin._apps:
        _app = firebase_admin.get_app()
        return _app

    private_key = os.environ["FIREBASE_ADMIN_PRIVATE_KEY"].replace("\\n", "\n")
    cred = credentials.Certificate(
        {
            "type": "service_account",
            "project_id": os.environ["FIREBASE_ADMIN_PROJECT_ID"],
            "client_email": os.environ["FIREBASE_ADMIN_CLIENT_EMAIL"],
            "private_key": private_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )
    try:
        _app = firebase_admin.initialize_app(cred)
    except Exception:
        raise RuntimeError("Firebase init failed") from None
    return _app


def get_db() -> firestore.Client:
    _get_app()
    return firestore.client()


def _doc_to_dict(doc: DocumentSnapshot) -> dict:
    data = doc.to_dict() or {}
    data["id"] = doc.id
    for field_name in ("timestamp", "updatedAt"):
        ts = data.get(field_name)
        if isinstance(ts, datetime):
            data[field_name] = ts.isoformat()
        elif ts is not None:
            data[field_name] = datetime.fromtimestamp(
                getattr(ts, "seconds", 0), tz=timezone.utc
            ).isoformat()
    return data


def _omit_none(d: dict) -> dict:
    """Remove keys whose value is None for merge-heavy writes."""
    return {k: v for k, v in d.items() if v is not None}


def _messages_collection(trip_id: str):
    return get_db().collection("trips").document(trip_id).collection("messages")


def _storage_bucket_name() -> str:
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
    if not bucket_name:
        raise RuntimeError("FIREBASE_STORAGE_BUCKET is not configured")
    return bucket_name


def get_messages(trip_id: str) -> list[dict]:
    docs = _messages_collection(trip_id).order_by("timestamp").stream()
    msgs = [_doc_to_dict(doc) for doc in docs]
    return [m for m in msgs if m.get("type") != "reset"]


def get_recent_messages(trip_id: str, limit: int = 10) -> list[dict]:
    docs = (
        _messages_collection(trip_id)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    msgs = [_doc_to_dict(doc) for doc in docs]
    msgs.reverse()
    return msgs


def add_message(trip_id: str, msg: dict) -> str:
    ref = _messages_collection(trip_id).document()
    payload = _omit_none({**msg, "timestamp": firestore.SERVER_TIMESTAMP})
    ref.set(payload)
    return ref.id


def reserve_message_id(trip_id: str) -> str:
    return _messages_collection(trip_id).document().id


def create_message_with_id(trip_id: str, message_id: str, msg: dict) -> dict:
    ref = _messages_collection(trip_id).document(message_id)
    ref.set({**msg, "timestamp": firestore.SERVER_TIMESTAMP})
    return _doc_to_dict(ref.get())


def get_message(trip_id: str, message_id: str) -> dict | None:
    doc = _messages_collection(trip_id).document(message_id).get()
    if not doc.exists:
        return None
    return _doc_to_dict(doc)


def upload_image_to_storage(image_path: str, payload: bytes, content_type: str) -> str:
    _get_app()
    bucket = storage.bucket(_storage_bucket_name())
    blob = bucket.blob(image_path)
    download_token = str(uuid.uuid4())
    blob.metadata = {"firebaseStorageDownloadTokens": download_token}
    blob.upload_from_string(payload, content_type=content_type)
    blob.patch()
    return (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/"
        f"{quote(image_path, safe='')}?alt=media&token={download_token}"
    )


def delete_storage_object(image_path: str) -> None:
    if not image_path:
        return
    try:
        _get_app()
        storage.bucket(_storage_bucket_name()).blob(image_path).delete()
    except Exception:
        logger.warning("[storage] failed to delete image path=%s", image_path)


def finalize_image_message_success(
    *,
    trip_id: str,
    message_id: str,
    image_analysis: dict,
    reply_text: str,
) -> str | None:
    db = get_db()
    messages = db.collection("trips").document(trip_id).collection("messages")
    message_ref = messages.document(message_id)
    transaction = db.transaction()

    @firestore.transactional
    def _finalize(transaction):
        snapshot = message_ref.get(transaction=transaction)
        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        if data.get("analysisStatus") == "completed":
            return data.get("analysisReplyMessageId")
        if data.get("analysisReplyMessageId"):
            return data.get("analysisReplyMessageId")
        if data.get("analysisStatus") != "pending":
            return None

        reply_ref = messages.document()
        transaction.set(
            reply_ref,
            {
                "senderId": "ai",
                "text": reply_text,
                "type": "ai",
                "replyToMessageId": message_id,
                "timestamp": firestore.SERVER_TIMESTAMP,
            },
        )
        transaction.update(
            message_ref,
            {
                "analysisStatus": "completed",
                "imageAnalysis": image_analysis,
                "analysisReplyMessageId": reply_ref.id,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        return reply_ref.id

    return _finalize(transaction)


def finalize_image_message_failure(
    *,
    trip_id: str,
    message_id: str,
    image_analysis: dict | None,
) -> bool:
    db = get_db()
    messages = db.collection("trips").document(trip_id).collection("messages")
    message_ref = messages.document(message_id)
    transaction = db.transaction()

    @firestore.transactional
    def _finalize(transaction):
        snapshot = message_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False

        data = snapshot.to_dict() or {}
        if data.get("analysisStatus") != "pending":
            return False

        patch = {
            "analysisStatus": "failed",
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        if image_analysis is not None:
            patch["imageAnalysis"] = image_analysis
        transaction.update(message_ref, patch)
        return True

    return bool(_finalize(transaction))


def delete_message_cascade(trip_id: str, message_id: str) -> None:
    message = get_message(trip_id, message_id)
    if not message:
        return

    if message.get("imagePath"):
        delete_storage_object(message["imagePath"])

    reply_id = message.get("analysisReplyMessageId")
    if reply_id:
        _messages_collection(trip_id).document(reply_id).delete()

    _messages_collection(trip_id).document(message_id).delete()


def upsert_user_preference(trip_id: str, user_id: str, preference: dict) -> None:
    get_db().collection("trips").document(trip_id).collection("preferences").document(
        user_id
    ).set(
        {
            "userId": user_id,
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "items": firestore.ArrayUnion([preference]),
        },
        merge=True,
    )


def add_wish_pool_entry(trip_id: str, entry: dict) -> str:
    db = get_db()
    ref = db.collection("trips").document(trip_id).collection("wishPool").document()
    payload = _omit_none({**entry, "confirmedAt": firestore.SERVER_TIMESTAMP})
    ref.set(payload)
    return ref.id


def upsert_wish_pool_entry(
    trip_id: str,
    uid: str,
    destination: str,
    tags: list,
    estimated_cost: str | None,
    source_url: str | None,
) -> str:
    db = get_db()
    col = db.collection("trips").document(trip_id).collection("wishPool")

    if source_url:
        docs = list(col.where("sourceUrl", "==", source_url).limit(1).stream())
        if docs:
            docs[0].reference.update({"acceptedBy": firestore.ArrayUnion([uid])})
            return docs[0].id

    ref = col.document()
    payload = _omit_none(
        {
            "destination": destination,
            "tags": tags,
            "estimatedCost": estimated_cost,
            "sourceUrl": source_url,
            "acceptedBy": [uid],
            "confirmedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    ref.set(payload)
    return ref.id


def upsert_user(uid: str, name: str, email: str, avatar_url: str) -> None:
    payload = _omit_none({"name": name, "email": email, "avatarUrl": avatar_url})
    get_db().collection("users").document(uid).set(payload, merge=True)


def get_user(uid: str) -> dict | None:
    doc = get_db().collection("users").document(uid).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return data


def update_user(uid: str, fields: dict) -> None:
    get_db().collection("users").document(uid).set(_omit_none(fields), merge=True)


def set_user_calendar_token(uid: str, access_token: str) -> None:
    get_db().collection("users").document(uid).set(
        {"googleCalendarToken": access_token}, merge=True
    )


def clear_user_calendar_token(uid: str) -> None:
    get_db().collection("users").document(uid).update(
        {"googleCalendarToken": firestore.DELETE_FIELD}
    )


def reset_trip(trip_id: str) -> None:
    db = get_db()
    member_ids = get_trip_members(trip_id)

    message_docs = list(db.collection("trips").document(trip_id).collection("messages").stream())
    for doc in message_docs:
        image_path = (doc.to_dict() or {}).get("imagePath")
        if image_path:
            delete_storage_object(image_path)

    for subcol in ("messages", "preferences", "wishPool", "proposals"):
        docs = list(db.collection("trips").document(trip_id).collection(subcol).stream())
        for doc in docs:
            doc.reference.delete()

    update_fields: dict = {"memberIds": []}
    try:
        update_fields["availableWindows"] = firestore.DELETE_FIELD
    except Exception:
        pass
    db.collection("trips").document(trip_id).set(update_fields, merge=True)

    for uid in member_ids:
        try:
            clear_user_calendar_token(uid)
        except Exception:
            pass

    add_message(trip_id, {"senderId": "system", "type": "reset", "text": ""})


def get_trip(trip_id: str) -> dict | None:
    doc = get_db().collection("trips").document(trip_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return data


def add_trip_member(trip_id: str, user_id: str) -> None:
    get_db().collection("trips").document(trip_id).set(
        {"memberIds": firestore.ArrayUnion([user_id])}, merge=True
    )


def get_trip_members(trip_id: str) -> list[str]:
    trip = get_trip(trip_id)
    if not trip:
        return []
    return trip.get("memberIds", [])


def get_trip_member_status(trip_id: str) -> list[dict]:
    member_ids = get_trip_members(trip_id)
    result = []
    for uid in member_ids:
        user = get_user(uid)
        if not user:
            continue
        result.append(
            {
                "name": user.get("name") or uid,
                "calendarConnected": bool(user.get("googleCalendarToken")),
            }
        )
    return result


def store_trip_availability(trip_id: str, windows: list[dict]) -> None:
    get_db().collection("trips").document(trip_id).set(
        {"availableWindows": windows}, merge=True
    )


def get_wish_pool(trip_id: str) -> list[dict]:
    docs = (
        get_db()
        .collection("trips")
        .document(trip_id)
        .collection("wishPool")
        .order_by("confirmedAt")
        .stream()
    )
    result = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        result.append(data)
    return result


def add_proposal(trip_id: str, proposal: dict) -> str:
    ref = (
        get_db()
        .collection("trips")
        .document(trip_id)
        .collection("proposals")
        .document()
    )
    payload = _omit_none({**proposal, "generatedAt": firestore.SERVER_TIMESTAMP})
    ref.set(payload)
    return ref.id


def get_proposals(trip_id: str) -> list[dict]:
    docs = (
        get_db()
        .collection("trips")
        .document(trip_id)
        .collection("proposals")
        .order_by("generatedAt")
        .stream()
    )
    result = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        ts = data.get("generatedAt")
        if isinstance(ts, datetime):
            data["generatedAt"] = ts.isoformat()
        result.append(data)
    return result


def record_vote(trip_id: str, proposal_id: str, user_id: str, vote: str) -> None:
    get_db().collection("trips").document(trip_id).collection("proposals").document(
        proposal_id
    ).set({"votes": {user_id: vote}}, merge=True)


async def stream_messages(trip_id: str) -> AsyncGenerator[str, None]:
    """
    Poll Firestore every second and emit both new messages and updates to existing
    messages. This keeps the chat UI in sync with screenshot analysis patches.
    """
    logger.info("[SSE] stream_messages started for trip %s", trip_id)
    try:
        db = get_db()
        loop = asyncio.get_running_loop()
        fingerprints: dict[str, str] = {}

        try:
            initial = await loop.run_in_executor(
                None,
                lambda: list(
                    db.collection("trips")
                    .document(trip_id)
                    .collection("messages")
                    .order_by("timestamp")
                    .stream()
                ),
            )
            for doc in initial:
                fingerprints[doc.id] = doc.update_time.isoformat() if doc.update_time else ""
            logger.info("[SSE] pre-populated %s message fingerprints", len(fingerprints))
        except Exception as exc:
            logger.warning("[SSE] initial fetch error: %s", exc)

        while True:
            await asyncio.sleep(1)
            try:
                docs = await loop.run_in_executor(
                    None,
                    lambda: list(
                        db.collection("trips")
                        .document(trip_id)
                        .collection("messages")
                        .order_by("timestamp")
                        .stream()
                    ),
                )
                for doc in docs:
                    fingerprint = doc.update_time.isoformat() if doc.update_time else ""
                    if fingerprints.get(doc.id) != fingerprint:
                        fingerprints[doc.id] = fingerprint
                        payload = json.dumps(_doc_to_dict(doc))
                        yield f"data: {payload}\n\n"
            except Exception as exc:
                logger.error("[SSE] poll error for trip=%s: %s", trip_id, exc, exc_info=True)
                yield f"event: error\ndata: {json.dumps({'message': 'stream error'})}\n\n"
                return
    except BaseException as exc:
        logger.error("[SSE] generator crashed: %s: %s", type(exc).__name__, exc)
        raise
