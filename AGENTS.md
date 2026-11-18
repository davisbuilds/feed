# AGENTS.md

`feed` is a newsletter intelligence CLI that fetches RSS feeds, generates
AI-powered digests, and delivers them by email or terminal. `./feed --help`
lists commands (`./feed` wraps `uv run feed`).

## Documentation Map

- `CONTRIBUTING.md` — contribution scope, review expectations, and delivery.
- `docs/system/ARCHITECTURE.md` — pipeline, CLI layer, LLM provider defaults, storage, cache, schedulers.
- `docs/system/FEATURES.md` — CLI command reference, config variables, features.
- `docs/system/OPERATIONS.md` — local dev, CI and local verification, env vars, XDG paths, scripts, privacy, recovery.
- `docs/system/TEST_STRATEGY.md` — test plan: edge cases, security validation, benchmarks.
- `docs/project/ROADMAP.md`, `docs/project/BACKLOG.md`.
- `docs/project/GIT_HISTORY_POLICY.md` — merge strategy and commit classification for releases.

## Runtime Configuration Gotchas

Settings load through Pydantic Settings from `~/.config/feed/config.env` (XDG,
written by `feed init`), overridden by a `.env` in the current directory.

- **Do not assume `config/feeds.yaml` is the active feed file.** The active file
  is `settings.config_dir / "feeds.yaml"`, and `config_dir` follows env
  resolution. Check `feed config` (or `--json`) before editing a user's feeds.
- When asked to "standardize" feeds, compare and sync both `config/feeds.yaml`
  and `~/.config/feed/feeds.yaml` as requested; neither is automatically
  authoritative.

## Testing

- **Local gate** (matches the required `Lint & dead code`, `Test (pytest)`, and
  `check` checks):
  `uv sync --locked --extra dev && uv run ruff check . && uv run ruff format --check . && uv run python -m pytest -q && python3 scripts/check_publication_hygiene.py`.
  CI also classifies every non-merge commit subject on the branch:
  `python3 scripts/check_commit_subjects.py origin/main` (it refuses an empty range).
  For workflow changes, also run `uvx zizmor@1.30.0 --offline .github/workflows/`.
- **Dead-code gate** (`tests/test_dead_code.py`) owns cross-file dead code; ruff
  `F`/`ERA` own within-file unused code. `scripts/` and the Jinja templates
  (`src/feed/deliver/templates/`) count as references. For an intentionally unreferenced symbol or module (external
  API, framework-invoked), add it to `SYMBOL_EXCEPTIONS`/`MODULE_EXCEPTIONS` with
  a reason rather than silencing the test.
- Ruff owns modern-Python style; fix what it flags.

## Working Agreement

- **Clarify before building** when a request is vague, contradictory, or skips a
  key decision; clear, well-scoped requests need no interview.
- **Fix small issues now; backlog the rest.** Fix simple, quick, or blocking
  issues in this repo as part of the current change and call them out. Record in
  `docs/project/BACKLOG.md` only what can't be finished now or needs the
  maintainer's decision; don't open a branch or PR just for a backlog entry.
- **Keep docs current** when a change makes a documented contract, boundary,
  procedure, or direction stale.
- **Plan and hand off work.** Reuse clear task context. Save planning docs when
  decisions, acceptance, or coordination need persistence, and leave a brief
  handoff only when needed to resume unfinished work. Commit shared docs and keep
  status current. `docs/archive/` is gitignored: before archiving a completed doc
  there, preserve lasting decisions and open work in maintained docs and repair
  links.
- **Commit and push.** Commit coherent chunks, staging by explicit path. Push
  your task branch and open a PR once the work is complete and the local gate
  passes; don't push directly to `main`.
- **Merge** only under the standing merge authority in the maintainer's workspace
  instructions, or when the maintainer asks. Without those instructions in
  context, leave the PR for the maintainer.
- **History and releases.** Squash is disabled: merge commit by default, rebase
  only when the branch's commits are already clean. Every non-merge commit uses a
  Conventional Commit subject, with `!` or a `BREAKING CHANGE:` footer for
  incompatible behavior; the PR title does not replace that, because Release
  Please reads the preserved commits (bump rules in `GIT_HISTORY_POLICY.md`).
  Merging the Release Please PR tags a GitHub Release; leave it for the maintainer.
- **Re-ground after compaction** in source, this file, the owning docs, and
  recent commits. A summary and your own earlier proposals are not user approval.
