import json

import requests

from config import INTENT_PROMPT_RULES, INTENT_SCHEMA, SUPPORTED_INTENTS

from .prompting import build_extraction_prompt, build_intent_detection_prompt


class OllamaLLMProvider:
    def __init__(self, base_url: str, model_name: str, timeout_seconds: int) -> None:
        self.base_url = base_url
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def extract_parameters(
        self,
        user_text: str,
        schema: dict,
        prompt_rules: tuple[str, ...],
        current_date: str,
        user_timezone: str,
    ) -> dict:
        prompt = build_extraction_prompt(
            user_text=user_text,
            schema=schema,
            prompt_rules=prompt_rules,
            current_date=current_date,
            user_timezone=user_timezone,
        )
        response_data = self._request_completion(prompt)
        return self._parse_response(response_data)

    def detect_intent(
        self,
        user_text: str,
        current_date: str,
        user_timezone: str,
    ) -> str:
        prompt = build_intent_detection_prompt(
            user_text=user_text,
            schema=INTENT_SCHEMA,
            prompt_rules=INTENT_PROMPT_RULES,
            current_date=current_date,
            user_timezone=user_timezone,
        )
        response_data = self._request_completion(prompt)
        parsed_response = self._parse_response(response_data)
        intent = parsed_response.get("intent")

        if intent in SUPPORTED_INTENTS:
            return intent

        return "unknown"

    def _request_completion(self, prompt: str) -> dict:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": False,
        }

        response = requests.post(
            self.base_url,
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response_data: dict) -> dict:
        content = response_data["message"]["content"]
        return json.loads(content)
