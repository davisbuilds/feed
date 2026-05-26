# Feed

Personal newsletter intelligence CLI. Feed fetches RSS/Atom feeds, summarizes new
articles with an LLM, and delivers a digest to the terminal, clipboard, or email.

Current CLI version: `v0.3.0`.

## Agent Setup

New here? Paste the prompt below into your coding agent (Claude Code, Codex, etc.) and it will clone, install, configure, and verify the repo for you, then tell you exactly which API keys you still need to supply.

```text
Set up the `feed` repo for me. It's a Python CLI (Python 3.12+, uv, Typer/Rich,
SQLite) that fetches RSS feeds, summarizes them with an LLM, and delivers a digest
to the terminal or email.

Do this, in order:

1. Install deps. Ensure `uv` is installed (https://astral.sh/uv); then run `uv sync`
   from the repo root. If we're not in the repo yet, clone
   https://github.com/davisbuilds/feed.git and cd into it first.

2. Configure env. Copy `.env.example` to `.env`. Fill values with clearly-labeled
   placeholders for now — do NOT invent real keys. Then tell me which are REQUIRED
   vs OPTIONAL:
   - REQUIRED to run a real digest: LLM_API_KEY (+ LLM_PROVIDER, defaults to gemini;
     openai/anthropic also supported).
   - OPTIONAL, email delivery only: RESEND_API_KEY, EMAIL_FROM, EMAIL_TO.

3. Verify the setup works WITHOUT any secrets. Run `uv run python -m pytest`
   (note: use `python -m pytest`, not `uv run pytest`) and `./feed --help`. Both
   should succeed offline. If either fails, show me the error and stop.

4. Report back: confirm install + smoke passed, list exactly which keys I still
   need to provide a real value for and what each unlocks, and give me the single
   command to run it for real (`./feed init` for the guided wizard, or `./feed run`
   once LLM_API_KEY is set).

Don't commit anything, and don't run commands that need a real API key until I give
you one.
```

Prefer to do it yourself? The manual steps are below.

## What It Does

- Fetches Substack, RSS, and Atom feeds concurrently.
- Summarizes articles, extracts takeaways, and synthesizes trends with Gemini, OpenAI, or Anthropic.
- Groups updates by feed category for easier reading.
- Outputs rich terminal text, plain text, JSON, clipboard Markdown, or email via Resend.
- Stores article metadata, digest records, send state, and LLM cache entries in local SQLite.
- Supports run-anywhere XDG config under `~/.config/feed/`.
- Includes feed diagnostics, scheduling helpers, response caching, and retry/backoff controls.

## Quick Start

Requirements:

- Python `3.12+`
- `uv`
- An LLM API key for real digest generation

```bash
git clone https://github.com/davisbuilds/feed.git
cd feed
uv sync

./feed init
./feed run
```

The setup wizard writes `~/.config/feed/config.env` and `~/.config/feed/feeds.yaml`
so the installed `feed` command can run from any directory. Email delivery is
optional and can be skipped if you only want terminal output.

Optional global install from the repo root:

```bash
uv tool install --editable .
feed --help
```

## Common Commands

```bash
./feed --help
./feed init                      # interactive setup wizard
./feed config                    # show active env, config, feed, and data paths
./feed run                       # ingest, analyze, and print a digest
./feed run --copy                # copy digest as Markdown
./feed run --send                # send digest by email
./feed test --all                # validate configured feeds
./feed schedule --status         # inspect installed schedule status
./feed schedule --install        # install schedule with automatic backend
uv run python -m pytest          # run tests
uv run ruff check .              # lint
uv run ruff format --check .     # formatting check
```

Run `feed <command> --help` for per-command options. The full CLI surface is in
[docs/system/FEATURES.md](docs/system/FEATURES.md).

## Configuration

Config is loaded from two env-file locations. Later entries override earlier ones:

1. `~/.config/feed/config.env` — user-level XDG config created by `feed init`
2. `.env` in the current directory — project-level override

Minimum real digest config:

```ini
LLM_PROVIDER=gemini
LLM_API_KEY=your_api_key
```

Email delivery with `feed run --send` also requires:

```ini
RESEND_API_KEY=your_resend_api_key
EMAIL_FROM=digest@yourdomain.com
EMAIL_TO=you@example.com
```

Feed subscriptions live in `feeds.yaml` under the active `CONFIG_DIR`. Run
`feed config` or `feed config --json` before editing feeds so you know whether
the active file is the repo-local `config/feeds.yaml` or the XDG
`~/.config/feed/feeds.yaml`.

Detailed environment variables, XDG path behavior, scripts, privacy notes, and
troubleshooting live in [docs/system/OPERATIONS.md](docs/system/OPERATIONS.md).

## Code Layout

```text
config/              default feeds.yaml
src/analyze/         summarizer and digest builder
src/deliver/         email sender and templates
src/ingest/          feed fetch, parse, and diagnostics
src/llm/             provider clients and retry wrapper
src/storage/         SQLite DB and cache store
src/cli.py           Typer CLI entry point
scripts/             utility scripts
tests/               pytest suite
docs/                system, project, and plan docs
```

## Documentation

- Agent implementation guidance: [AGENTS.md](AGENTS.md)
- Architecture and code organization: [docs/system/ARCHITECTURE.md](docs/system/ARCHITECTURE.md)
- Feature and CLI reference: [docs/system/FEATURES.md](docs/system/FEATURES.md)
- Runtime operations, env vars, scripts, and troubleshooting: [docs/system/OPERATIONS.md](docs/system/OPERATIONS.md)
- Product roadmap snapshot: [docs/project/ROADMAP.md](docs/project/ROADMAP.md)
- Testing strategy: [docs/plans/TEST_PLAN.md](docs/plans/TEST_PLAN.md)
- Git history and branch policy: [docs/project/GIT_HISTORY_POLICY.md](docs/project/GIT_HISTORY_POLICY.md)
- Contributor workflow and PR expectations: [CONTRIBUTING.md](CONTRIBUTING.md)

## Current Boundaries

- Real digest generation requires an LLM API key.
- Email delivery is optional and requires Resend credentials plus a verified sender domain.
- `uv run python -m pytest` is the canonical test command; do not use `uv run pytest`.
- The active feeds file is config-dependent. Always check `feed config` before editing a user's subscriptions.
