# Proposals route: generate trip proposals, list them, and record in-chat votes.
import asyncio
import logging
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from services.activity_log import log_event
from services.auth import get_current_user
from services.firebase import (
    add_message,
    add_proposal,
    get_proposals,
    get_trip,
    get_trip_members,
    get_user,
    get_wish_pool,
    record_vote,
)
from services.anthropic_client import generate_trip_proposals
from services.flights_service import get_cheapest_flight

router = APIRouter()
logger = logging.getLogger(__name__)

TRIP_ID_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"

# Aliases for common non-canonical city names Claude might return despite prompt instructions.
# Key: lowercase raw string → Value: canonical display name.
_CITY_ALIASES: dict[str, str] = {
    "nyc": "New York City, NY",
    "new york": "New York City, NY",
    "manhattan": "New York City, NY",
    "brooklyn": "New York City, NY",
    "queens": "New York City, NY",
    "the bronx": "New York City, NY",
    "la": "Los Angeles, CA",
    "hollywood": "Los Angeles, CA",
    "sf": "San Francisco, CA",
    "san fran": "San Francisco, CA",
    "vegas": "Las Vegas, NV",
    "london": "London, UK",
    "paris": "Paris, France",
    "tokyo": "Tokyo, Japan",
    "rome": "Rome, Italy",
    "barcelona": "Barcelona, Spain",
    "amsterdam": "Amsterdam, Netherlands",
    "bangkok": "Bangkok, Thailand",
    "bali": "Bali, Indonesia",
    "cancun": "Cancún, Mexico",
}


def _normalize_destination(dest: str) -> tuple[str, str]:
    """Return (canonical_key, display_name) for a destination string, resolving common aliases."""
    raw_lower = dest.lower().strip()
    if raw_lower in _CITY_ALIASES:
        canonical = _CITY_ALIASES[raw_lower]
        return canonical.lower(), canonical
    return raw_lower, dest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_accepted_by(entry: dict) -> list[str]:
    """Normalize acceptedBy across old submittedBy schema and new acceptedBy schema."""
    accepted = entry.get("acceptedBy")
    if accepted:
        return accepted
    legacy = entry.get("submittedBy")
    return [legacy] if legacy else []


def _aggregate_destinations(wish_pool: list[dict], member_count: int) -> list[dict]:
    """
    Group wishpool entries by destination, count unique acceptors and total votes.
    Filter to destinations accepted by strict majority (> 50%) of members.
    Returns list of {destination, entries, total_votes} sorted by total_votes desc, max 5.
    """
    dest_map: dict[str, dict] = defaultdict(
        lambda: {"entries": [], "unique_acceptors": set(), "total_votes": 0, "display_name": ""}
    )
    for entry in wish_pool:
        dest = entry.get("destination", "").strip()
        if not dest:
            continue
        accepted = _get_accepted_by(entry)
        key, display = _normalize_destination(dest)
        dest_map[key]["entries"].append(entry)
        dest_map[key]["unique_acceptors"].update(accepted)
        dest_map[key]["total_votes"] += len(accepted)
        if not dest_map[key]["display_name"]:
            dest_map[key]["display_name"] = display

    threshold = member_count / 2  # strict majority: unique_acceptors count must be > threshold
    qualified = [
        {
            "destination": data["display_name"],
            "entries": data["entries"],
            "total_votes": data["total_votes"],
        }
        for data in dest_map.values()
        if len(data["unique_acceptors"]) > threshold
    ]
    qualified.sort(key=lambda x: x["total_votes"], reverse=True)
    return qualified[:5]


def _check_proposal_readiness(trip_id: str, member_ids: list[str]) -> dict:
    """Returns {missing_budget: [names], missing_calendar: [names]}."""
    missing_budget: list[str] = []
    missing_calendar: list[str] = []
    for uid in member_ids:
        user = get_user(uid)
        if not user:
            continue
        name = user.get("name") or uid
        if user.get("budgetMin") is None or user.get("budgetMax") is None:
            missing_budget.append(name)
        if not user.get("googleCalendarToken"):
            missing_calendar.append(name)
    return {"missing_budget": missing_budget, "missing_calendar": missing_calendar}


def _get_group_budget(trip_id: str) -> dict:
    """Compute group budget overlap across all members with budgets set."""
    member_ids = get_trip_members(trip_id)
    budgets: list[tuple[int, int]] = []
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

    return {
        "group_min": max(b[0] for b in budgets),
        "group_max": min(b[1] for b in budgets),
        "members_with_budget": len(budgets),
    }


