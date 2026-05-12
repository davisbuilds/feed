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
    """OpenAI responses should be parsed from message content with usage attached."""
    openai_module = ModuleType("openai")

    class FakeCompletions:
        def __init__(self) -> None:
            self.kwargs = {}

        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content='{"answer": "ok"}'))
                ],
                usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
            )

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.chat = SimpleNamespace(completions=FakeCompletions())

    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)
    module = _fresh_import("src.llm.openai")

    client = module.OpenAIClient(api_key="key-123", model="model-abc")
    response = client.generate("prompt", "system", Answer)

    assert response.parsed == {"answer": "ok"}
    assert response.raw_text == '{"answer": "ok"}'
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert client.client.api_key == "key-123"
    assert client.client.chat.completions.kwargs["model"] == "model-abc"
    assert client.client.chat.completions.kwargs["response_format"]["type"] == "json_schema"


def test_openai_text_extraction_accepts_parts_and_missing_message(monkeypatch) -> None:
    """OpenAI text extraction should support SDK text parts and empty choices."""
    openai_module = ModuleType("openai")
    openai_module.OpenAI = object
    monkeypatch.setitem(sys.modules, "openai", openai_module)
    module = _fresh_import("src.llm.openai")

    message = SimpleNamespace(
        content=[
            {"type": "text", "text": "first"},
            SimpleNamespace(text="second"),
            {"type": "image", "text": "ignored"},
        ]
    )

    assert module._extract_openai_text(message) == "first\nsecond"
    assert module._extract_openai_text(None) == ""
    assert module._extract_openai_text(SimpleNamespace(content=123)) == "123"


def test_openai_client_wraps_invalid_json(monkeypatch) -> None:
    """Invalid JSON provider responses should raise the shared LLMError."""
    openai_module = ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="{bad"))],
                        usage=None,
                    )
                )
            )

    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)
    module = _fresh_import("src.llm.openai")

    with pytest.raises(module.LLMError, match="OpenAI response parsing failed"):
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
    module = _fresh_import("src.llm.anthropic")

    client = module.AnthropicClient(api_key="key-abc", model="claude-test")
    response = client.generate("prompt", "system", Answer)

    assert response.parsed == {"answer": "anthropic"}
    assert response.raw_text == '{"answer": "anthropic"}'
    assert response.input_tokens == 13
    assert response.output_tokens == 5
    assert client.client.messages.kwargs["model"] == "claude-test"
    assert "Return valid JSON matching this schema exactly" in client.client.messages.kwargs[
        "messages"
    ][0]["content"]


def test_anthropic_text_extraction_accepts_objects_and_empty_blocks(monkeypatch) -> None:
    """Anthropic text extraction should join text blocks and ignore non-text blocks."""
    anthropic_module = ModuleType("anthropic")
    anthropic_module.Anthropic = object
    monkeypatch.setitem(sys.modules, "anthropic", anthropic_module)
    module = _fresh_import("src.llm.anthropic")

    blocks = [
        SimpleNamespace(type="text", text="first"),
        SimpleNamespace(type="tool_use", text="ignored"),
        {"type": "text", "text": "second"},
    ]

    assert module._extract_anthropic_text(blocks) == "first\nsecond"
    assert module._extract_anthropic_text([]) == ""
