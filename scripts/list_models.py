"""List available models for the configured LLM provider."""

from feed.config import get_settings


def main() -> int:
    """List models for provider if supported."""
    settings = get_settings()

    if settings.llm_provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as exc:
            print(f"OpenAI SDK is unavailable: {exc}")
            return 1

        client = OpenAI(api_key=settings.provider_api_key, timeout=settings.llm_timeout)
        print("Available models:")
        for model in client.models.list().data:
            print(f"- {model.id}")
        return 0

    if settings.llm_provider == "anthropic":
        print(
            "Model listing is not implemented for anthropic; "
            "use the Anthropic Console to inspect available models."
        )
        return 1

    try:
        from google import genai
    except ImportError as exc:
        print(
            "Gemini model listing requires the gemini dependency. "
            "Install it with: uv sync --extra gemini"
        )
        print(f"Import error: {exc}")
        return 1

    client = genai.Client(api_key=settings.provider_api_key)
    print("Available models:")
    for model in client.models.list():
        if "generateContent" in model.supported_generation_methods:
            print(f"- {model.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