def _make_booking_search_url(destination: str, date_from: str, date_to: str, adults: int, origin: str | None = None) -> str:
    """Generate a pre-filled Google Flights search URL for the proposal."""
    def _fmt_date(iso: str) -> str:
        try:
            d = datetime.strptime(iso[:10], "%Y-%m-%d")
            return d.strftime(f"%B {d.day}, %Y")
        except ValueError:
            return iso

    from_part = f"from {origin} " if origin else ""
    query = f"flights {from_part}to {destination} {_fmt_date(date_from)} to {_fmt_date(date_to)}"
    return (
        "https://www.google.com/travel/flights?hl=en&q="
        + urllib.parse.quote(query)
        + f"&adults={adults}"
    )


def _fetch_flight_estimates(trip_id: str, destinations: list[str], outbound_date: str, adults: int) -> tuple[dict[str, int | None], list[str]]:
    """
    For each destination, find the cheapest flight from any member's homeAirport.
    Returns (estimates dict, home_airports list).
    """
    member_ids = get_trip_members(trip_id)
    home_airports: list[str] = []
    for uid in member_ids:
        user = get_user(uid)
        if user and user.get("homeAirport"):
            home_airports.append(user["homeAirport"])

    if not home_airports:
        return {dest: None for dest in destinations}, []

    estimates: dict[str, int | None] = {}
    for dest in destinations:
        prices: list[int] = []
        for origin in home_airports:
            price = get_cheapest_flight(
                origin=origin,
                destination=dest,
                outbound_date=outbound_date,
                adults=adults,
            )
            if price is not None:
                prices.append(price)
        estimates[dest] = min(prices) if prices else None

    return estimates, home_airports


