# Anthropic service: lazy Claude client initialization, JSON fence stripping, and travel content parsing.
import datetime
import json
import os
import re

from anthropic import Anthropic
from prompts.agent import AGENT_CONTEXT, PARSE_CONTENT_SYSTEM_PROMPT, PREFERENCE_EXTRACTION_PROMPT, PROPOSAL_GENERATION_PROMPT

# Central model constant — override via ANTHROPIC_MODEL env var to switch models without code changes
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_client: Anthropic | None = None


def _json_default(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _strip_code_fences(raw: str) -> str:
    """Remove optional ```json ... ``` wrappers Claude sometimes adds."""
    return re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE).rstrip("` \n")


def get_chat_response(
    messages_context: list[dict],
    sender_name: str,
    members: list[dict] | None = None,
    extra_context: str = "",
) -> str:
    """
    Generate a conversational reply to an @adov mention.
    messages_context: recent messages ordered oldest-first, each with senderId/senderName/text/type.
    members: list of {name, calendarConnected} for each human trip member (optional).
    Returns the AI reply text.
    """
    # Build alternating-role turns from chat history
    raw_turns: list[dict] = []
    for msg in messages_context:
        if msg.get("senderId") == "ai":
            raw_turns.append({"role": "assistant", "content": msg.get("text", "")})
        else:
            name = msg.get("senderName") or msg.get("senderId", "User")
            raw_turns.append({"role": "user", "content": f"[{name}]: {msg.get('text', '')}"})

    # Merge consecutive same-role turns (Claude requires strict alternation)
    merged: list[dict] = []
    for turn in raw_turns:
        if merged and merged[-1]["role"] == turn["role"]:
            merged[-1]["content"] += "\n" + turn["content"]
        else:
            merged.append(dict(turn))

    # Ensure the last turn is from the user (required by Claude)
    if not merged or merged[-1]["role"] != "user":
        merged.append({"role": "user", "content": f"[{sender_name}] mentioned you."})

    # Inject ground-truth member calendar status so Claude never guesses
    system = AGENT_CONTEXT
    injections: list[str] = []
    if members:
        connected = [m["name"] for m in members if m["calendarConnected"]]
        not_connected = [m["name"] for m in members if not m["calendarConnected"]]
        injections.append("\n\n[MEMBER CALENDAR STATUS — treat this as ground truth, never guess or infer differently:]")
        if connected:
            injections.append(f"Calendar connected: {', '.join(connected)}")
        if not_connected:
            injections.append(f"Calendar not connected: {', '.join(not_connected)}")
        injections.append(
            "You are the AI assistant (adov). You are not a trip member and do not have a calendar. "
            "Never ask yourself to connect a calendar."
        )
    if extra_context:
        injections.append(extra_context)
    if injections:
        system = AGENT_CONTEXT + "\n".join(injections)

    message = get_client().messages.create(
        model=MODEL,
        max_tokens=500,
        system=system,
        messages=merged,
    )
    return message.content[0].text.strip() if message.content else ""


def extract_preference(text: str) -> dict | None:
    """
    Lightweight call to extract a single preference from user text.
    Returns a dict with type/item/sentiment, or None if no clear preference found.
    """
    message = get_client().messages.create(
        model=MODEL,
        max_tokens=150,
        system=PREFERENCE_EXTRACTION_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    raw = message.content[0].text.strip() if message.content else "null"
    if raw.lower() == "null":
        return None
    cleaned = _strip_code_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def generate_trip_proposals(
    aggregated_destinations: list[dict],
    windows: list[dict],
    budget: dict,
    member_count: int,
    flight_estimates: dict[str, int | None] | None = None,
) -> list[dict]:
    """
    Generate one structured trip proposal per aggregated destination.

    Args:
        aggregated_destinations: Pre-filtered, vote-ranked list of
            [{destination, entries, total_votes}, ...] (max 5, strict-majority accepted)
        windows: Available calendar windows [{start, end}, ...]
        budget: Group budget {group_min, group_max, members_with_budget}
        member_count: Total number of trip members
        flight_estimates: Optional map of destination → cheapest flight price in USD

    Returns:
        List of proposal dicts (one per destination), or raises ValueError on unparseable output.
    """
    context = {
        "destinations": aggregated_destinations,
        "availableWindows": windows,
        "groupBudget": budget,
        "memberCount": member_count,
        "flightEstimates": flight_estimates or {},
    }
    user_content = f"Group travel context:\n{json.dumps(context, ensure_ascii=False, indent=2, default=_json_default)}"

    message = get_client().messages.create(
        model=MODEL,
        max_tokens=2000,
        system=AGENT_CONTEXT + PROPOSAL_GENERATION_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = message.content[0].text if message.content else ""
    cleaned = _strip_code_fences(raw_text)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON proposals: {raw_text!r}") from exc

    if not isinstance(result, list):
        raise ValueError(f"Claude returned unexpected proposals shape: {raw_text!r}")

    return result


def parse_travel_content(url: str | None, text: str | None) -> dict:
    """
    Call Claude to extract travel intent from a URL and/or caption text.
    Returns a dict with keys: destination, tags, estimatedCost (optional), confidence.
    Raises ValueError if Claude returns unparseable JSON.
    """
    parts = []
    if url:
        parts.append(f"URL: {url}")
    if text:
        parts.append(f"Caption / text: {text}")
    user_content = "\n".join(parts)

    message = get_client().messages.create(
        model=MODEL,
        max_tokens=1000,
        system=PARSE_CONTENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = message.content[0].text if message.content else ""
    cleaned = _strip_code_fences(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON: {raw_text!r}") from exc

    return parsed
