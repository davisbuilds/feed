"""LLM provider factory and shared exports."""

from typing import Literal

from .base import LLMClient, LLMError, LLMResponse

Provider = Literal["gemini", "openai", "anthropic"]

PROVIDER_DEFAULTS: dict[Provider, str] = {
    "gemini": "gemini-3-flash-preview",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


def create_client(provider: Provider, api_key: str, model: str | None = None) -> LLMClient:
    """Create an LLM client for the given provider."""
    resolved_model = model or PROVIDER_DEFAULTS[provider]

    match provider:
        case "gemini":
            from .gemini import GeminiClient

            return GeminiClient(api_key=api_key, model=resolved_model)
        case "openai":
            raise LLMError("OpenAI client is not implemented yet")
        case "anthropic":
            raise LLMError("Anthropic client is not implemented yet")
        case _:
            raise LLMError(f"Unknown LLM provider: {provider}")


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "PROVIDER_DEFAULTS",
    "Provider",
    "create_client",
]