def _pick_outbound_date(windows: list[dict]) -> str:
    """
    Pick the soonest future window start date for flight lookup.
    Falls back to 60 days from now if no windows exist or all are in the past.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    for window in windows:
        start = window.get("start", "")[:10]
        if start >= today:
            return start
    # No windows, or all stale — use a near-future fallback
    return (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")


def _declare_winning_destination(trip_id: str, proposals: list[dict], member_count: int) -> None:
    """
    Compare yes-vote counts across all proposals and write a single winner announcement.
    Called once when every member has voted on every proposal.
    """
    scored = [
        (sum(1 for v in p.get("votes", {}).values() if v == "yes"), p.get("destination", "this destination"))
        for p in proposals
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return

    top_yes, top_dest = scored[0]
    if top_yes == 0:
        ai_text = (
            "All votes are in — no destination received a yes vote. "
            "Want to revisit the wish pool or generate new proposals?"
        )
    elif len(scored) > 1 and scored[1][0] == top_yes:
        tied = [dest for yes, dest in scored if yes == top_yes]
        tied_str = " and ".join(f"**{d}**" for d in tied)
        ai_text = (
            f"All votes are in! It's a tie between {tied_str} with {top_yes} yes vote(s) each. "
            "Group, you decide — want to do another round?"
        )
    else:
        ai_text = (
            f"All votes are in! **{top_dest}** wins with {top_yes} yes vote(s). Time to book!"
        )

    add_message(trip_id, {"senderId": "ai", "text": ai_text, "type": "ai"})
    log_event("ai_reply", trip_id=trip_id, preview=ai_text[:80])


# ── Shared proposal generation core (used by REST endpoint and @adov trigger) ──

async def _run_proposal_generation(trip_id: str, force: bool = False) -> dict:
    """
    Full proposal generation flow: wish pool aggregation → readiness check → budget → flights → Claude → write.
    Returns {"ok": True, "proposals": [...]} or {"ok": False, "reason": "..."}.
    Writes proposals and a proposal-type chat message to Firestore.
    Raises HTTPException on unrecoverable errors.
    force=True skips the budget/calendar readiness check.
    """
    loop = asyncio.get_running_loop()

    # Gather all context concurrently
    wish_pool_future = loop.run_in_executor(None, lambda: get_wish_pool(trip_id))
    trip_future = loop.run_in_executor(None, lambda: get_trip(trip_id))
    budget_future = loop.run_in_executor(None, lambda: _get_group_budget(trip_id))
    member_ids_future = loop.run_in_executor(None, lambda: get_trip_members(trip_id))

    wish_pool, trip, budget, member_ids = await asyncio.gather(
        wish_pool_future, trip_future, budget_future, member_ids_future
    )

    member_count = len(member_ids)

    # Aggregate wishpool entries by destination and filter to strict-majority-accepted ones
    aggregated = _aggregate_destinations(wish_pool, member_count)
    if not aggregated:
        _nudge = (
            "No destinations have enough votes yet. "
            "Share travel links and have the group click Add to build up the wish pool."
        )
        add_message(trip_id, {"senderId": "ai", "text": _nudge, "type": "ai"})
        log_event("ai_reply", trip_id=trip_id, preview=_nudge[:80])
        return {"ok": False, "reason": "no_qualified_destinations"}

    # Pre-flight readiness check: warn about missing budget / calendar (skipped when force=True)
    if not force:
        readiness = await loop.run_in_executor(
            None, lambda: _check_proposal_readiness(trip_id, member_ids)
        )
        parts: list[str] = []
        if readiness["missing_budget"]:
            names = ", ".join(readiness["missing_budget"])
            parts.append(f"{names} haven't set a budget yet (tap Profile → Budget)")
        if readiness["missing_calendar"]:
            names = ", ".join(readiness["missing_calendar"])
            parts.append(
                f"{names} haven't connected their calendar "
                f"(tap Profile → Google Calendar → Connect)"
            )
        if parts:
            _readiness_msg = (
                "Before I generate proposals: " + " and ".join(parts) + ".\n"
                'To generate with the info I have now, say "@adov generate anyway".'
            )
            add_message(trip_id, {"senderId": "ai", "text": _readiness_msg, "type": "ai"})
            log_event("ai_reply", trip_id=trip_id, preview=_readiness_msg[:80])
            return {"ok": False, "reason": "missing_data", "details": readiness}

    windows: list[dict] = (trip or {}).get("availableWindows", [])

    # Pick nearest future window start date; fall back to 60 days from now
    outbound_date = _pick_outbound_date(windows)

    # Fetch real flight prices from SerpAPI if members have home airports set
    destinations_to_check = [d["destination"] for d in aggregated]
    home_airports: list[str] = []
    try:
        flight_estimates, home_airports = await loop.run_in_executor(
            None,
            lambda: _fetch_flight_estimates(trip_id, destinations_to_check, outbound_date, member_count),
        )
    except Exception as exc:
        logger.warning(f"[proposals] flight estimate error (non-fatal): {exc}")
        flight_estimates = {}

    primary_origin = home_airports[0] if home_airports else None

    # Call Claude to generate one proposal per aggregated destination
    try:
        proposals_raw = await loop.run_in_executor(
            None,
            lambda: generate_trip_proposals(
                aggregated_destinations=aggregated,
                windows=windows,
                budget=budget,
                member_count=member_count,
                flight_estimates=flight_estimates,
            ),
        )
    except Exception as exc:
        logger.error(f"[proposals] Claude error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate proposals")

    # Persist each proposal and build the chat message payload
    proposals_data: list[dict] = []
    for p in proposals_raw:
        dates = p.get("suggestedDates", {})
        date_from = dates.get("start", "")[:10]
        date_to = dates.get("end", "")[:10]
        destination = p.get("destination", "")

        booking_url = _make_booking_search_url(destination, date_from, date_to, member_count, origin=primary_origin)

        proposal_doc = {
            "destination": destination,
            "suggestedDates": {"start": date_from, "end": date_to},
            "estimatedCostPerPerson": p.get("estimatedCostPerPerson"),
            "flightEstimate": p.get("flightEstimate"),
            "rationale": p.get("rationale", ""),
            "tradeoff": p.get("tradeoff", ""),
            "bookingSearchUrl": booking_url,
            "votes": {},
        }
        proposal_id = await loop.run_in_executor(None, lambda pd=proposal_doc: add_proposal(trip_id, pd))
        proposals_data.append({"proposalId": proposal_id, **proposal_doc})

    # Write a single proposal-type message to the chat with all proposals embedded
    add_message(
        trip_id,
        {
            "senderId": "ai",
            "text": f"Here are {len(proposals_data)} trip ideas based on your wish pool — vote on your favorite!",
            "type": "proposal",
            "proposalsData": proposals_data,
        },
    )
    log_event("proposals_generated", trip_id=trip_id, count=len(proposals_data),
              destinations=[p["destination"] for p in proposals_data])

    return {"ok": True, "proposals": proposals_data}


# ── Generate proposals ────────────────────────────────────────────────────────

@router.post("/api/trips/{trip_id}/proposals/generate")
async def generate_proposals(
    trip_id: str = Path(..., pattern=TRIP_ID_PATTERN),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate 2–3 trip proposals from wish pool + availability + budget.
    Writes each proposal to Firestore and posts a 'proposal' message to the chat.
    """
    result = await _run_proposal_generation(trip_id)
    return result


