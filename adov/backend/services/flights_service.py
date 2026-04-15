# Flights service: thin SerpAPI wrapper for Google Flights price lookups.
# Used during proposal generation to provide real flight cost estimates per member.
# Adapted from booking_searcher/travel/serpapi.py — kept minimal (no hotel search).
import os
import time

import requests

SERPAPI_URL = os.getenv("SERPAPI_URL", "https://serpapi.com/search.json")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_TIMEOUT = int(os.getenv("SERPAPI_TIMEOUT_SECONDS", "30"))

MAX_RETRIES = 2
RETRY_DELAY = 2

# Common city → airport code mappings (subset from booking_searcher/config/mappings.py)
CITY_TO_AIRPORT: dict[str, str] = {
    "los angeles": "LAX",
    "la": "LAX",
    "new york": "JFK",
    "nyc": "JFK",
    "new york city": "JFK",
    "san francisco": "SFO",
    "sf": "SFO",
    "chicago": "ORD",
    "miami": "MIA",
    "seattle": "SEA",
    "boston": "BOS",
    "dallas": "DFW",
    "houston": "IAH",
    "denver": "DEN",
    "atlanta": "ATL",
    "phoenix": "PHX",
    "las vegas": "LAS",
    "orlando": "MCO",
    "washington": "DCA",
    "dc": "IAD",
    "portland": "PDX",
    "minneapolis": "MSP",
    "detroit": "DTW",
    "philadelphia": "PHL",
    "san diego": "SAN",
    "london": "LHR",
    "paris": "CDG",
    "tokyo": "NRT",
    "osaka": "KIX",
    "seoul": "ICN",
    "beijing": "PEK",
    "shanghai": "PVG",
    "hong kong": "HKG",
    "singapore": "SIN",
    "bangkok": "BKK",
    "dubai": "DXB",
    "amsterdam": "AMS",
    "frankfurt": "FRA",
    "barcelona": "BCN",
    "madrid": "MAD",
    "rome": "FCO",
    "milan": "MXP",
    "zurich": "ZRH",
    "istanbul": "IST",
    "sydney": "SYD",
    "melbourne": "MEL",
    "toronto": "YYZ",
    "montreal": "YUL",
    "cancun": "CUN",
    "mexico city": "MEX",
    "sao paulo": "GRU",
    "buenos aires": "EZE",
    "bali": "DPS",
    "denpasar": "DPS",
    "phuket": "HKT",
    "hawaii": "HNL",
    "honolulu": "HNL",
    "lisbon": "LIS",
    "athens": "ATH",
    "munich": "MUC",
    "vienna": "VIE",
    "prague": "PRG",
    "budapest": "BUD",
    "stockholm": "ARN",
    "oslo": "OSL",
    "copenhagen": "CPH",
}


def _resolve_airport(location: str) -> str:
    """Resolve a city name or airport code to an IATA code."""
    if not location:
        return ""
    cleaned = location.strip()
    # If already a 3-letter code, return as-is
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    mapped = CITY_TO_AIRPORT.get(cleaned.lower())
    if mapped:
        return mapped
    # Return cleaned value and let SerpAPI try to handle it
    return cleaned


def get_cheapest_flight(
    origin: str,
    destination: str,
    outbound_date: str,
    adults: int = 1,
    return_date: str | None = None,
) -> int | None:
    """
    Query Google Flights via SerpAPI and return the cheapest round-trip price in USD.
    Returns None if SERPAPI_API_KEY is not set, the query fails, or no results are found.

    Args:
        origin: City name or IATA code (e.g. "Los Angeles" or "LAX")
        destination: City name or IATA code (e.g. "Bali" or "DPS")
        outbound_date: Departure date in YYYY-MM-DD format
        adults: Number of passengers (default 1)
        return_date: Return date in YYYY-MM-DD format (optional; improves price accuracy)

    Returns:
        Cheapest price as integer USD, or None if unavailable.
    """
    if not SERPAPI_API_KEY:
        return None

    dep = _resolve_airport(origin)
    arr = _resolve_airport(destination)
    if not dep or not arr:
        return None

    params: dict = {
        "engine": "google_flights",
        "api_key": SERPAPI_API_KEY,
        "departure_id": dep,
        "arrival_id": arr,
        "outbound_date": outbound_date,
        "adults": adults,
        "hl": "en",
        "gl": "us",
        "currency": "USD",
    }
    if return_date:
        params["return_date"] = return_date

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=SERPAPI_TIMEOUT)
            payload = resp.json()
        except Exception as exc:
            print(f"[flights_service] request error (attempt {attempt}): {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            continue

        if payload.get("error"):
            print(f"[flights_service] SerpAPI error: {payload['error']}")
            return None

        prices: list[int] = []
        for section in ("best_flights", "other_flights"):
            for option in payload.get(section, []):
                price = option.get("price")
                if isinstance(price, (int, float)) and price > 0:
                    prices.append(int(price))

        if prices:
            return min(prices)

        print(f"[flights_service] no flight results for {dep}→{arr} on {outbound_date}")
        return None

    return None
