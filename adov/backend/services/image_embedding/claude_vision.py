from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

from services.anthropic_client import get_client

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """\
You are a travel content analyzer. Given a screenshot or image, extract any travel-related information.
Respond ONLY with a valid JSON object — no markdown fences, no explanation.

Schema:
{
  "contentCategory": "travel_related" | "non_travel_text" | "non_travel_image" | "unknown",
  "summary": "<one or two sentence description of what this image shows>",
  "extractedText": "<all readable text in the image, or null if none>",
  "confidence": <0.0–1.0>,
  "travelSignals": {
    "locations": [{"value": "<city or place>", "confidence": <0.0–1.0>}],
    "dates": [{"value": "<date string>", "confidence": <0.0–1.0>}],
    "prices": [{"value": "<price string>", "confidence": <0.0–1.0>}],
    "lodging": [{"value": "<hotel/rental name>", "confidence": <0.0–1.0>}],
    "transport": [{"value": "<airline/train/etc>", "confidence": <0.0–1.0>}],
    "bookingSignals": [{"value": "<booking-related keyword>", "confidence": <0.0–1.0>}]
  }
}

If the image is not travel-related, still populate extractedText and set travelSignals arrays to [].
"""

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _strip_fences(raw: str) -> str:
    m = _CODE_FENCE_RE.search(raw)
    return m.group(1).strip() if m else raw.strip()


def analyze_image(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """Send image to Claude Haiku and return a normalized image_analysis dict."""
    encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
    client = get_client()

    response = client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": encoded,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Analyze this image and return the JSON.",
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text if response.content else ""
    try:
        result = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("[claude_vision] failed to parse response: %r", raw[:200])
        result = {}

    return _normalize(result)


def _normalize(r: dict[str, Any]) -> dict[str, Any]:
    signal_keys = ["locations", "dates", "prices", "lodging", "transport", "bookingSignals"]
    signals = r.get("travelSignals") or {}
    return {
        "processor": "claude_haiku",
        "contentCategory": r.get("contentCategory") or "unknown",
        "summary": r.get("summary") or None,
        "extractedText": r.get("extractedText") or None,
        "confidence": float(r["confidence"]) if r.get("confidence") is not None else None,
        "qualityScore": None,
        "travelSignals": {k: signals.get(k) or [] for k in signal_keys},
        "error": None,
    }
