"""Tests for provider-aware utility scripts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_list_models_uses_openai_catalog_for_the_primary_provider(monkeypatch, capsys) -> None:
    """The model utility should list OpenAI models when OpenAI is selected."""
    module = _load_script("list_models")
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            llm_provider="openai",
            provider_api_key="test-key",
            llm_timeout=45,
        ),
    )

    openai_module = ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, api_key: str, timeout: float) -> None:
            self.api_key = api_key
            self.timeout = timeout
            self.models = SimpleNamespace(
                list=lambda: SimpleNamespace(
                    data=[SimpleNamespace(id="gpt-5.6-luna"), SimpleNamespace(id="gpt-5.6-terra")]
                )
            )

    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)

    assert module.main() == 0
    output = capsys.readouterr().out
    assert "gpt-5.6-luna" in output
    assert "gpt-5.6-terra" in output


def test_list_models_uses_gemini_beta_catalog_and_filters_by_action(monkeypatch, capsys) -> None:
    module = _load_script("list_models")
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(llm_provider="gemini", provider_api_key="test-key"),
    )

    models = [
        SimpleNamespace(name="models/generative", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/embedding", supported_actions=["embedContent"]),
        SimpleNamespace(name="models/unknown", supported_actions=None),
    ]
    client = Mock(return_value=SimpleNamespace(models=SimpleNamespace(list=lambda: models)))
    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    types_module = ModuleType("google.genai.types")
    genai_module.Client = client
    types_module.HttpOptions = lambda **kwargs: kwargs
    google_module.genai = genai_module
    genai_module.types = types_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)

    assert module.main() == 0
    client.assert_called_once_with(api_key="test-key", http_options={"api_version": "v1beta"})
    assert capsys.readouterr().out.splitlines() == ["Available models:", "- models/generative"]
