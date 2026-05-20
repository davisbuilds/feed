"""Additional tests covering scheduler helpers and edge paths."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.scheduler import (
    SchedulePlan,
    _read_crontab,
    bootstrap_launchd,
    build_cron_schedule,
    build_job_shell_command,
    build_launchd_path,
    build_launchd_plist,
    build_plan,
    cron_marker_end,
    cron_marker_start,
    default_day_of_week,
    default_lookback_hours,
    get_cron_managed_block,
    install_cron,
    launchd_domain_and_service,
    launchd_plist_path,
    normalize_day_of_week,
    resolve_backend,
    resolve_log_path,
    resolve_runner,
    write_launchd_plist,
)


def _plan(tmp_path: Path, **overrides) -> SchedulePlan:
    defaults = dict(
        backend="cron",
        frequency="weekly",
        day_of_week="fri",
        time_str="17:00",
        lookback_hours=168,
        project_root=tmp_path,
        runner_override="uv run feed",
        log_file=Path("logs/cron.log"),
        label="com.user.feed",
        launch_agents_dir=tmp_path / "LaunchAgents",
    )
    defaults.update(overrides)
    return build_plan(**defaults)


def test_normalize_day_of_week_accepts_long_names():
    assert normalize_day_of_week("Monday") == "mon"
    assert normalize_day_of_week("THURSDAY") == "thu"


def test_normalize_day_of_week_invalid_raises():
    with pytest.raises(ValueError):
        normalize_day_of_week("funday")


def test_resolve_backend_explicit():
    assert resolve_backend("cron") == "cron"
    assert resolve_backend("launchd") == "launchd"


def test_resolve_backend_auto_uses_platform(monkeypatch):
    monkeypatch.setattr("src.scheduler.sys.platform", "darwin")
    assert resolve_backend("auto") == "launchd"
    monkeypatch.setattr("src.scheduler.sys.platform", "linux")
    assert resolve_backend("auto") == "cron"


def test_resolve_backend_invalid_raises():
    with pytest.raises(ValueError):
        resolve_backend("podman")


def test_default_day_and_lookback():
    assert default_day_of_week("daily") is None
    assert default_day_of_week("weekly") == "fri"
    assert default_lookback_hours("daily") == 24
    assert default_lookback_hours("weekly") == 168


def test_resolve_runner_without_wrapper_uses_uv(tmp_path):
    assert resolve_runner(tmp_path, None) == "uv run feed"


def test_resolve_runner_with_wrapper_uses_local(tmp_path):
    (tmp_path / "feed").write_text("#!/usr/bin/env bash\n")
    assert resolve_runner(tmp_path, None) == "./feed"


def test_resolve_runner_quotes_override(tmp_path):
    assert resolve_runner(tmp_path, "myrunner --flag value") == "myrunner --flag value"


def test_resolve_log_path_absolute_returned_directly(tmp_path):
    abs_path = tmp_path / "logs" / "x.log"
    assert resolve_log_path(tmp_path, abs_path) == abs_path


def test_resolve_log_path_relative_joined_to_root(tmp_path):
    rel = Path("logs/x.log")
    assert resolve_log_path(tmp_path, rel) == tmp_path / "logs" / "x.log"


def test_build_plan_daily_with_day_of_week_raises(tmp_path):
    with pytest.raises(ValueError):
        _plan(tmp_path, frequency="daily", day_of_week="mon")


def test_build_plan_invalid_frequency(tmp_path):
    with pytest.raises(ValueError):
        _plan(tmp_path, frequency="monthly")


def test_build_plan_bad_lookback(tmp_path):
    with pytest.raises(ValueError):
        _plan(tmp_path, lookback_hours=0)


def test_build_plan_empty_label(tmp_path):
    with pytest.raises(ValueError):
        _plan(tmp_path, label="   ")


def test_build_cron_schedule_daily(tmp_path):
    plan = _plan(tmp_path, frequency="daily", day_of_week=None)
    assert build_cron_schedule(plan) == "0 17 * * *"


def test_build_cron_schedule_weekly(tmp_path):
    plan = _plan(tmp_path)
    assert build_cron_schedule(plan) == "0 17 * * 5"


def test_build_job_shell_command_no_redirect(tmp_path):
    plan = _plan(tmp_path)
    cmd = build_job_shell_command(plan, redirect_to_log=False)
    assert "LOOKBACK_HOURS=168" in cmd
    assert ">>" not in cmd


def test_build_job_shell_command_with_redirect(tmp_path):
    plan = _plan(tmp_path)
    cmd = build_job_shell_command(plan, redirect_to_log=True)
    assert ">>" in cmd
    assert "2>&1" in cmd


def test_build_launchd_plist_daily_omits_weekday(tmp_path):
    plan = _plan(tmp_path, frequency="daily", day_of_week=None)
    payload = build_launchd_plist(plan)
    interval = payload["StartCalendarInterval"]
    assert "Weekday" not in interval


def test_build_launchd_path_includes_expected_entries():
    path = build_launchd_path()
    entries = path.split(":")
    assert "/usr/bin" in entries
    assert "/bin" in entries
    # No duplicates
    assert len(entries) == len(set(entries))


def test_launchd_plist_path(tmp_path):
    plan = _plan(tmp_path)
    expected = (tmp_path / "LaunchAgents" / "com.user.feed.plist")
    assert launchd_plist_path(plan) == expected


def test_cron_markers_unique_per_label():
    assert cron_marker_start("a") != cron_marker_start("b")
    assert cron_marker_end("a") != cron_marker_end("b")
    assert "a" in cron_marker_start("a")


def test_get_cron_managed_block_returns_none_when_partial(monkeypatch):
    monkeypatch.setattr(
        "src.scheduler._read_crontab",
        lambda: "# >>> feed schedule (only-start) >>>\n0 8 * * * echo hi\n",
    )
    assert get_cron_managed_block("only-start") is None


def test_get_cron_managed_block_malformed_order_raises(monkeypatch):
    bad = (
        "# <<< feed schedule (lbl) <<<\n"
        "echo wrong-order\n"
        "# >>> feed schedule (lbl) >>>\n"
    )
    monkeypatch.setattr("src.scheduler._read_crontab", lambda: bad)
    with pytest.raises(RuntimeError):
        get_cron_managed_block("lbl")


def test_install_cron_appends_when_missing(tmp_path, monkeypatch):
    plan = _plan(tmp_path)
    monkeypatch.setattr("src.scheduler._read_crontab", lambda: "")
    written = {}

    def _w(content: str) -> None:
        written["content"] = content

    monkeypatch.setattr("src.scheduler._write_crontab", _w)
    install_cron(plan)

    assert ">>> feed schedule (com.user.feed) >>>" in written["content"]


def test_install_cron_replaces_when_existing(tmp_path, monkeypatch):
    plan = _plan(tmp_path)
    existing = (
        "# header line\n"
        "# >>> feed schedule (com.user.feed) >>>\n"
        "OLD CRON ENTRY\n"
        "# <<< feed schedule (com.user.feed) <<<\n"
    )
    monkeypatch.setattr("src.scheduler._read_crontab", lambda: existing)
    written = {}

    def _w(content: str) -> None:
        written["content"] = content

    monkeypatch.setattr("src.scheduler._write_crontab", _w)
    install_cron(plan, replace_existing=True)

    assert "OLD CRON ENTRY" not in written["content"]
    assert "# header line" in written["content"]
    assert "LOOKBACK_HOURS=168" in written["content"]


def test_install_cron_refuses_without_replace(tmp_path, monkeypatch):
    plan = _plan(tmp_path)
    existing = (
        "# >>> feed schedule (com.user.feed) >>>\n"
        "OLD CRON ENTRY\n"
        "# <<< feed schedule (com.user.feed) <<<\n"
    )
    monkeypatch.setattr("src.scheduler._read_crontab", lambda: existing)
    monkeypatch.setattr("src.scheduler._write_crontab", lambda content: None)
    with pytest.raises(RuntimeError):
        install_cron(plan, replace_existing=False)


def test_install_cron_malformed_block_raises(tmp_path, monkeypatch):
    plan = _plan(tmp_path)
    bad = (
        "# <<< feed schedule (com.user.feed) <<<\n"
        "OLD\n"
        "# >>> feed schedule (com.user.feed) >>>\n"
    )
    monkeypatch.setattr("src.scheduler._read_crontab", lambda: bad)
    monkeypatch.setattr("src.scheduler._write_crontab", lambda content: None)
    with pytest.raises(RuntimeError):
        install_cron(plan)


def test_read_crontab_returns_empty_when_no_crontab():
    fake = MagicMock(returncode=1, stdout="", stderr="no crontab for user")
    with patch("src.scheduler.subprocess.run", return_value=fake):
        assert _read_crontab() == ""


def test_read_crontab_raises_on_unknown_error():
    fake = MagicMock(returncode=2, stdout="", stderr="permission denied")
    with patch("src.scheduler.subprocess.run", return_value=fake):
        with pytest.raises(RuntimeError):
            _read_crontab()


def test_launchd_domain_and_service_format():
    domain, service = launchd_domain_and_service("com.foo.bar")
    assert domain.startswith("gui/")
    assert service.endswith("/com.foo.bar")


def test_write_launchd_plist_writes_xml(tmp_path):
    plan = _plan(tmp_path)
    path = write_launchd_plist(plan)
    assert path.exists()
    content = path.read_bytes()
    assert b"com.user.feed" in content
    assert (tmp_path / "logs").is_dir()


def test_bootstrap_launchd_invokes_launchctl(tmp_path):
    plan = _plan(tmp_path)
    plist_path = tmp_path / "p.plist"
    plist_path.write_text("")

    calls = []

    def _run(args, *a, **kw):
        calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("src.scheduler.subprocess.run", side_effect=_run):
        domain, service = bootstrap_launchd(plan, plist_path)

    assert domain.startswith("gui/")
    assert service.endswith("/com.user.feed")
    assert any("bootout" in c for c in calls)
    assert any("bootstrap" in c for c in calls)
