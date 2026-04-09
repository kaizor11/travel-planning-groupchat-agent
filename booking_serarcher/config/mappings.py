CITY_TO_AIRPORT = {
    "los angeles": "LAX",
    "la": "LAX",
    "\u6d1b\u6749\u77f6": "LAX",
    "new york": "NYC",
    "nyc": "NYC",
    "\u7ebd\u7ea6": "NYC",
    "san francisco": "SFO",
    "sf": "SFO",
    "\u65e7\u91d1\u5c71": "SFO",
    "shanghai": "SHA",
    "\u4e0a\u6d77": "SHA",
    "beijing": "PEK",
    "\u5317\u4eac": "PEK",
}


AMBIGUOUS_CITY_AIRPORTS = {
    "new york": ("NYC", "JFK", "EWR", "LGA"),
    "nyc": ("NYC", "JFK", "EWR", "LGA"),
    "\u7ebd\u7ea6": ("NYC", "JFK", "EWR", "LGA"),
}


TRAVEL_CLASS_TO_SERPAPI = {
    "economy": 1,
    "premium_economy": 2,
    "business": 3,
    "first": 4,
}


SORT_BY_TO_SERPAPI = {
    "price": 2,
}


def get_airport_code(city_name: str | None) -> str | None:
    if not city_name:
        return None

    normalized = city_name.strip().lower()
    return CITY_TO_AIRPORT.get(normalized)


def get_airport_candidates(
    city_name: str | None,
    mapped_airport: str | None = None,
) -> list[str]:
    candidates = []

    def add_candidate(value: str | None) -> None:
        if value and value not in candidates:
            candidates.append(value)

    add_candidate(mapped_airport)

    lookup_values = []
    if city_name:
        lookup_values.append(city_name.strip().lower())
    if mapped_airport:
        lookup_values.append(mapped_airport.strip().lower())

    for lookup_value in lookup_values:
        for airport_code in AMBIGUOUS_CITY_AIRPORTS.get(lookup_value, ()):
            add_candidate(airport_code)

    return candidates
