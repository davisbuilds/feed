# Operations

## Local Development

```bash
uv sync
./feed <command>
```

Or equivalently: `uv run feed <command>`.

## Useful Commands

```bash
uv sync                          # Install dependencies
uv sync --extra dev              # Install with dev tools
./feed init                      # Interactive setup wizard
./feed config                    # Show active config/data/feed paths
./feed run                       # Full pipeline (terminal output)
./feed run --send                # Full pipeline (email delivery)
uv run python -m pytest          # Run tests (NOT uv run pytest)
uv run ruff check .              # Lint
uv run ruff format --check .     # Formatting check
```

## CI

Workflow: `.github/workflows/ci.yml`

Triggers:

- Pull requests to `main`
- Pushes to `main`

Jobs:

- Lint/dead-code: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run python -m pytest -q tests/test_dead_code.py`.
- Test: `uv run python -m pytest -q`.

CI runtime details:

- Python 3.12
- uv with `uv sync --extra dev`

## Environment Variables

### Required

| Variable | Required For | Used For |
|----------|--------------|----------|
| `OPENAI_API_KEY` | `feed analyze`, `feed run` with `LLM_PROVIDER=openai` | Primary OpenAI authentication |
| `LLM_API_KEY` or `GOOGLE_API_KEY` | `feed analyze`, `feed run` with Gemini or Anthropic | Optional-provider authentication (`LLM_API_KEY` is also a legacy OpenAI fallback) |
| `RESEND_API_KEY` | `feed send`, `feed run --send` | Email delivery via Resend |
| `EMAIL_FROM` | `feed send`, `feed run --send` | Sender email address |
| `EMAIL_TO` | `feed send`, `feed run --send` | Recipient email address |

Terminal-only ingestion/status/cache commands do not need Resend credentials.

### Optional

| Variable | Default | Used For |
|----------|---------|----------|
| `LLM_PROVIDER` | `openai` | Provider selection (`openai`, `gemini`, `anthropic`) |
| `LLM_MODEL` | per-provider | Model override |
| `LLM_REASONING_EFFORT` | `xhigh` | OpenAI reasoning effort; ignored by Gemini and Anthropic |
| `CONFIG_DIR` | `config/` | Path to `feeds.yaml` directory |
| `DATA_DIR` | `data/` | SQLite data directory |
| `DIGEST_HOUR` | `7` | Hour for scheduled digests (0-23) |
| `DIGEST_TIMEZONE` | `America/New_York` | Timezone for scheduling |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_ARTICLES_PER_FEED` | `10` | Per-feed fetch cap |
| `LOOKBACK_HOURS` | `24` | New-article window |
| `CACHE_TTL_DAYS` | `7` | LLM cache retention window |

## XDG Config Paths

- User-level config: `~/.config/feed/config.env` (created by `feed init`).
- User-level feeds: `~/.config/feed/feeds.yaml`.
- Project `.env` overrides XDG config.
- Run `feed config` to see active paths.
- Active feed config is `settings.config_dir / "feeds.yaml"`; do not assume the
  repo's `config/feeds.yaml` is live for a user.

## Scripts

Utility scripts in `scripts/`:

| Script | Purpose |
|--------|---------|
| `healthcheck.py` | Verify environment and dependencies |
| `verify_setup.py` | Validate configuration |
| `list_models.py` | List available models for configured provider |
| `preview_email.py` | Preview email template rendering |
| `run_ingest.py` | Test ingestion pipeline manually |
| `run_analyze.py` | Test analysis pipeline manually |
| `run_email.py` | Test email delivery manually |
| `setup_cron.py` | Configure cron scheduling |
| `setup_launchd.py` | Configure launchd scheduling |

## Data

- Article database: `data/articles.db` (SQLite, WAL mode).
- Cache database: co-located in the same SQLite file.
- Do not commit `data/` or `*.db` files.

## Privacy And Local Data

- `config.env` contains API keys and email addresses. Keep it out of git.
- `feeds.yaml` can reveal private reading interests. Confirm the active path before
  editing or sharing.
- `articles.db` stores article metadata, summaries, digest records, send status, and
  cached LLM responses.
- Cache entries expire lazily according to `CACHE_TTL_DAYS`; old SQLite rows may
  remain until cache maintenance/write paths touch them.
- Email previews and delivery templates can contain personal inbox context. Treat
  rendered output as private by default.

## Recovery And Troubleshooting

| Symptom | Check |
| --- | --- |
| CLI cannot find config | Run `./feed init`, then `./feed config` to inspect active paths. |
| Edited feeds are ignored | Check whether cwd `.env` changes `CONFIG_DIR`; compare repo `config/feeds.yaml` with `~/.config/feed/feeds.yaml`. |
| `uv run pytest` fails | Use `uv run python -m pytest`; this repo documents that form as canonical. |
| LLM provider uses unexpected model | Check `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_REASONING_EFFORT` in both env files. For Gemini, also inspect legacy `GEMINI_MODEL`. |
| OpenAI authentication fails | Confirm `OPENAI_API_KEY` is available to the process. A configured Gemini or Anthropic provider instead uses `LLM_API_KEY` (or Gemini's legacy `GOOGLE_API_KEY`). |
| Email send fails | Verify `RESEND_API_KEY`, `EMAIL_FROM`, and `EMAIL_TO`; preview rendering with `scripts/preview_email.py` before sending. |
| Digest repeats old articles | Inspect `LOOKBACK_HOURS`, cache state, and `data/articles.db`. |
| Scheduler fires at wrong time | Check `DIGEST_TIMEZONE` and generated cron/launchd entry. |
| Data path is surprising | Run `feed config --json` and inspect `DATA_DIR`. |
