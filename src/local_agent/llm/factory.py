from local_agent.config import settings
from local_agent.llm.base import LLMProvider


def create_llm_provider(scaled_width: int, scaled_height: int) -> LLMProvider:
    """Create an LLM provider based on config."""
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        from local_agent.llm.anthropic import AnthropicProvider

        return AnthropicProvider(scaled_width, scaled_height)
    elif provider == "ollama":
        from local_agent.llm.ollama import OllamaProvider

        return OllamaProvider(scaled_width, scaled_height)
    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}. Supported: anthropic, ollama")
