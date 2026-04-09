from config import (
    ACTIVE_TRAVEL_PROVIDER,
    SERPAPI_API_KEY,
    SERPAPI_COUNTRY,
    SERPAPI_CURRENCY,
    SERPAPI_ENGINE,
    SERPAPI_LANGUAGE,
    SERPAPI_TIMEOUT_SECONDS,
    SERPAPI_URL,
)
from .mock import MockTravelSearchProvider
from .serpapi import SerpApiTravelSearchProvider


def create_travel_provider(provider_name: str | None = None):
    selected_provider = (provider_name or ACTIVE_TRAVEL_PROVIDER).strip().lower()

    if selected_provider == "mock":
        return MockTravelSearchProvider()

    if selected_provider == "serpapi":
        return SerpApiTravelSearchProvider(
            base_url=SERPAPI_URL,
            engine=SERPAPI_ENGINE,
            api_key=SERPAPI_API_KEY,
            timeout_seconds=SERPAPI_TIMEOUT_SECONDS,
            language=SERPAPI_LANGUAGE,
            country=SERPAPI_COUNTRY,
            currency=SERPAPI_CURRENCY,
        )

    raise ValueError(f"Unsupported travel provider: {selected_provider}")
