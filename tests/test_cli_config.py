"""Exercise configuration diagnostics with synthetic credentials."""

import json

import pytest
from typer.testing import CliRunner

from feed import config
from feed.cli import app

OPENAI_KEY = "fixture-openai-credential"
GENERIC_KEY = "fixture-provider-credential"
RESEND_KEY = "fixture-resend-credential"


@pytest.fixture
def config_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("feed.cli.XDG_CONFIG_PATH", tmp_path)
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    monkeypatch.setattr(config, "_settings", None)
    for name in ("OPENAI_API_KEY", "LLM_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RESEND_API_KEY", RESEND_KEY)
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "feeds.yaml").write_text(
        "feeds:\n  Example:\n    url: https://example.com/feed.xml\n    category: Research\n"
    )
    return CliRunner()


@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
@pytest.mark.parametrize(
    ("provider", "credential_name"),
    [
        ("openai", "OPENAI_API_KEY"),
        ("openai", "LLM_API_KEY"),
        ("gemini", "GOOGLE_API_KEY"),
        ("anthropic", "LLM_API_KEY"),
    ],
)
def test_config_reports_credential_presence(
    config_cli, monkeypatch, provider, credential_name, as_json
):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    is_openai_key = credential_name == "OPENAI_API_KEY"
    credential = OPENAI_KEY if is_openai_key else GENERIC_KEY
    monkeypatch.setenv(credential_name, credential)

    result = config_cli.invoke(app, ["config", "--json"] if as_json else ["config"])

    assert result.exit_code == 0, result.output
    for value in (credential, RESEND_KEY):
        assert value not in result.output
        assert value[:10] not in result.output
    if as_json:
        data = json.loads(result.stdout)
        assert data["llm_provider"] == provider
        assert data["provider_api_key_configured"] is True
        assert data["openai_api_key_configured"] is is_openai_key
        assert data["llm_api_key_configured"] is not is_openai_key
        assert data["resend_api_key_configured"] is True
        assert not {"llm_api_key", "openai_api_key", "resend_api_key"} & data.keys()
        assert data["feed_count"] == 1
        assert data["feeds"]["Example"]["category"] == "Research"
    else:
        assert "LLM API key: configured" in result.stdout
        assert "Resend API key: configured" in result.stdout
        assert f"LLM provider: {provider}" in result.stdout
        assert "Feeds configured: 1" in result.stdout


@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
def test_config_errors_do_not_include_settings_input(config_cli, monkeypatch, as_json):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)

    result = config_cli.invoke(app, ["config", "--json"] if as_json else ["config"])

    assert result.exit_code == 1
    diagnostic = json.loads(result.stdout)["error"] if as_json else result.stdout
    assert "LLM_API_KEY is required for provider 'gemini'" in diagnostic
    assert "input_value" not in result.output
    for value in (OPENAI_KEY, RESEND_KEY):
        assert value not in result.output
        assert value[:10] not in result.output
