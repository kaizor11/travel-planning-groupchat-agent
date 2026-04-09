from config import (
    ACTIVE_LLM_PROVIDER,
    OLLAMA_MODEL_NAME,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_URL,
)
from .ollama import OllamaLLMProvider


def create_llm_provider(provider_name: str | None = None):
    selected_provider = (provider_name or ACTIVE_LLM_PROVIDER).strip().lower()

    if selected_provider == "ollama":
        return OllamaLLMProvider(
            base_url=OLLAMA_URL,
            model_name=OLLAMA_MODEL_NAME,
            timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
        )

    raise ValueError(f"Unsupported LLM provider: {selected_provider}")
