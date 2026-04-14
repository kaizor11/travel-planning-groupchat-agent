# AI route: receives a URL or text, calls Claude to parse travel intent, and writes the result as a Firestore message.
import asyncio
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.anthropic_client import extract_preference, get_chat_response, parse_travel_content
from services.firebase import add_message, get_db, get_recent_messages, get_trip_member_status, upsert_user_preference
from services.instagram_scraper import scrapify_reel
from firebase_admin import firestore

router = APIRouter()

URL_REGEX = re.compile(r"https?://[^\s]+")

SOCIAL_MEDIA_REGEX = re.compile(
    r"instagram|tiktok|youtube|youtu\.be|twitter|x\.com", re.IGNORECASE
)

INSTAGRAM_REEL_REGEX = re.compile(r"*instagram\.com/reel*")

COST_EMOJI = {"budget": "💸", "mid-range": "💰", "luxury": "💎"}


class ParseRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    trip_id: str
    sender_id: str


async def handle_mention(trip_id: str, sender_name: str) -> None:
    """Fetch recent context, call Claude, write an AI reply to the chat."""
    loop = asyncio.get_running_loop()
    try:
        msgs_future = loop.run_in_executor(None, lambda: get_recent_messages(trip_id, 10))
        members_future = loop.run_in_executor(None, lambda: get_trip_member_status(trip_id))
        msgs, members = await asyncio.gather(msgs_future, members_future)
        reply = await loop.run_in_executor(None, lambda: get_chat_response(msgs, sender_name, members))
        if reply:
            add_message(trip_id, {"senderId": "ai", "text": reply, "type": "ai"})
    except Exception as exc:
        print(f"[handle_mention] error: {exc}")


async def handle_preference(trip_id: str, sender_id: str, text: str) -> None:
    """Extract a preference from text and silently store it — no chat message written."""
    loop = asyncio.get_running_loop()
    try:
        pref = await loop.run_in_executor(None, lambda: extract_preference(text))
        if pref:
            await loop.run_in_executor(
                None, lambda: upsert_user_preference(trip_id, sender_id, pref)
            )
    except Exception as exc:
        print(f"[handle_preference] error: {exc}")


@router.post("/api/ai/parse-content")
async def parse_content(body: ParseRequest):
    if not body.url and not body.text:
        raise HTTPException(status_code=400, detail="url or text is required")

    is_social = bool(body.url and SOCIAL_MEDIA_REGEX.search(body.url))
    is_reel = bool(body.url and INSTAGRAM_REEL_REGEX.search(body.url))

    # Run in a thread so the asyncio event loop stays free while Claude responds.
    # Without this, the 2-5 s blocking call would stall uvicorn, killing the SSE stream.
    parsed: dict | None = None
    try:
        loop = asyncio.get_running_loop()
        if not is_reel:
            parsed = await loop.run_in_executor(
                None, lambda: parse_travel_content(url=body.url, text=body.text)
            )
        else:
            temp = await loop.run_in_executor(
                None, lambda: scrapify_reel(body.url)
            )   
            parsed = dict()
            parsed["destination"] = temp["location"]
            parsed["tags"] = temp.get("tags", [])
            parsed["estimatedCost"] = "$15" #placeholder, maybe add more parsing logic or call to claude
            parsed["confidence"] = 0.8 #placeholder

    except Exception:
        pass  # Fall through — always write a fallback message below


    high_confidence = parsed is not None and parsed.get("confidence", 0) >= 0.7

    if high_confidence:
        destination = parsed.get("destination", "")  # type: ignore[union-attr]
        tags = parsed.get("tags", [])  # type: ignore[union-attr]
        estimated_cost = parsed.get("estimatedCost")  # type: ignore[union-attr]
        tag_str = ", ".join(tags)
        cost_str = f", {estimated_cost}" if estimated_cost else ""
        ai_text = (
            f"Found a travel idea: **{destination}** ({tag_str}{cost_str}). "
            f"Add it to the wish pool?"
        )
        msg: dict = {
            "senderId": "ai",
            "text": ai_text,
            "type": "wishpool_confirm",
            "parsedData": parsed,
        }
    elif is_social:
        ai_text = (
            "I can see the link but can't view the content — "
            "can you paste the caption or describe where this is? I'll save it to the wish pool."
        )
        msg = {"senderId": "ai", "text": ai_text, "type": "ai"}
    else:
        ai_text = (
            "I couldn't pull a clear destination from that link. "
            "Can you paste the caption or describe it?"
        )
        msg = {"senderId": "ai", "text": ai_text, "type": "ai"}

    if body.url:
        msg["attachedUrl"] = body.url

    add_message(body.trip_id, msg)

    return {**(parsed or {}), "needsConfirmation": not high_confidence}
