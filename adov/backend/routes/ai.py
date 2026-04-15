# AI route: receives a URL or text, calls Claude to parse travel intent, and writes the result as a Firestore message.
import asyncio
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.anthropic_client import extract_preference, get_chat_response, parse_travel_content
from services.firebase import (
    add_message,
    get_db,
    get_proposals,
    get_recent_messages,
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


async def handle_mention(trip_id: str, sender_name: str) -> None:
    """Fetch recent context (including active proposal vote status), call Claude, write AI reply."""
    loop = asyncio.get_running_loop()
    try:
        msgs_future = loop.run_in_executor(None, lambda: get_recent_messages(trip_id, 10))
        members_future = loop.run_in_executor(None, lambda: get_trip_member_status(trip_id))
        proposals_future = loop.run_in_executor(None, lambda: get_proposals(trip_id))
        member_ids_future = loop.run_in_executor(None, lambda: get_trip_members(trip_id))

        msgs, members, proposals, member_ids = await asyncio.gather(
            msgs_future, members_future, proposals_future, member_ids_future
        )

        # Build extra context: inject vote tallies so Claude can report progress
        extra_context = ""
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
            extra_context = "\n" + "\n".join(vote_lines)

        reply = await loop.run_in_executor(
            None, lambda: get_chat_response(msgs, sender_name, members, extra_context=extra_context)
        )
        if reply:
            add_message(trip_id, {"senderId": "ai", "text": reply, "type": "ai"})
    except Exception as exc:
        print(f"[handle_mention] error: {exc}")


async def handle_proposal_request(trip_id: str, sender_name: str) -> None:
    """
    Trigger the proposal generation flow when @adov is mentioned with a trip-planning phrase.
    Falls back to a regular handle_mention if generation fails or wish pool is too thin.
    """
    loop = asyncio.get_running_loop()
    try:
        from routes.proposals import generate_proposals as _generate_proposals
        from services.auth import get_current_user as _get_current_user

        # Call the proposals generate endpoint logic directly (reuse the service functions)
        from services.firebase import get_wish_pool, get_trip, get_trip_members, get_user
        from services.anthropic_client import generate_trip_proposals
        from services.flights_service import get_cheapest_flight
        import urllib.parse

        wish_pool = await loop.run_in_executor(None, lambda: get_wish_pool(trip_id))

        if len(wish_pool) < 3:
            add_message(
                trip_id,
                {
                    "senderId": "ai",
                    "text": (
                        f"I only have {len(wish_pool)} confirmed destination(s) in the wish pool right now. "
                        "Share at least 3 travel links or ideas first, then ask me again!"
                    ),
                    "type": "ai",
                },
            )
            return

        trip = await loop.run_in_executor(None, lambda: get_trip(trip_id))
        member_ids = await loop.run_in_executor(None, lambda: get_trip_members(trip_id))
        member_count = len(member_ids)

        # Budget
        budgets: list[tuple[int, int]] = []
        for uid in member_ids:
            user = await loop.run_in_executor(None, lambda u=uid: get_user(u))
            if user:
                low, high = user.get("budgetMin"), user.get("budgetMax")
                if low is not None and high is not None:
                    budgets.append((low, high))
        budget = (
            {
                "group_min": max(b[0] for b in budgets),
                "group_max": min(b[1] for b in budgets),
                "members_with_budget": len(budgets),
            }
            if budgets
            else {"group_min": None, "group_max": None, "members_with_budget": 0}
        )

        windows: list[dict] = (trip or {}).get("availableWindows", [])
        outbound_date = windows[0]["start"][:10] if windows else "2026-06-01"

        # Flight estimates
        destinations = [e.get("destination", "") for e in wish_pool if e.get("destination")]
        home_airports: list[str] = []
        for uid in member_ids:
            user = await loop.run_in_executor(None, lambda u=uid: get_user(u))
            if user and user.get("homeAirport"):
                home_airports.append(user["homeAirport"])

        flight_estimates: dict[str, int | None] = {}
        for dest in destinations:
            prices = []
            for origin in home_airports:
                price = await loop.run_in_executor(
                    None,
                    lambda o=origin, d=dest: get_cheapest_flight(o, d, outbound_date, member_count),
                )
                if price is not None:
                    prices.append(price)
            flight_estimates[dest] = min(prices) if prices else None

        proposals_raw = await loop.run_in_executor(
            None,
            lambda: generate_trip_proposals(
                wish_pool=wish_pool,
                windows=windows,
                budget=budget,
                member_count=member_count,
                flight_estimates=flight_estimates,
            ),
        )

        # Handle thin-data response
        if proposals_raw and isinstance(proposals_raw[0], dict) and proposals_raw[0].get("tooThinData"):
            add_message(
                trip_id,
                {
                    "senderId": "ai",
                    "text": proposals_raw[0].get("message", "Not enough travel data yet to propose trips."),
                    "type": "ai",
                },
            )
            return

        from services.firebase import add_proposal

        proposals_data: list[dict] = []
        for p in proposals_raw:
            dates = p.get("suggestedDates", {})
            date_from = dates.get("start", "")
            date_to = dates.get("end", "")
            destination = p.get("destination", "")

            query = f"flights to {destination} {date_from} to {date_to}"
            booking_url = (
                "https://www.google.com/travel/flights?hl=en&q="
                + urllib.parse.quote(query)
                + f"&adults={member_count}"
            )
            proposal_doc = {
                "destination": destination,
                "suggestedDates": dates,
                "estimatedCostPerPerson": p.get("estimatedCostPerPerson"),
                "flightEstimate": p.get("flightEstimate"),
                "rationale": p.get("rationale", ""),
                "tradeoff": p.get("tradeoff", ""),
                "bookingSearchUrl": booking_url,
                "votes": {},
            }
            proposal_id = await loop.run_in_executor(None, lambda pd=proposal_doc: add_proposal(trip_id, pd))
            proposals_data.append({"proposalId": proposal_id, **proposal_doc})

        add_message(
            trip_id,
            {
                "senderId": "ai",
                "text": f"Here are {len(proposals_data)} trip ideas based on your wish pool — vote on your favorite!",
                "type": "proposal",
                "proposalsData": proposals_data,
            },
        )

    except Exception as exc:
        print(f"[handle_proposal_request] error: {exc}")
        # Graceful fallback: treat as regular @adov mention
        await handle_mention(trip_id, sender_name)


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
