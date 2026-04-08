# Firebase service: lazy Admin SDK initialization, Firestore CRUD helpers, and SSE-compatible message streaming.
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_document import DocumentSnapshot

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
    _app = firebase_admin.initialize_app(cred)
    return _app


def get_db() -> firestore.Client:
    _get_app()
    return firestore.client()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _doc_to_dict(doc: DocumentSnapshot) -> dict:
    data = doc.to_dict() or {}
    data["id"] = doc.id
    # DatetimeWithNanoseconds (Firestore's timestamp type) is a datetime subclass —
    # json.dumps can't serialize datetime, so convert everything to ISO strings here.
    ts = data.get("timestamp")
    if isinstance(ts, datetime):
        data["timestamp"] = ts.isoformat()
    elif ts is not None:
        # Fallback: proto Timestamp has .seconds/.nanos directly
        data["timestamp"] = datetime.fromtimestamp(
            getattr(ts, "seconds", 0), tz=timezone.utc
        ).isoformat()
    return data


def _omit_none(d: dict) -> dict:
    """Remove keys whose value is None so Firestore doesn't reject them."""
    return {k: v for k, v in d.items() if v is not None}


# ── Read ──────────────────────────────────────────────────────────────────────

def get_messages(trip_id: str) -> list[dict]:
    db = get_db()
    q = (
        db.collection("trips")
        .document(trip_id)
        .collection("messages")
        .order_by("timestamp")
    )
    return [_doc_to_dict(doc) for doc in q.stream()]


# ── Write ─────────────────────────────────────────────────────────────────────

def get_recent_messages(trip_id: str, limit: int = 10) -> list[dict]:
    """Return the most recent `limit` messages, ordered oldest-first."""
    db = get_db()
    docs = (
        db.collection("trips")
        .document(trip_id)
        .collection("messages")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    msgs = [_doc_to_dict(doc) for doc in docs]
    msgs.reverse()
    return msgs


def add_message(trip_id: str, msg: dict) -> str:
    db = get_db()
    ref = (
        db.collection("trips")
        .document(trip_id)
        .collection("messages")
        .document()
    )
    payload = _omit_none({**msg, "timestamp": firestore.SERVER_TIMESTAMP})
    ref.set(payload)
    return ref.id


def upsert_user_preference(trip_id: str, user_id: str, preference: dict) -> None:
    """Append a preference item to /trips/{tripId}/preferences/{userId}."""
    db = get_db()
    db.collection("trips").document(trip_id).collection("preferences").document(
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
    ref = (
        db.collection("trips")
        .document(trip_id)
        .collection("wishPool")
        .document()
    )
    payload = _omit_none({**entry, "confirmedAt": firestore.SERVER_TIMESTAMP})
    ref.set(payload)
    return ref.id


# ── User helpers ─────────────────────────────────────────────────────────────

def upsert_user(uid: str, name: str, email: str, avatar_url: str) -> None:
    """Create or merge user record at /users/{uid}. Safe to call on every request."""
    db = get_db()
    payload = _omit_none({"name": name, "email": email, "avatarUrl": avatar_url})
    db.collection("users").document(uid).set(payload, merge=True)


def get_user(uid: str) -> dict | None:
    """Return user doc from /users/{uid}, or None if not found."""
    db = get_db()
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return data


def update_user(uid: str, fields: dict) -> None:
    """Merge arbitrary fields into /users/{uid}. Never writes None values."""
    db = get_db()
    db.collection("users").document(uid).set(_omit_none(fields), merge=True)


def set_user_calendar_token(uid: str, access_token: str) -> None:
    """Store Google OAuth access token for calendar queries. Never logged."""
    db = get_db()
    db.collection("users").document(uid).set(
        {"googleCalendarToken": access_token}, merge=True
    )


# ── Trip membership helpers ──────────────────────────────────────────────────

def get_trip(trip_id: str) -> dict | None:
    """Return trip doc from /trips/{tripId}, or None if not found."""
    db = get_db()
    doc = db.collection("trips").document(trip_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return data


def add_trip_member(trip_id: str, user_id: str) -> None:
    """Add user_id to /trips/{tripId}.memberIds (arrayUnion — idempotent)."""
    db = get_db()
    db.collection("trips").document(trip_id).set(
        {"memberIds": firestore.ArrayUnion([user_id])}, merge=True
    )


def get_trip_members(trip_id: str) -> list[str]:
    """Return memberIds array from /trips/{tripId}. Empty list if trip missing."""
    trip = get_trip(trip_id)
    if not trip:
        return []
    return trip.get("memberIds", [])


def store_trip_availability(trip_id: str, windows: list[dict]) -> None:
    """Persist free/busy overlap windows onto the trip document."""
    db = get_db()
    db.collection("trips").document(trip_id).set(
        {"availableWindows": windows}, merge=True
    )


# ── SSE streaming ─────────────────────────────────────────────────────────────

async def stream_messages(trip_id: str) -> AsyncGenerator[str, None]:
    """
    Polls Firestore every second for new messages and yields raw SSE-formatted strings.
    Uses StreamingResponse (not sse_starlette) to avoid any library version issues.
    Format: "data: <json>\\n\\n"
    """
    print(f"[SSE] stream_messages started for trip {trip_id}")
    try:
        db = get_db()
        loop = asyncio.get_running_loop()
        seen_ids: set[str] = set()

        # Pre-populate seen_ids so we don't re-emit messages from before the stream opened
        try:
            initial = await loop.run_in_executor(
                None,
                lambda: list(
                    db.collection("trips").document(trip_id)
                    .collection("messages").stream()
                ),
            )
            for doc in initial:
                seen_ids.add(doc.id)
            print(f"[SSE] pre-populated {len(seen_ids)} seen IDs")
        except Exception as exc:
            print(f"[SSE] initial fetch error: {exc}")

        # Poll every second — no threading bridge, no on_snapshot, no asyncio.Queue
        while True:
            await asyncio.sleep(1)
            try:
                docs = await loop.run_in_executor(
                    None,
                    lambda: list(
                        db.collection("trips").document(trip_id)
                        .collection("messages").order_by("timestamp").stream()
                    ),
                )
                for doc in docs:
                    if doc.id not in seen_ids:
                        seen_ids.add(doc.id)
                        data = _doc_to_dict(doc)
                        try:
                            payload = json.dumps(data)
                            print(f"[SSE] yielding message {doc.id}")
                            yield f"data: {payload}\n\n"
                        except (TypeError, ValueError) as exc:
                            print(f"[SSE] serialization error (message skipped): {exc}")
            except Exception as exc:
                print(f"[SSE] poll error: {exc}")
    except BaseException as exc:
        print(f"[SSE] generator crashed: {type(exc).__name__}: {exc}")
        raise
