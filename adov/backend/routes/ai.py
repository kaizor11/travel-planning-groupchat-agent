# AI route: receives a URL or text, calls Claude to parse travel intent, and writes the result as a Firestore message.
import asyncio
import logging
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from services.anthropic_client import extract_preference, get_chat_response, parse_travel_content
from services.firebase import (
    add_message,
    get_db,
    get_proposals,
    get_recent_messages,
    get_trip,
    get_trip_member_status,
    get_trip_members,
    upsert_user_preference,
)
from services.instagram_scraper import scrapify_reel
from firebase_admin import firestore

router = APIRouter()

URL_REGEX = re.compile(r"https?://[^\s]+")

SOCIAL_MEDIA_REGEX = re.compile(
    r"instagram|tiktok|youtube|youtu\.be|twitter|x\.com", re.IGNORECASE
)

INSTAGRAM_REEL_REGEX = re.compile(r"instagram\.com/reel")

COST_EMOJI = {"budget": "💸", "mid-range": "💰", "luxury": "💎"}


class ParseRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    trip_id: str
    sender_id: str


_AVAILABILITY_RE = re.compile(
    r"\b(free|available|availability|calendar|schedule|when (can|are|is)|open)\b",
    re.IGNORECASE,
)


async def handle_mention(trip_id: str, sender_name: str, trigger_text: str = "") -> None:
    """Fetch recent context (including active proposal vote status), call Claude, write AI reply."""
    loop = asyncio.get_running_loop()
    try:
        msgs_future = loop.run_in_executor(None, lambda: get_recent_messages(trip_id, 10))
        members_future = loop.run_in_executor(None, lambda: get_trip_member_status(trip_id))
        proposals_future = loop.run_in_executor(None, lambda: get_proposals(trip_id))
        member_ids_future = loop.run_in_executor(None, lambda: get_trip_members(trip_id))
        trip_future = loop.run_in_executor(None, lambda: get_trip(trip_id))

        msgs, members, proposals, member_ids, trip = await asyncio.gather(
            msgs_future, members_future, proposals_future, member_ids_future, trip_future
        )

        # ── Determine the "real" request text ─────────────────────────────────
        # If the trigger is a bare "@adov" (user forgot to include the question),
        # treat the previous user message as the actual request.
        trigger_stripped = re.sub(r"@adov\b", "", trigger_text, flags=re.IGNORECASE).strip()
        is_bare_mention = len(trigger_stripped) < 3

        context_for_analysis = trigger_text
        if is_bare_mention and msgs:
            for m in reversed(msgs[:-1]):  # walk backwards, skip the @adov msg itself
                if m.get("senderId") != "ai":
                    context_for_analysis = m.get("text", "") + " " + trigger_text
                    break

        # ── Calendar availability check ───────────────────────────────────────
        # If an availability keyword is detected, short-circuit with a concise error
        # for any members who haven't connected their calendar.
        # When no specific names are mentioned (e.g. "when is everyone free?"),
        # treat all trip members as the target group.
        _is_availability_question = False
        if members and _AVAILABILITY_RE.search(context_for_analysis):
            _is_availability_question = True
            ctx_lower = context_for_analysis.lower()
            mentioned = [
                m for m in members
                if m.get("name") and re.search(
                    r"\b" + re.escape(m["name"].split()[0].lower()) + r"\b",
                    ctx_lower,
                )
            ]
            # Fall back to all members when no specific names are in the query
            target_members = mentioned if mentioned else members

            missing = [m["name"] for m in target_members if not m["calendarConnected"]]
            if missing:
                names_str = (
                    " and ".join(missing)
                    if len(missing) <= 2
                    else ", ".join(missing[:-1]) + f", and {missing[-1]}"
                )
                verb = "haven't" if len(missing) > 1 else "hasn't"
                add_message(
                    trip_id,
                    {
                        "senderId": "ai",
                        "text": (
                            f"{names_str} {verb} connected their calendar yet. "
                            f"They can connect by tapping the profile icon (top-left) "
                            f"→ Google Calendar → Connect."
                        ),
                        "type": "ai",
                    },
                )
                return

        # ── Build extra context for Claude ────────────────────────────────────
        extra_context_parts: list[str] = []

        # Inject available windows when all members are connected.
        # Always fetch fresh — never use cached availableWindows — so that expired tokens
        # are detected and cleared before we report any availability data.
        if _is_availability_question:
            windows: list[dict] = []
            try:
                from services.calendar_service import fetch_and_store_freebusy
                windows = await loop.run_in_executor(
                    None, lambda: fetch_and_store_freebusy(trip_id)
                )
            except Exception as _exc:
                logger.warning(f"[handle_mention] inline freebusy fetch failed: {_exc}")

            if windows:
                window_lines = [
                    f"  • {w['start'][:10]} to {w['end'][:10]}" for w in windows[:10]
                ]
                extra_context_parts.append(
                    "\n[AVAILABLE FREE WINDOWS (ground truth from Google Calendar — report these to the group):\n"
                    + "\n".join(window_lines) + "]"
                )
            else:
                # Re-fetch member status: fetch_and_store_freebusy may have cleared expired
                # tokens, so the stale `members` list is no longer accurate.
                refreshed_members = get_trip_member_status(trip_id)
                expired = [m["name"] for m in refreshed_members if not m["calendarConnected"]]
                if expired:
                    expired_str = (
                        " and ".join(expired)
                        if len(expired) <= 2
                        else ", ".join(expired[:-1]) + f", and {expired[-1]}"
                    )
                    extra_context_parts.append(
                        f"\n[CALENDAR NOTE: {expired_str}'s Google Calendar token has expired. "
                        f"Tell them to tap the profile icon (top-left) → Google Calendar → Reconnect. "
                        f"Do NOT report any availability windows until all members have reconnected.]"
                    )
                else:
                    extra_context_parts.append(
                        "\n[CALENDAR NOTE: All calendars are connected but no overlapping free windows "
                        "were found in the next 90 days. Tell the group their schedules may be fully booked.]"
                    )

        if proposals:
            vote_lines = ["[ACTIVE PROPOSALS AND CURRENT VOTES — ground truth:]"]
            for p in proposals:
                votes = p.get("votes", {})
                tally = {"yes": 0, "no": 0, "maybe": 0}
                for v in votes.values():
                    if v in tally:
                        tally[v] += 1
                vote_lines.append(
                    f"  • {p.get('destination', '?')}: "
                    f"{len(votes)}/{len(member_ids)} voted — "
                    f"👍 {tally['yes']} 👎 {tally['no']} 🤔 {tally['maybe']}"
                )
            extra_context_parts.append("\n" + "\n".join(vote_lines))

        # Tell Claude which message contains the actual request
        if is_bare_mention:
            extra_context_parts.append(
                "\n[RESPONSE FOCUS: The user sent just \"@adov\" to get your attention. "
                "The actual request is in the message immediately before the @adov message. "
                "Respond to that message's intent — do not just acknowledge the mention.]"
            )

        extra_context = "".join(extra_context_parts)

        reply = await loop.run_in_executor(
            None, lambda: get_chat_response(msgs, sender_name, members, extra_context=extra_context)
        )
        if reply:
            add_message(trip_id, {"senderId": "ai", "text": reply, "type": "ai"})
    except Exception as exc:
        logger.error(f"[handle_mention] error: {exc}", exc_info=True)


