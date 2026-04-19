from __future__ import annotations

import base64
import importlib
import json
from typing import Any

from . import normalize_image_analysis
from .config_loader import ImageEmbeddingConfig


class RemoteEmbedderError(RuntimeError):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


def _categorize_openai_error(exc: Exception) -> RemoteEmbedderError:
    exc_name = type(exc).__name__.lower()
    status_code = getattr(exc, "status_code", None)
    message = str(exc)

    if status_code in (401, 403) or "auth" in exc_name:
        return RemoteEmbedderError("auth", message)
    if status_code == 429 or "rate" in exc_name:
        return RemoteEmbedderError("rate_limit", message)
    if "timeout" in exc_name:
        return RemoteEmbedderError("timeout", message)
    if any(token in exc_name for token in ("connection", "network", "apierror", "apiconnection")):
        return RemoteEmbedderError("network_failure", message)
    return RemoteEmbedderError("invalid_response", message)


def analyze_image(
    image_bytes: bytes,
    mime_type: str,
    config: ImageEmbeddingConfig,
) -> dict[str, Any]:
    openai_module = importlib.import_module("openai")
    openai_client_cls = getattr(openai_module, "OpenAI")

    client_kwargs: dict[str, Any] = {"api_key": config.openai_api_key}
    if config.remote.base_url:
        client_kwargs["base_url"] = config.remote.base_url

    client = openai_client_cls(**client_kwargs)
    data_url = "data:{mime};base64,{payload}".format(
        mime=mime_type,
        payload=base64.b64encode(image_bytes).decode("ascii"),
    )

    try:
        response = client.chat.completions.create(
            model=config.remote.model,
            temperature=0,
            max_tokens=config.remote.max_output_tokens,
            timeout=config.remote.timeout_seconds,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": config.remote.prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
    except Exception as exc:
        raise _categorize_openai_error(exc) from exc

    try:
        raw_text = response.choices[0].message.content or ""
    except (AttributeError, IndexError) as exc:
        raise RemoteEmbedderError("invalid_response", "OpenAI returned no content") from exc

    if isinstance(raw_text, list):
        raw_text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw_text
        )

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RemoteEmbedderError("invalid_response", "OpenAI returned invalid JSON") from exc

    normalized = normalize_image_analysis(payload, processor="openai_vision")
    expected_keys = {
        "processor",
        "contentCategory",
        "summary",
        "extractedText",
        "confidence",
        "qualityScore",
        "travelSignals",
        "error",
    }
    if set(normalized.keys()) != expected_keys:
        raise RemoteEmbedderError("invalid_response", "OpenAI returned an unexpected schema")

    return normalized
