"""Tests for CLI helper behavior."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import typer

from feed.models import Article, CategoryDigest, DailyDigest


def _sample_digest() -> DailyDigest:
    article = Article(
        id="cli-article",
        url="https://example.com/cli",
        title="CLI Article",
        feed_name="Example",
        feed_url="https://example.com/feed.xml",
        published=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
        summary="A concise summary.",
    )
    return DailyDigest(
        id="digest-cli",
        date=datetime(2026, 5, 13, 11, 0, tzinfo=UTC),
        categories=[
            CategoryDigest(
                name="Tools",
                article_count=1,
                articles=[article],
                synthesis="CLI helpers remain predictable.",
            )
        ],
        total_articles=1,
        total_feeds=1,
        must_read=["https://example.com/cli"],
    )


def test_version_callback_prints_version_and_exits(capsys) -> None:
    """The eager version callback should print the CLI version."""
    import feed.cli as cli

    with pytest.raises(typer.Exit):
        cli.version_callback(True)

    assert "Feed CLI v" in capsys.readouterr().out


def test_version_callback_ignores_false_value(capsys) -> None:
    """The version callback should be a no-op unless requested."""
    import feed.cli as cli

    assert cli.version_callback(False) is None
    assert capsys.readouterr().out == ""


def test_resolve_feeds_config_path_prefers_loaded_settings(monkeypatch, tmp_path) -> None:
    """Feed config path should come from resolved settings when available."""
    import feed.cli as cli

    config_dir = tmp_path / "xdg"
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(config_dir=config_dir))

    assert cli._resolve_feeds_config_path() == config_dir / "feeds.yaml"


def test_resolve_feeds_config_path_falls_back_to_project_config(monkeypatch, tmp_path) -> None:
    """Feed config path should fall back when full settings cannot be loaded."""
    import feed.cli as cli

    monkeypatch.setattr(cli, "get_settings", lambda: (_ for _ in ()).throw(RuntimeError("bad")))
    monkeypatch.setattr(cli, "XDG_CONFIG_PATH", tmp_path / "missing")

    assert cli._resolve_feeds_config_path() == cli.Path("config/feeds.yaml")


def test_copy_digest_to_clipboard_uses_xclip_when_available(monkeypatch) -> None:
    """Clipboard copy should use the Linux xclip fallback when pbcopy is unavailable."""
    import feed.cli as cli

    calls: list[tuple[list[str], bytes, bool]] = []

    def fake_which(command: str) -> str | None:
        return "/usr/bin/xclip" if command == "xclip" else None

    def fake_run(args: list[str], input: bytes, check: bool):
        calls.append((args, input, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli.shutil, "which", fake_which)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli._copy_digest_to_clipboard(_sample_digest()) is True
    assert calls[0][0] == ["/usr/bin/xclip", "-selection", "clipboard"]
    assert b"CLI Article" in calls[0][1]
    assert calls[0][2] is False


def test_copy_digest_to_clipboard_returns_false_without_tool(monkeypatch) -> None:
    """Clipboard copy should fail cleanly when no platform command exists."""
    import feed.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _command: None)

    assert cli._copy_digest_to_clipboard(_sample_digest()) is False


def test_print_digest_json_outputs_serialized_digest(capsys) -> None:
    """JSON output should serialize the digest model."""
    import feed.cli as cli

    cli._print_digest(_sample_digest(), "json")

    out = capsys.readouterr().out
    assert '"id": "digest-cli"' in out
    assert '"must_read": [' in out


def test_print_digest_text_uses_renderer(capsys) -> None:
    """Text output should use the email text renderer."""
    import feed.cli as cli

    cli._print_digest(_sample_digest(), "text")

    out = capsys.readouterr().out
    assert "CLI Article" in out
    assert "CLI helpers remain predictable." in out
