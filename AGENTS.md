# AGENTS.md

`feed` is a newsletter intelligence CLI that fetches RSS feeds, generates AI-powered digests, and delivers them via email/terminal.

## Documentation Map

- `docs/system/ARCHITECTURE.md` — pipeline flow, CLI layer, LLM abstraction (provider defaults), storage tables, cache, scheduler backends, directory map.
- `docs/system/FEATURES.md` — full CLI command reference, config variables, ingestion/analysis/delivery features, scheduling, cache.
- `docs/system/OPERATIONS.md` — local dev, command list, CI/local verification, env vars, XDG paths, scripts catalog, local data/privacy, recovery/troubleshooting.
- `docs/project/ROADMAP.md` — shipped highlights and pointers to active plans under `docs/plans/`.
- `docs/project/GIT_HISTORY_POLICY.md` — history conventions.

## Command Quickstart

```bash
uv sync --extra dev
./feed --help      # list all available CLI commands
./feed init        # interactive setup
./feed run         # full pipeline
```

## Runtime Configuration Gotchas

Settings load via Pydantic Settings from two env-file locations (cwd `.env` overrides XDG):

1. `~/.config/feed/config.env` — user-level XDG config (created by `feed init`).
2. `.env` in current working directory — project-level override.

The `feed init` wizard writes `config.env` and copies `feeds.yaml` into the XDG dir, so users can run `feed` from any location.

- **Do not assume `config/feeds.yaml` is the active feed file.** Active path is `settings.config_dir / "feeds.yaml"` and `settings.config_dir` is driven by env resolution.
- Before editing feed configuration for a user, verify active paths with `feed config` (or `feed config --json` for machine-readable output).
- When users ask to "standardize" feeds, compare and sync both `config/feeds.yaml` and `~/.config/feed/feeds.yaml` as requested — neither is automatically authoritative.
- **Run tests with `uv run python -m pytest`**, not `uv run pytest` (the latter fails with "No such file or directory").

## Testing

- **Pre-push** (matches CI `.github/workflows/ci.yml`): `uv run ruff check .`, `uv run ruff format --check .`, and `uv run python -m pytest`.
- **TDD**: red/green for new features, major refactors, and large changes. The red step must fail for the behavior you're about to fix — a test that fails only because the symbol doesn't exist yet is a stub, not a red test; write the signature first, then a test that fails on the behavior. Skip the red step for code with no behavior to assert, and cover it after. For smaller edits, still run the relevant existing tests before wrapping up.
- **Dead-code gate** (`tests/test_dead_code.py`): static checks for unused public symbols, orphaned modules, and unreachable code. Out-of-package consumers (`scripts/`) and Jinja `templates/` are part of its reference corpus. It owns cross-file dead code; ruff `F`/`ERA` own within-file unused imports/locals and commented-out code. When a symbol/module is intentionally unreferenced (external API, framework-invoked), add it to `SYMBOL_EXCEPTIONS`/`MODULE_EXCEPTIONS` with a reason rather than silencing the test.

## Conventions Enforced Elsewhere

Ruff handles modern-Python style: `datetime.UTC` over `timezone.utc` (UP017), `collections.abc` imports (UP035), import ordering (I001), forward-ref hints via `from __future__ import annotations` + `TYPE_CHECKING`. Don't restate these here — fix any violations the linter flags.

## Working Agreement

- **Push back before building.** If a request is incoherent or self-contradictory, or a spec/plan is vague or skips key decisions, stop and interview me — ask clarifying questions and confirm intent before writing code or changing files. Don't guess at scope or comply silently. (Clear, well-scoped requests don't need this.)
- **Keep docs current.** After a significant change, PR, or completed spec/plan, update any now-stale reference docs under `docs/system/` (and `docs/project/ROADMAP.md`) so they match shipped behavior. Skip this for trivial changes.
- **Commit logically.** Commit completed work in coherent chunks as you proceed. Push only when explicitly asked.
- **Log findings in `BACKLOG.md`.** Note design gaps, tech debt, or better approaches you spot mid-task in `docs/project/BACKLOG.md`; fix simple/quick ones inline and call them out.
- **Re-ground after compaction.** A compaction summary loses precise paths, context, and verification state — before continuing, re-read this project's `AGENTS.md`, its reference docs, and recent commits.