# ── List proposals ────────────────────────────────────────────────────────────

@router.get("/api/trips/{trip_id}/proposals")
async def list_proposals(
    trip_id: str = Path(..., pattern=TRIP_ID_PATTERN),
    current_user: dict = Depends(get_current_user),
):
    """Return all proposals for a trip with current vote counts."""
    loop = asyncio.get_running_loop()
    proposals = await loop.run_in_executor(None, lambda: get_proposals(trip_id))
    return {"proposals": proposals}


# ── Vote ──────────────────────────────────────────────────────────────────────

class VoteBody(BaseModel):
    vote: str  # "yes" | "no" | "maybe"


@router.post("/api/trips/{trip_id}/proposals/{proposal_id}/vote")
async def cast_vote(
    trip_id: str = Path(..., pattern=TRIP_ID_PATTERN),
    proposal_id: str = Path(..., pattern=TRIP_ID_PATTERN),
    body: VoteBody = ...,
    current_user: dict = Depends(get_current_user),
):
    """Record this user's vote and write an AI progress update to chat."""
    valid_votes = {"yes", "no", "maybe"}
    if body.vote not in valid_votes:
        raise HTTPException(status_code=400, detail="vote must be one of: yes, no, maybe")

    uid = current_user["uid"]
    loop = asyncio.get_running_loop()

    # Verify proposal exists before recording vote (prevent orphaned data)
    all_proposals = await loop.run_in_executor(None, lambda: get_proposals(trip_id))
    target = next((p for p in all_proposals if p["id"] == proposal_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Record the vote
    await loop.run_in_executor(None, lambda: record_vote(trip_id, proposal_id, uid, body.vote))
    logger.info(f"[audit] user={uid} action=vote trip={trip_id} proposal={proposal_id} vote={body.vote}")

    # Refresh proposal to get updated vote map
    all_proposals = await loop.run_in_executor(None, lambda: get_proposals(trip_id))
    target = next((p for p in all_proposals if p["id"] == proposal_id), None)

    votes: dict = target.get("votes", {}) if target else {}
    tally = {"yes": 0, "no": 0, "maybe": 0}
    for v in votes.values():
        if v in tally:
            tally[v] += 1

    # Determine how many members still need to vote
    member_ids = await loop.run_in_executor(None, lambda: get_trip_members(trip_id))
    member_count = len(member_ids)
    voted_count = len(votes)
    remaining = member_count - voted_count

    # Build AI progress message
    destination = (target or {}).get("destination", "this proposal")
    if remaining > 0:
        ai_text = (
            f"{voted_count} of {member_count} members have voted on **{destination}** "
            f"— waiting on {remaining} more."
        )
    else:
        # All voted — announce result
        if tally["yes"] > tally["no"] and tally["yes"] > tally["maybe"]:
            ai_text = (
                f"All {member_count} members voted! **{destination}** won with "
                f"{tally['yes']} yes vote(s). Time to book — check the search link on the proposal!"
            )
        elif tally["yes"] == tally["no"]:
            ai_text = (
                f"It's a tie between yes ({tally['yes']}) and no ({tally['no']}) for "
                f"**{destination}**. Group, you decide — want to put this to another vote?"
            )
        else:
            ai_text = (
                f"All {member_count} members voted on **{destination}**: "
                f"👍 {tally['yes']} · 👎 {tally['no']} · 🤔 {tally['maybe']}."
            )

    add_message(trip_id, {"senderId": "ai", "text": ai_text, "type": "ai"})
    log_event("ai_reply", trip_id=trip_id, preview=ai_text[:80])

    # When multiple proposals exist, declare the cross-proposal winner once all are fully voted.
    if len(all_proposals) > 1:
        all_fully_voted = all(len(p.get("votes", {})) >= member_count for p in all_proposals)
        if all_fully_voted:
            _declare_winning_destination(trip_id, all_proposals, member_count)

    return {"ok": True, "votes": votes, "tally": tally}
