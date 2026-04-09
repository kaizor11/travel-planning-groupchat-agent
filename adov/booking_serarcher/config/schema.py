SUPPORTED_INTENTS = (
    "flight_search",
    "hotel_search",
    "unknown",
)


INTENT_SCHEMA = {
    "intent": None,
}


INTENT_PROMPT_RULES = (
    "Output exactly one valid JSON object.",
    f'intent must be one of: {", ".join(SUPPORTED_INTENTS)}.',
    'Use "flight_search" for flight, airfare, plane, airport, or round-trip travel requests.',
    'Use "hotel_search" for hotel, stay, lodging, accommodation, room, or check-in/check-out requests.',
    'Use "unknown" if the request is ambiguous or not clearly a flight or hotel search.',
)


ALLOWED_TRAVEL_CLASSES = (
    "economy",
    "premium_economy",
    "business",
    "first",
)


FLIGHT_SEARCH_SCHEMA = {
    "intent": "flight_search",
    "origin_city": None,
    "destination_city": None,
    "outbound_date": None,
    "return_date": None,
    "adults": 1,
    "travel_class": None,
    "sort_by": None,
}


HOTEL_SEARCH_SCHEMA = {
    "intent": "hotel_search",
    "location": None,
    "check_in_date": None,
    "check_out_date": None,
    "adults": 1,
    "rooms": 1,
    "min_star_rating": None,
    "max_price_per_night": None,
    "sort_by": None,
}


FLIGHT_EXTRACTION_PROMPT_RULES = (
    "Output exactly one valid JSON object.",
    "Dates must use YYYY-MM-DD.",
    "If the user does not specify a year, use the nearest possible future date after the current date.",
    "adults must be an integer.",
    f'travel_class must be one of: {", ".join(ALLOWED_TRAVEL_CLASSES)}.',
    'If the user asks for the cheapest option, set sort_by to "price".',
    "If a field cannot be determined, set it to null.",
)


HOTEL_EXTRACTION_PROMPT_RULES = (
    "Output exactly one valid JSON object.",
    "Dates must use YYYY-MM-DD.",
    "If the user does not specify a year, use the nearest possible future date after the current date.",
    "adults must be an integer.",
    "rooms must be an integer.",
    "min_star_rating should be a number if specified, otherwise null.",
    "max_price_per_night should be a number if specified, otherwise null.",
    'If the user asks for the cheapest option, set sort_by to "price".',
    "If a field cannot be determined, set it to null.",
)


EXTRACTION_SCHEMA = FLIGHT_SEARCH_SCHEMA
EXTRACTION_PROMPT_RULES = FLIGHT_EXTRACTION_PROMPT_RULES
