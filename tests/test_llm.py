"""Tests for LLM factory behavior."""

from types import ModuleType

import pytest

from feed.llm import LLMError, create_client
from feed.llm.retry import RetryClient


class _DummyClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        reasoning_effort: str = "xhigh",
        timeout: float = 120,
    ):
        self.api_key = api_key
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout


def test_create_client_openai_uses_provider_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should pass provider default model when model is omitted."""
    module = ModuleType("feed.llm.openai")
    module.OpenAIClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "feed.llm.openai", module)

    client = create_client(provider="openai", api_key="test-key")

    assert isinstance(client, RetryClient)
    assert isinstance(client.inner, _DummyClient)
    assert client.inner.api_key == "test-key"
    assert client.inner.model == "gpt-5.6-luna"
    assert client.inner.reasoning_effort == "xhigh"
    assert client.inner.timeout == 120


def test_create_client_anthropic_uses_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should preserve explicitly passed model."""
    module = ModuleType("feed.llm.anthropic")
    module.AnthropicClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "feed.llm.anthropic", module)

    client = create_client(provider="anthropic", api_key="test-key", model="claude-custom")

    assert isinstance(client, RetryClient)
    assert client.inner.model == "claude-custom"


def test_create_client_missing_dependency_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should wrap dependency import errors as LLMError."""
    monkeypatch.setitem(__import__("sys").modules, "feed.llm.openai", None)

    with pytest.raises(LLMError):
        create_client(provider="openai", api_key="test-key")


def test_create_client_passes_openai_reasoning_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI receives its configured reasoning effort and request timeout."""
    module = ModuleType("feed.llm.openai")
    module.OpenAIClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "feed.llm.openai", module)

    client = create_client(
        provider="openai",
        api_key="test-key",
        reasoning_effort="high",
        timeout=45,
    )

    assert isinstance(client.inner, _DummyClient)
    assert client.inner.reasoning_effort == "high"
    assert client.inner.timeout == 45


def test_create_client_unknown_provider_raises_llm_error() -> None:
    """Factory should reject unsupported provider strings."""
    with pytest.raises(LLMError):
        create_client(provider="unknown", api_key="test-key")  # type: ignore[arg-type]


def test_create_client_wraps_with_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should wrap provider client with RetryClient."""
    module = ModuleType("feed.llm.gemini")
    module.GeminiClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "feed.llm.gemini", module)

    client = create_client(provider="gemini", api_key="test-key")

    assert isinstance(client, RetryClient)
    assert isinstance(client.inner, _DummyClient)


def test_create_client_passes_retry_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should pass max_retries to RetryClient."""
    module = ModuleType("feed.llm.gemini")
    module.GeminiClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "feed.llm.gemini", module)

    client = create_client(provider="gemini", api_key="test-key", max_retries=5)

    assert isinstance(client, RetryClient)
    assert client.max_retries == 5
