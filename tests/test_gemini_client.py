"""Tests for the Gemini LLM client wrapper."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from src.llm.base import LLMError


class _Schema(BaseModel):
    summary: str = ""


def _make_response(*, parsed=None, text="", usage=None):
    return SimpleNamespace(parsed=parsed, text=text, usage_metadata=usage)


@patch("src.llm.gemini.genai.Client")
def test_gemini_generate_uses_parsed_basemodel(mock_client_cls):
    from src.llm.gemini import GeminiClient

    parsed = _Schema(summary="hello")
    usage = SimpleNamespace(prompt_token_count=42, candidates_token_count=7)
    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=parsed, text='{"summary":"hello"}', usage=usage,
    )
    mock_client_cls.return_value = mock_instance

    client = GeminiClient(api_key="k", model="gemini-test")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {"summary": "hello"}
    assert result.input_tokens == 42
    assert result.output_tokens == 7
    assert result.raw_text == '{"summary":"hello"}'


@patch("src.llm.gemini.genai.Client")
def test_gemini_generate_uses_parsed_dict(mock_client_cls):
    from src.llm.gemini import GeminiClient

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed={"summary": "from-dict"}, text="ignored", usage=None,
    )
    mock_client_cls.return_value = mock_instance

    client = GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {"summary": "from-dict"}
    assert result.input_tokens == 0
    assert result.output_tokens == 0


@patch("src.llm.gemini.genai.Client")
def test_gemini_generate_falls_back_to_json_text(mock_client_cls):
    from src.llm.gemini import GeminiClient

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=None, text='{"summary":"json-fallback"}',
    )
    mock_client_cls.return_value = mock_instance

    client = GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {"summary": "json-fallback"}


@patch("src.llm.gemini.genai.Client")
def test_gemini_generate_empty_returns_empty_dict(mock_client_cls):
    from src.llm.gemini import GeminiClient

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=None, text="",
    )
    mock_client_cls.return_value = mock_instance

    client = GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {}
    assert result.raw_text == ""


@patch("src.llm.gemini.genai.Client")
def test_gemini_generate_invalid_json_raises_llm_error(mock_client_cls):
    from src.llm.gemini import GeminiClient

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=None, text="not-json",
    )
    mock_client_cls.return_value = mock_instance

    client = GeminiClient(api_key="k", model="m")
    with pytest.raises(LLMError):
        client.generate(prompt="p", system="s", response_schema=_Schema)


@patch("src.llm.gemini.genai.Client")
def test_gemini_generate_partial_usage_counts(mock_client_cls):
    from src.llm.gemini import GeminiClient

    usage = SimpleNamespace(prompt_token_count=None, candidates_token_count=5)
    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed={"summary": "x"}, text="ignored", usage=usage,
    )
    mock_client_cls.return_value = mock_instance

    client = GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.input_tokens == 0
    assert result.output_tokens == 5
