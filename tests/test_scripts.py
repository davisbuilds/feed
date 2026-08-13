"""Tests for provider-aware utility scripts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

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