async def handle_proposal_request(trip_id: str, sender_name: str, trigger_text: str = "") -> None:
    """
    Trigger the proposal generation flow when @adov is mentioned with a trip-planning phrase.
    Delegates to the shared _run_proposal_generation helper in routes.proposals.
    Falls back to a regular handle_mention if generation fails or wish pool is too thin.
    """
    try:
        from routes.proposals import _run_proposal_generation
        await _run_proposal_generation(trip_id)
    except Exception as exc:
        logger.error(f"[handle_proposal_request] error: {exc}", exc_info=True)
        # Graceful fallback: treat as regular @adov mention
        await handle_mention(trip_id, sender_name, trigger_text=trigger_text)


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
        logger.error(f"[handle_preference] error: {exc}", exc_info=True)


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
            location = temp.get("locationName") or ""
            caption = temp.get("caption") or ""
            transcript = temp.get("transcript") or ""
            hashtags = temp.get("hashtags") or []

            # Build rich combined text so Claude can extract estimatedCost, better tags, etc.
            text_parts: list[str] = []
            if location:
                text_parts.append(f"Location: {location}")
            if caption:
                text_parts.append(f"Caption: {caption}")
            if transcript:
                text_parts.append(f"Video transcript: {transcript}")
            if hashtags:
                text_parts.append(f"Hashtags: {' '.join(hashtags[:15])}")
            combined_text = "\n".join(text_parts) or None

            parsed = await loop.run_in_executor(
                None, lambda: parse_travel_content(url=body.url, text=combined_text)
            )
            # Trust Apify's physical location name over Claude's inference
            if location and not parsed.get("destination"):
                parsed["destination"] = location
            if location:
                parsed["confidence"] = max(parsed.get("confidence", 0), 0.85)

    except Exception as exc:
        logger.error(
            f"[parse_content] Failed for trip={body.trip_id}, url={body.url}: {exc}",
            exc_info=True,
        )
        # Fall through — always write a fallback message below


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
