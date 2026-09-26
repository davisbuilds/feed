"""Local release wiring and commit classification regression checks."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_release_baseline_and_lockfile_match_package_version() -> None:
    """A release must update the package, manifest, and root lock entry together."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    manifest = json.loads((ROOT / ".release-please-manifest.json").read_text())
    packages = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    root_package = next(package for package in packages if package["name"] == project["name"])

    assert project["version"] == manifest["."] == root_package["version"]


@pytest.mark.parametrize(
    ("subjects", "expected", "merge"),
    [
        (
            ["feat(cli)!: change output schema", "fix: handle empty feeds", "docs: explain flags"],
            0,
            False,
        ),
        (["Add output mode"], 1, False),
        (["feat: "], 1, False),
        (["feat: add output mode"], 0, True),
    ],
)
def test_commit_guard_classifies_real_git_history(tmp_path, subjects, expected, merge) -> None:
    """The CI command accepts classified subjects and rejects omitted change types."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "config", "user.name", "Release test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "release-test@example.invalid"], cwd=tmp_path, check=True
    )

    def commit(subject):
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", subject],
            cwd=tmp_path,
            check=True,
        )

    commit("Legacy baseline")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    if merge:
        subprocess.run(["git", "checkout", "-qb", "feature"], cwd=tmp_path, check=True)
    for subject in subjects:
        commit(subject)
    if merge:
        subprocess.run(["git", "checkout", "-q", "-"], cwd=tmp_path, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "commit.gpgsign=false",
                "merge",
                "--no-ff",
                "-qm",
                "Merge feature",
                "feature",
            ],
            cwd=tmp_path,
            check=True,
        )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_commit_subjects.py"), base],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == expected
    if expected:
        assert "Unclassified commit subject:" in result.stderr
