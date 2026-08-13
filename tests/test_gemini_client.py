"""Tests for the Gemini LLM client wrapper."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from feed.llm.base import LLMError


class _Schema(BaseModel):
    summary: str = ""


def _make_response(*, parsed=None, text="", usage=None):
    return SimpleNamespace(parsed=parsed, text=text, usage_metadata=usage)


@pytest.fixture
def gemini_module(monkeypatch):
    """Load the optional Gemini client against a minimal SDK fake."""
    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    types_module = ModuleType("google.genai.types")
    client_cls = MagicMock()

    genai_module.Client = client_cls
    types_module.GenerateContentConfig = lambda **kwargs: kwargs
    types_module.HttpOptions = lambda **kwargs: kwargs
    google_module.genai = genai_module
    genai_module.types = types_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)
    sys.modules.pop("feed.llm.gemini", None)

    return importlib.import_module("feed.llm.gemini"), client_cls


def test_gemini_generate_uses_parsed_basemodel(gemini_module):
    """Gemini normalizes parsed Pydantic output without the optional SDK installed."""
    module, mock_client_cls = gemini_module

    parsed = _Schema(summary="hello")
    usage = SimpleNamespace(prompt_token_count=42, candidates_token_count=7)
    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=parsed,
        text='{"summary":"hello"}',
        usage=usage,
    )
    mock_client_cls.return_value = mock_instance

    client = module.GeminiClient(api_key="k", model="gemini-test")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {"summary": "hello"}
    assert result.input_tokens == 42
    assert result.output_tokens == 7
    assert result.raw_text == '{"summary":"hello"}'


def test_gemini_generate_uses_parsed_dict(gemini_module):
    """Gemini preserves parsed dictionary output."""
    module, mock_client_cls = gemini_module

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed={"summary": "from-dict"},
        text="ignored",
        usage=None,
    )
    mock_client_cls.return_value = mock_instance

    client = module.GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {"summary": "from-dict"}
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_gemini_generate_falls_back_to_json_text(gemini_module):
    """Gemini parses JSON text when parsed output is absent."""
    module, mock_client_cls = gemini_module

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=None,
        text='{"summary":"json-fallback"}',
    )
    mock_client_cls.return_value = mock_instance

    client = module.GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {"summary": "json-fallback"}


def test_gemini_generate_empty_returns_empty_dict(gemini_module):
    """Gemini returns an empty object for an empty successful response."""
    module, mock_client_cls = gemini_module

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=None,
        text="",
    )
    mock_client_cls.return_value = mock_instance

    client = module.GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.parsed == {}
    assert result.raw_text == ""


def test_gemini_generate_invalid_json_raises_llm_error(gemini_module):
    """Gemini maps invalid JSON fallback output to the shared error type."""
    module, mock_client_cls = gemini_module

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed=None,
        text="not-json",
    )
    mock_client_cls.return_value = mock_instance

    client = module.GeminiClient(api_key="k", model="m")
    with pytest.raises(LLMError):
        client.generate(prompt="p", system="s", response_schema=_Schema)


def test_gemini_generate_partial_usage_counts(gemini_module):
    """Gemini treats missing usage dimensions as zero."""
    module, mock_client_cls = gemini_module

    usage = SimpleNamespace(prompt_token_count=None, candidates_token_count=5)
    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = _make_response(
        parsed={"summary": "x"},
        text="ignored",
        usage=usage,
    )
    mock_client_cls.return_value = mock_instance

    client = module.GeminiClient(api_key="k", model="m")
    result = client.generate(prompt="p", system="s", response_schema=_Schema)

    assert result.input_tokens == 0
    assert result.output_tokens == 5
