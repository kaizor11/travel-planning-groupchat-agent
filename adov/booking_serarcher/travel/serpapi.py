import json
import time

import requests

from config.mappings import get_airport_candidates, get_airport_code


NO_RESULTS_ERROR_TEXT = "Google Flights hasn't returned any results for this query."
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


class SerpApiTravelSearchProvider:
    def __init__(
        self,
        base_url: str,
        engine: str,
        api_key: str | None,
        timeout_seconds: int,
        language: str,
        country: str,
        currency: str,
    ) -> None:
        self.base_url = base_url
        self.engine = engine
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.language = language
        self.country = country
        self.currency = currency

    def search_flights(self, structured_data: dict) -> dict:
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is not set.")

        search_plan = self._build_search_plan(structured_data)
        last_error_message = "SerpApi Google Flights request failed."

        for candidate_index, candidate in enumerate(search_plan, start=1):
            candidate_label = self._format_candidate_label(candidate)

            for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
                params = self._build_search_params(structured_data, candidate)
                self._print_request_debug(
                    params=params,
                    candidate_label=candidate_label,
                    candidate_index=candidate_index,
                    total_candidates=len(search_plan),
                    attempt=attempt,
                )

                response = requests.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                payload = self._parse_payload(response)

                if payload.get("error"):
                    error_message = str(payload["error"])
                    flights_results_state = self._get_flights_results_state(payload)
                    last_error_message = error_message

                    self._print_error_debug(
                        params=params,
                        status_code=response.status_code,
                        payload=payload,
                        candidate_label=candidate_label,
                    )

                    if (
                        self._is_empty_results_error(error_message, flights_results_state)
                        and candidate_index < len(search_plan)
                    ):
                        print(
                            "Trying the next airport candidate because this route "
                            "returned an empty Google Flights result."
                        )
                        break

                    if attempt < MAX_RETRY_ATTEMPTS:
                        print(
                            f"Retrying SerpApi request in {RETRY_DELAY_SECONDS} seconds "
                            f"for candidate {candidate_label}."
                        )
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue

                    raise RuntimeError(
                        "SerpApi Google Flights request failed after "
                        f"{attempt} attempt(s) for {candidate_label}: {error_message}"
                    )

                response.raise_for_status()

                return {
                    "status": payload.get("search_metadata", {}).get(
                        "status", "success"
                    ).lower(),
                    "used_params": structured_data,
                    "results": self._parse_flights(payload),
                    "price_insights": payload.get("price_insights"),
                }

        raise RuntimeError(
            "SerpApi Google Flights request failed after exhausting airport "
            f"fallbacks: {last_error_message}"
        )

    def search_hotels(self, structured_data: dict) -> dict:
        print(
            "SerpApi hotel search is not implemented in this prototype yet. "
            "Returning a mock hotel response."
        )
        return {
            "status": "success",
            "provider_mode": "mock",
            "used_params": structured_data,
            "note": "Hotel search is currently mocked for the SerpApi provider.",
            "results": [
                {"hotel": "Example Hotel A", "price_per_night": 180, "star_rating": 4},
                {"hotel": "Example Hotel B", "price_per_night": 245, "star_rating": 5},
            ],
        }

    def _build_search_plan(self, structured_data: dict) -> list[dict]:
        origin = self._resolve_location(structured_data.get("origin_city"))
        destination = self._resolve_location(structured_data.get("destination_city"))
        outbound_date = structured_data.get("outbound_date")

        if not origin or not destination or not outbound_date:
            raise ValueError(
                "SerpApi travel provider requires origin_city, destination_city, and outbound_date."
            )

        origin_candidates = get_airport_candidates(
            structured_data.get("origin_city"),
            origin,
        ) or [origin]
        destination_candidates = get_airport_candidates(
            structured_data.get("destination_city"),
            destination,
        ) or [destination]

        search_plan = []
        seen_pairs = set()

        for origin_candidate in origin_candidates:
            for destination_candidate in destination_candidates:
                pair = (origin_candidate, destination_candidate)
                if pair in seen_pairs:
                    continue

                seen_pairs.add(pair)
                search_plan.append(
                    {
                        "departure_id": origin_candidate,
                        "arrival_id": destination_candidate,
                    }
                )

        return search_plan

    def _build_search_params(self, structured_data: dict, candidate: dict) -> dict:
        outbound_date = structured_data.get("outbound_date")
        return_date = structured_data.get("return_date")
        adults = self._normalize_adults(structured_data.get("adults"))

        params = {
            "engine": self.engine,
            "api_key": self.api_key,
            "departure_id": candidate["departure_id"],
            "arrival_id": candidate["arrival_id"],
            "outbound_date": outbound_date,
            "return_date": return_date,
            "adults": adults,
            "hl": self.language,
            "gl": self.country,
            "currency": self.currency,
        }

        return {key: value for key, value in params.items() if value is not None}

    def _print_request_debug(
        self,
        params: dict,
        candidate_label: str,
        candidate_index: int,
        total_candidates: int,
        attempt: int,
    ) -> None:
        print(
            f"SerpApi request candidate {candidate_index}/{total_candidates}, "
            f"attempt {attempt}/{MAX_RETRY_ATTEMPTS}: {candidate_label}"
        )
        print(json.dumps(self._mask_secrets(params), ensure_ascii=False, indent=2))

    def _normalize_adults(self, adults_value) -> int | None:
        if adults_value in (None, ""):
            return None

        try:
            adults = int(adults_value)
        except (TypeError, ValueError):
            return None

        return adults if adults > 0 else None

    def _parse_payload(self, response: requests.Response) -> dict:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                "SerpApi returned a non-JSON response with "
                f"HTTP status code {response.status_code}."
            ) from exc

    def _is_empty_results_error(
        self,
        error_message: str,
        flights_results_state: str | None,
    ) -> bool:
        return NO_RESULTS_ERROR_TEXT in error_message or flights_results_state == "Fully empty"

    def _print_error_debug(
        self,
        params: dict,
        status_code: int,
        payload: dict,
        candidate_label: str,
    ) -> None:
        metadata = {
            key: payload[key]
            for key in (
                "search_metadata",
                "search_parameters",
                "search_information",
                "error",
            )
            if key in payload
        }
        flights_results_state = self._get_flights_results_state(payload)

        print("SerpApi returned an error response.")
        print(f"Current airport candidate: {candidate_label}")
        print("Request params:")
        print(json.dumps(self._mask_secrets(params), ensure_ascii=False, indent=2))
        print(f"HTTP status code: {status_code}")
        print(f"Raw error message: {payload.get('error')}")
        if flights_results_state:
            print(f"Flights results state: {flights_results_state}")
        if metadata:
            print("Top-level metadata:")
            print(
                json.dumps(
                    self._mask_secrets(metadata),
                    ensure_ascii=False,
                    indent=2,
                )
            )

    def _get_flights_results_state(self, payload: dict) -> str | None:
        if payload.get("flights_results_state"):
            return payload["flights_results_state"]

        search_information = payload.get("search_information") or {}
        return search_information.get("flights_results_state")

    def _mask_secrets(self, value):
        if isinstance(value, dict):
            return {
                key: (
                    "***masked***"
                    if key.lower() == "api_key"
                    else self._mask_secrets(item)
                )
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [self._mask_secrets(item) for item in value]

        return value

    def _format_candidate_label(self, candidate: dict) -> str:
        return (
            f"departure_id={candidate['departure_id']}, "
            f"arrival_id={candidate['arrival_id']}"
        )

    def _resolve_location(self, city_name: str | None) -> str | None:
        mapped_airport = get_airport_code(city_name)
        if mapped_airport:
            return mapped_airport

        if not city_name:
            return None

        cleaned_value = city_name.strip()
        if len(cleaned_value) == 3 and cleaned_value.isalpha():
            return cleaned_value.upper()

        return cleaned_value

    def _parse_flights(self, payload: dict) -> list[dict]:
        parsed_results = []

        for section_name in ("best_flights", "other_flights"):
            for option in payload.get(section_name, []):
                parsed_results.append(self._parse_option(option))

        return parsed_results

    def _parse_option(self, option: dict) -> dict:
        flight_segments = option.get("flights", [])
        airline_names = [
            segment.get("airline")
            for segment in flight_segments
            if segment.get("airline")
        ]
        departure_airport = (
            flight_segments[0].get("departure_airport", {})
            if flight_segments
            else {}
        )
        arrival_airport = (
            flight_segments[-1].get("arrival_airport", {})
            if flight_segments
            else {}
        )

        return {
            "flight": " / ".join(dict.fromkeys(airline_names)) or "Unknown airline",
            "price": option.get("price"),
            "departure_airport": departure_airport.get("id")
            or departure_airport.get("name"),
            "arrival_airport": arrival_airport.get("id")
            or arrival_airport.get("name"),
            "total_duration": option.get("total_duration"),
            "stops": max(len(flight_segments) - 1, 0),
        }
