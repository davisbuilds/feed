"""Exercise digest commands through Typer with an isolated SQLite database."""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
import resend
from typer.testing import CliRunner

from feed import config
from feed.analyze.digest_builder import OverallSynthesisResponse
from feed.analyze.summarizer import ArticleSummaryResponse
from feed.cli import app
from feed.llm.base import LLMResponse
from feed.llm.openai import OpenAIClient
from feed.models import Article, ArticleStatus, DailyDigest
from feed.storage.db import Database


@pytest.fixture
def digest_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-llm-key")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LOOKBACK_HOURS", "24")
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "reader@example.com")
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setitem(config.Settings.model_config, "env_file", ())
    monkeypatch.setattr(config, "_settings", None)
    monkeypatch.setattr(resend, "api_key", "test-resend-key")

    def generate(_client, _prompt, _system, response_schema):
        if response_schema is ArticleSummaryResponse:
            payload = {
                "summary": "Fixture article summary.",
                "key_takeaways": [],
                "action_items": [],
            }
        else:
            assert response_schema is OverallSynthesisResponse
            payload = {"overall_themes": ["Fixture digest theme"], "must_read_overall": []}
        return LLMResponse(parsed=payload, raw_text="{}", input_tokens=10, output_tokens=5)

    monkeypatch.setattr(OpenAIClient, "generate", generate)
    send_email = Mock(return_value={"id": "fixture-email"})
    monkeypatch.setattr(resend.Emails, "send", send_email)
    db = Database(tmp_path / "data" / "articles.db")
    return CliRunner(), db, send_email


def save_fixture_article(db, *, summarized=False, age_hours=0):
    article = Article(
        id="digest-fixture-article",
        url="https://example.com/article",
        title="Fixture digest article",
        feed_name="Fixture feed",
        feed_url="https://example.com/feed.xml",
        published=datetime.now(UTC) - timedelta(hours=age_hours),
        category="Testing",
        status=ArticleStatus.SUMMARIZED if summarized else ArticleStatus.PENDING,
        summary="Fixture article summary." if summarized else None,
    )
    assert db.save_article(article)


@pytest.mark.parametrize(
    ("command", "diagnostic"),
    [
        ("analyze", "No pending articles"),
        ("run", "No digest to output"),
        ("send", "No summarized articles"),
    ],
)
def test_empty_digest_json(digest_cli, command, diagnostic) -> None:
    runner, _db, send_email = digest_cli

    result = runner.invoke(app, [command, "--format", "json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert diagnostic in result.stderr
    send_email.assert_not_called()


@pytest.mark.parametrize("command", ["analyze", "run", "send"])
def test_populated_digest_json(digest_cli, command) -> None:
    runner, db, send_email = digest_cli
    save_fixture_article(db, summarized=command == "send")
    args = ["--test"] if command == "send" else []

    result = runner.invoke(app, [command, "--format", "json", *args])

    assert result.exit_code == 0, result.exception
    digest = DailyDigest.model_validate_json(result.stdout)
    assert digest.total_articles == digest.total_feeds == 1
    assert digest.overall_themes == ["Fixture digest theme"]
    assert digest.categories[0].name == "Testing"
    assert digest.categories[0].articles[0].summary == "Fixture article summary."
    send_email.assert_not_called()


@pytest.mark.parametrize("command", ["analyze", "run"])
def test_pending_articles_outside_lookback_produce_null(digest_cli, command) -> None:
    runner, db, _send_email = digest_cli
    save_fixture_article(db, age_hours=48)

    result = runner.invoke(app, [command, "--format", "json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None


@pytest.mark.parametrize("command", ["analyze", "run", "send"])
def test_digest_json_configuration_error_leaves_stdout_empty(
    digest_cli, monkeypatch, command
) -> None:
    runner, _db, _send_email = digest_cli
    monkeypatch.setenv("LOOKBACK_HOURS", "invalid")

    result = runner.invoke(app, [command, "--format", "json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Configuration error" in result.stderr


def test_invalid_feed_yaml_leaves_json_stdout_empty(digest_cli, tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "feeds.yaml").write_text("feeds: invalid\n")

    result = subprocess.run(
        [sys.executable, "-m", "feed.cli", "run", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Invalid feeds.yaml" in result.stderr


def test_send_delivers_rendered_digest(digest_cli) -> None:
    runner, db, send_email = digest_cli
    save_fixture_article(db, summarized=True)

    result = runner.invoke(app, ["send"])

    assert result.exit_code == 0, result.exception
    assert "Email sent successfully" in result.stdout
    send_email.assert_called_once()
    assert "Fixture digest article" in send_email.call_args.args[0]["html"]


@pytest.mark.parametrize("output_format", ["rich", "text"])
def test_send_previews_digest_in_the_requested_format(digest_cli, output_format) -> None:
    runner, db, send_email = digest_cli
    save_fixture_article(db, summarized=True)

    result = runner.invoke(app, ["send", "--format", output_format])

    assert result.exit_code == 0, result.exception
    assert "Preview of digest (1 articles)" in result.stdout
    assert "Fixture digest article" in result.stdout
    send_email.assert_not_called()


def test_analyze_json_copies_digest(digest_cli, tmp_path, monkeypatch, capfd) -> None:
    runner, db, _send_email = digest_cli
    save_fixture_article(db)
    clipboard_output = tmp_path / "clipboard.md"
    clipboard_tool = tmp_path / "pbcopy"
    clipboard_tool.write_text('#!/bin/sh\n/bin/cat > "$FEED_TEST_CLIPBOARD"\nprintf "copied\\n"\n')
    clipboard_tool.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("FEED_TEST_CLIPBOARD", str(clipboard_output))

    result = runner.invoke(app, ["analyze", "--copy", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert DailyDigest.model_validate_json(result.stdout).total_articles == 1
    assert "Fixture digest article" in clipboard_output.read_text()
    assert "Copied digest to clipboard" in result.stderr
    assert capfd.readouterr().out == ""


@pytest.mark.parametrize("send_fails", [False, True])
def test_run_digest_json_with_send(digest_cli, send_fails) -> None:
    runner, db, send_email = digest_cli
    save_fixture_article(db)
    if send_fails:
        send_email.side_effect = RuntimeError("fixture delivery failed")

    result = runner.invoke(app, ["run", "--send", "--format", "json"])

    send_email.assert_called_once()
    assert "Fixture digest article" in send_email.call_args.args[0]["text"]
    if send_fails:
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "Send failed: fixture delivery failed" in result.stderr
    else:
        assert result.exit_code == 0, result.output
        assert DailyDigest.model_validate_json(result.stdout).total_articles == 1
        assert "Email ID: fixture-email" in result.stderr
