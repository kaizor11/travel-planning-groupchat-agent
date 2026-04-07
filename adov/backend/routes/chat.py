# Chat routes: handles message retrieval, sending, SSE streaming, wish pool actions,
# group invite info, and joining a trip — all returning JSON.
# All routes use the /api/trips prefix so Vite can proxy /api to FastAPI without
# conflicting with React Router's client-side /trips/:tripId routes.
import re

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.auth import get_current_user
from services.firebase import (
    add_message,
    add_trip_member,
    add_wish_pool_entry,
    get_messages,
    get_trip,
    get_user,
    stream_messages,
)

router = APIRouter()

URL_REGEX = re.compile(r"https?://[^\s]+")


# ── Trip info ──────────────────────────────────────────────────────────────────

@router.get("/api/trips/{trip_id}")
async def get_trip_messages(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
):
    messages = get_messages(trip_id)
    return {
        "trip_id": trip_id,
        "messages": messages,
        "current_user_id": current_user["uid"],
        "current_user_name": current_user.get("name", ""),
    }


# ── SSE stream ────────────────────────────────────────────────────────────────

@router.get("/api/trips/{trip_id}/stream")
async def message_stream(trip_id: str):
    # SSE stream is unauthenticated — browsers can't set headers on EventSource.
    # The risk is low: messages are non-sensitive and the stream is read-only.
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
    sender_name: str = ""  # display name from Firebase Auth


@router.post("/api/trips/{trip_id}/messages")
async def send_message(
    trip_id: str,
    body: SendMessageBody,
    current_user: dict = Depends(get_current_user),
):
    text = body.text.strip()
    if not text:
        return {"ok": False, "error": "empty message"}

    uid = current_user["uid"]
    sender_name = body.sender_name or current_user.get("name", "")

    url_match = URL_REGEX.search(text)
    msg: dict = {
        "senderId": uid,
        "senderName": sender_name,
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
                sender_id=uid,
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


@router.post("/api/trips/{trip_id}/wishpool")
async def wishpool_action(
    trip_id: str,
    body: WishPoolBody,
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    if body.action == "add":
        entry = {
            "submittedBy": uid,
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


# ── Group invite ───────────────────────────────────────────────────────────────

@router.get("/api/trips/{trip_id}/invite")
async def get_invite_info(trip_id: str):
    """Public endpoint: returns trip preview for join page (no auth required)."""
    trip = get_trip(trip_id)
    member_count = len(trip.get("memberIds", [])) if trip else 0
    return {
        "trip_id": trip_id,
        "member_count": member_count,
        "exists": trip is not None,
    }


@router.post("/api/trips/{trip_id}/join")
async def join_trip(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Add the authenticated user to the trip's memberIds (idempotent)."""
    uid = current_user["uid"]
    add_trip_member(trip_id, uid)
    return {"ok": True, "trip_id": trip_id, "user_id": uid}


# ── Budget reconciliation (group summary — private) ────────────────────────────

@router.get("/api/trips/{trip_id}/budget")
async def get_budget_summary(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return group min/max budget without exposing individual members' numbers."""
    from services.firebase import get_trip_members

    member_ids = get_trip_members(trip_id)
    budgets = []
    for uid in member_ids:
        user = get_user(uid)
        if not user:
            continue
        low = user.get("budgetMin")
        high = user.get("budgetMax")
        if low is not None and high is not None:
            budgets.append((low, high))

    if not budgets:
        return {"group_min": None, "group_max": None, "members_with_budget": 0}

    group_min = max(b[0] for b in budgets)   # highest lower bound = viable floor
    group_max = min(b[1] for b in budgets)   # lowest upper bound = viable ceiling

    return {
        "group_min": group_min,
        "group_max": group_max,
        "members_with_budget": len(budgets),
    }
