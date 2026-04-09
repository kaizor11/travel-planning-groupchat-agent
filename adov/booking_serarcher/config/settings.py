import os


CURRENT_DATE = os.getenv("CURRENT_DATE", "2026-04-01")
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "America/Los_Angeles")

ACTIVE_LLM_PROVIDER = os.getenv("ACTIVE_LLM_PROVIDER", "ollama")
ACTIVE_TRAVEL_PROVIDER = os.getenv("ACTIVE_TRAVEL_PROVIDER") or (
    "serpapi" if os.getenv("SERPAPI_API_KEY") else "mock"
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "qwen2.5:7b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))

SERPAPI_URL = os.getenv("SERPAPI_URL", "https://serpapi.com/search.json")
SERPAPI_ENGINE = os.getenv("SERPAPI_ENGINE", "google_flights")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_TIMEOUT_SECONDS = int(os.getenv("SERPAPI_TIMEOUT_SECONDS", "120"))
SERPAPI_LANGUAGE = os.getenv("SERPAPI_LANGUAGE", "en")
SERPAPI_COUNTRY = os.getenv("SERPAPI_COUNTRY", "us")
SERPAPI_CURRENCY = os.getenv("SERPAPI_CURRENCY", "USD")
