# AI route: receives a URL or text, calls Claude to parse travel intent, and writes the result as a Firestore message.
import asyncio
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.anthropic_client import parse_travel_content
from services.firebase import add_message, get_db
from firebase_admin import firestore

router = APIRouter()

URL_REGEX = re.compile(r"https?://[^\s]+")

SOCIAL_MEDIA_REGEX = re.compile(
    r"instagram|tiktok|youtube|youtu\.be|twitter|x\.com", re.IGNORECASE
)

COST_EMOJI = {"budget": "💸", "mid-range": "💰", "luxury": "💎"}


class ParseRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    trip_id: str
    sender_id: str


@router.post("/api/ai/parse-content")
async def parse_content(body: ParseRequest):
    if not body.url and not body.text:
        raise HTTPException(status_code=400, detail="url or text is required")

    is_social = bool(body.url and SOCIAL_MEDIA_REGEX.search(body.url))

    # Run in a thread so the asyncio event loop stays free while Claude responds.
    # Without this, the 2-5 s blocking call would stall uvicorn, killing the SSE stream.
    parsed: dict | None = None
    try:
        loop = asyncio.get_running_loop()
        parsed = await loop.run_in_executor(
            None, lambda: parse_travel_content(url=body.url, text=body.text)
        )
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
