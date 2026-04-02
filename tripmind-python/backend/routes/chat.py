# Chat routes: handles message retrieval, sending, SSE streaming, and wish pool actions — all returning JSON.
# All routes use the /api/trips prefix so Vite can proxy /api to FastAPI without
# conflicting with React Router's client-side /trips/:tripId routes.
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.firebase import add_message, add_wish_pool_entry, get_messages, stream_messages

router = APIRouter()

URL_REGEX = re.compile(r"https?://[^\s]+")

# Temporary hardcoded user until Week 2 auth is added
TEMP_USER_ID = "dev-user-1"


@router.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str):
    messages = get_messages(trip_id)
    return {"trip_id": trip_id, "messages": messages, "current_user_id": TEMP_USER_ID}


# ── SSE stream ────────────────────────────────────────────────────────────────

@router.get("/api/trips/{trip_id}/stream")
async def message_stream(trip_id: str):
    return StreamingResponse(
        stream_messages(trip_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Send message ──────────────────────────────────────────────────────────────

class SendMessageBody(BaseModel):
    text: str
    sender_id: str = TEMP_USER_ID


@router.post("/api/trips/{trip_id}/messages")
async def send_message(trip_id: str, body: SendMessageBody):
    text = body.text.strip()
    if not text:
        return {"ok": False, "error": "empty message"}

    url_match = URL_REGEX.search(text)
    msg: dict = {
        "senderId": body.sender_id,
        "text": text,
        "type": "user",
    }
    if url_match:
        msg["attachedUrl"] = url_match.group(0)

    msg_id = add_message(trip_id, msg)

    # Trigger AI parsing inline if a URL was detected
    if url_match:
        from routes.ai import parse_content, ParseRequest

        caption = text.replace(url_match.group(0), "").strip() or None
        await parse_content(
            ParseRequest(
                url=url_match.group(0),
                text=caption,
                trip_id=trip_id,
                sender_id=body.sender_id,
            )
        )

    return {"ok": True, "id": msg_id}


# ── Wish pool confirm / skip ───────────────────────────────────────────────────

class WishPoolBody(BaseModel):
    action: str  # "add" or "skip"
    destination: str
    tags: list[str] = []
    estimated_cost: str | None = None
    source_url: str | None = None
    submitted_by: str = TEMP_USER_ID


@router.post("/api/trips/{trip_id}/wishpool")
async def wishpool_action(trip_id: str, body: WishPoolBody):
    if body.action == "add":
        entry = {
            "submittedBy": body.submitted_by,
            "destination": body.destination,
            "tags": body.tags,
        }
        if body.estimated_cost:
            entry["estimatedCost"] = body.estimated_cost
        if body.source_url:
            entry["sourceUrl"] = body.source_url
        entry_id = add_wish_pool_entry(trip_id, entry)
        return {"ok": True, "id": entry_id}

    return {"ok": True, "skipped": True}
