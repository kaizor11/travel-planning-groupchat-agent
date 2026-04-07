# Anthropic service: lazy Claude client initialization, JSON fence stripping, and travel content parsing.
import json
import os
import re

from anthropic import Anthropic
from prompts.agent import PARSE_CONTENT_SYSTEM_PROMPT

_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _strip_code_fences(raw: str) -> str:
    """Remove optional ```json ... ``` wrappers Claude sometimes adds."""
    return re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE).rstrip("` \n")


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
        model="claude-sonnet-4-6",
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
