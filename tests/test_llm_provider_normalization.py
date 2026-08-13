"""Tests for provider-specific response normalization."""

import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest
from pydantic import BaseModel


class Answer(BaseModel):
    answer: str


def _fresh_import(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_openai_client_generates_json_and_usage(monkeypatch) -> None:
    """OpenAI Responses output should preserve parsed content and usage."""
    openai_module = ModuleType("openai")

    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs = {}

        def parse(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                output_parsed=Answer(answer="ok"),
                output_text='{"answer": "ok"}',
                usage=SimpleNamespace(
                    input_tokens=11,
                    output_tokens=7,
                    output_tokens_details=SimpleNamespace(reasoning_tokens=3),
                ),
            )

    class FakeOpenAI:
        def __init__(self, api_key: str, timeout: float) -> None:
            self.api_key = api_key
            self.timeout = timeout
            self.responses = FakeResponses()

    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)
    module = _fresh_import("feed.llm.openai")

    client = module.OpenAIClient(
        api_key="key-123",
        model="gpt-5.6-luna",
        reasoning_effort="xhigh",
        timeout=45,
    )
    response = client.generate("prompt", "system", Answer)

    assert response.parsed == {"answer": "ok"}
    assert response.raw_text == '{"answer": "ok"}'
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert response.reasoning_tokens == 3
    assert client.client.api_key == "key-123"
    assert client.client.timeout == 45
    assert client.client.responses.kwargs["model"] == "gpt-5.6-luna"
    assert client.client.responses.kwargs["instructions"] == "system"
    assert client.client.responses.kwargs["input"] == "prompt"
    assert client.client.responses.kwargs["text_format"] is Answer
    assert client.client.responses.kwargs["reasoning"] == {"effort": "xhigh"}


def test_openai_client_wraps_invalid_json(monkeypatch) -> None:
    """Responses without parsed structured output raise the shared LLMError."""
    openai_module = ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, api_key: str, timeout: float = 120) -> None:
            self.responses = SimpleNamespace(
                parse=lambda **_kwargs: SimpleNamespace(
                    output_parsed=None,
                    output_text="",
                    usage=None,
                )
            )

    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)
    module = _fresh_import("feed.llm.openai")

    with pytest.raises(module.LLMError, match="OpenAI response did not contain structured output"):
        module.OpenAIClient(api_key="key", model="model").generate("prompt", "system", Answer)


def test_anthropic_client_generates_json_and_usage(monkeypatch) -> None:
    """Anthropic responses should be parsed from text blocks with usage attached."""
    anthropic_module = ModuleType("anthropic")

    class FakeMessages:
        def __init__(self) -> None:
            self.kwargs = {}

        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                content=[
                    {"type": "text", "text": '{"answer": "anthropic"}'},
                    {"type": "tool_use", "text": "ignored"},
                ],
                usage=SimpleNamespace(input_tokens=13, output_tokens=5),
            )

    class FakeAnthropic:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = FakeMessages()

    anthropic_module.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", anthropic_module)
    module = _fresh_import("feed.llm.anthropic")

    client = module.AnthropicClient(api_key="key-abc", model="claude-test")
    response = client.generate("prompt", "system", Answer)

    assert response.parsed == {"answer": "anthropic"}
    assert response.raw_text == '{"answer": "anthropic"}'
    assert response.input_tokens == 13
    assert response.output_tokens == 5
    assert client.client.messages.kwargs["model"] == "claude-test"
    assert (
        "Return valid JSON matching this schema exactly"
        in client.client.messages.kwargs["messages"][0]["content"]
    )


def test_anthropic_text_extraction_accepts_objects_and_empty_blocks(monkeypatch) -> None:
    """Anthropic text extraction should join text blocks and ignore non-text blocks."""
    anthropic_module = ModuleType("anthropic")
    anthropic_module.Anthropic = object
    monkeypatch.setitem(sys.modules, "anthropic", anthropic_module)
    module = _fresh_import("feed.llm.anthropic")

    blocks = [
        SimpleNamespace(type="text", text="first"),
        SimpleNamespace(type="tool_use", text="ignored"),
        {"type": "text", "text": "second"},
    ]

    assert module._extract_anthropic_text(blocks) == "first\nsecond"
    assert module._extract_anthropic_text([]) == ""
