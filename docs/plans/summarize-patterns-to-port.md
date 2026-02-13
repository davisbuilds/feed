# Patterns to Port from `summarize` → `feed`

> Analysis date: 2026-02-12
> Source project: `~/Dev/summarize` — TypeScript/Node.js monorepo CLI for URL/media summarization
> Target project: `~/Dev/feed` — Python CLI for RSS newsletter intelligence

## Context

The `summarize` project is a mature (~28K LOC TypeScript) CLI with multi-provider LLM support, streaming output, SQLite caching, a daemon service, and a Chrome extension. This analysis identifies design, performance, and architecture patterns worth porting to `feed`.

---

## Priority Matrix

| # | Opportunity | Impact | Effort | Priority |
|---|---|---|---|---|
| 1 | Response caching | High | Medium | **P1** |
| 2 | LLM retry + exponential backoff | High | Low | **P1** |
| 3 | Configurable timeouts | Medium | Low | **P2** |
| 4 | Actual cost tracking | Medium | Low | **P2** |
| 5 | Token preflight estimation | Medium | Low | **P2** |
| 6 | Model fallback chain | High | Medium | **P3** |
| 7 | Quality gate script | Low | Low | **P3** |
| 8 | EPIPE / broken pipe handling | Low | Trivial | **P3** |
| 9 | Streaming LLM output | Medium | Medium | **P4** |
| 10 | State resolution / dependency injection | Medium | High | **P4** |

---

## P1 — Do First

### 1. Response Caching Layer

**Problem:** Re-running `feed analyze` or `feed run` re-summarizes the same articles, burning API credits. No caching exists anywhere in the pipeline.

**How summarize does it:** SQLite-based cache (`src/cache.ts`, ~573 lines) with TTL, LRU eviction by max MB, and SHA256 cache keys. Separate cache kinds: `extract`, `summary`, `transcript`, `chat`, `slides`.

```typescript
// summarize's CacheStore interface
type CacheStore = {
  getText(kind, key): string | null
  getJson<T>(kind, key): T | null
  setText(kind, key, value, ttlMs): void
  setJson(kind, key, value, ttlMs): void
  clear(): void
  close(): void
}
```

**What to build in feed:**

- Add a `cache` table to the existing SQLite database:
  ```sql
  CREATE TABLE cache (
    kind TEXT NOT NULL,          -- 'summary' | 'synthesis'
    key TEXT NOT NULL,           -- SHA256 hash
    value TEXT NOT NULL,         -- JSON blob
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    PRIMARY KEY (kind, key)
  );
  ```
- Cache key = `sha256(article_url + content_hash + model + prompt_version)`
- Default TTL: 7 days
- Add `--no-cache` flag to `feed run` and `feed analyze`
- Add `feed cache clear` command
- Integrate into `Summarizer.summarize_article()` — check cache before LLM call

**ROI:** Highest of all items. Every dev/test cycle currently wastes full API spend.

---

### 2. LLM Retry with Exponential Backoff

**Problem:** A single timeout or transient 429/500 from any LLM provider kills the entire summarization batch. No retry logic exists in any of the three provider implementations.

**How summarize does it:** Configurable retries with exponential backoff on retryable errors (timeouts, rate limits, 5xx). Implemented in `src/llm/generate-text.ts` (~774 lines).

```typescript
// summarize's retry pattern
for (let attempt = 0; attempt <= maxRetries; attempt++) {
  try {
    const result = await race(promise, timeoutMs)
    return result
  } catch (error) {
    if (isRetryableTimeoutError(error) && attempt < maxRetries) {
      await delay(exponentialBackoff(attempt))
      continue
    }
    throw
  }
}
```

**What to build in feed:**

- Add a retry decorator or wrapper in `src/llm/base.py`:
  ```python
  def with_retry(fn, max_retries=2, base_delay=1.0):
      for attempt in range(max_retries + 1):
          try:
              return fn()
          except RETRYABLE_ERRORS as e:
              if attempt == max_retries:
                  raise
              delay = base_delay * (2 ** attempt)
              logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s: {e}")
              time.sleep(delay)
  ```
- Retryable errors: `TimeoutError`, `httpx.TimeoutException`, HTTP 429, HTTP 5xx
- Config: `LLM_RETRIES=2` env var, `--retries` CLI flag
- Apply in each provider's `generate()` method or at the `create_client` wrapper level

**Current gap:** `src/llm/gemini.py` has one bare `generate_content()` call with a hardcoded 120s timeout. OpenAI and Anthropic providers similarly have no retry.

---

## P2 — Do Next

### 3. Configurable Timeouts

**Problem:** Timeouts are hardcoded and scattered: 120s for Gemini, 30s for HTTP fetches. No way to override without editing source.

**How summarize does it:** `--timeout 2m` flag with a duration parser supporting `ms/s/m/h`. Centralized timeout configuration.

**What to build in feed:**

- Add to `config.py`:
  ```python
  llm_timeout: int = 120       # LLM_TIMEOUT env var (seconds)
  http_timeout: int = 30       # HTTP_TIMEOUT env var (seconds)
  ```
- Pass through to provider constructors and `httpx` calls
- Add `--timeout` flag to `feed run`

---

### 4. Actual Cost Tracking

**Problem:** `feed` estimates cost with a rough 70/30 input/output token split assumption. The actual `input_tokens` and `output_tokens` returned by `LLMResponse` are already available but not accumulated or displayed.

**How summarize does it:** Tracks actual `input_tokens` and `output_tokens` per call, accumulates across the pipeline, computes real costs with per-model pricing, and displays in JSON output and terminal summary.

**What to build in feed:**

- Accumulate `input_tokens` and `output_tokens` separately throughout `run_analysis()`
- Replace the 70/30 estimate with actual counts
- Update per-model pricing table with current rates
- Display at end of `feed run`:
  ```
  Tokens: 45,230 in / 8,102 out · Cost: $0.0089 (gemini-2.5-flash)
  ```
- Include in `--format json` output

---

### 5. Token Preflight Estimation

**Problem:** Article content is truncated at a hardcoded 30KB byte limit. A 29KB article with many short words can exceed token limits despite being under the byte cap.

**How summarize does it:** Uses `gpt-tokenizer` to estimate prompt token count before sending. Prevents wasted requests that would fail due to context overflow.

**What to build in feed:**

- Add `tiktoken` as a dev dependency (works for all providers as a rough estimate)
- In `Summarizer.summarize_article()`, estimate tokens before calling LLM:
  ```python
  import tiktoken
  enc = tiktoken.get_encoding("cl100k_base")
  token_count = len(enc.encode(content))
  if token_count > max_input_tokens:
      content = truncate_to_tokens(content, max_input_tokens)
  ```
- Log token estimates for cost visibility
- Replace the 30KB byte truncation with token-aware truncation

---

## P3 — Polish

### 6. Model Fallback Chain

**Problem:** If the configured model fails after retries, the entire pipeline fails. No automatic fallback to alternative models.

**How summarize does it:** `--model auto` tries candidates in order. The summary engine (`src/run/summary-engine.ts`) attempts models sequentially until one succeeds. Supports rules-based auto-selection per content type.

**What to build in feed:**

- Add `LLM_FALLBACK_MODELS` env var (comma-separated, e.g., `gemini-2.5-flash,gpt-4o-mini`)
- After primary model exhausts retries, try each fallback in order
- Log which model ultimately succeeded
- Natural extension since `feed` already supports 3 providers

---

### 7. Quality Gate Script

**Problem:** No unified check command. `uv run pytest` and `uv run ruff check .` are separate.

**How summarize does it:** `pnpm check` = lint + test with 75% coverage threshold. Single command gates all PRs.

**What to build in feed:**

- Add `scripts/check.sh`:
  ```bash
  #!/bin/bash
  set -e
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest --cov=src --cov-fail-under=75
  ```
- Or configure in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  addopts = "--cov=src --cov-fail-under=75"
  ```

---

### 8. EPIPE / Broken Pipe Handling

**Problem:** `feed run --format text | head -5` likely produces a `BrokenPipeError` traceback.

**How summarize does it:**
```typescript
stream.on('error', (error) => {
  if (error.code === 'EPIPE') exit(0)
})
```

**What to build in feed:**

Add to `cli.py` entry point:
```python
import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
```
Or wrap the CLI entry in a `BrokenPipeError` catch.

---

## P4 — Future

### 9. Streaming LLM Output

**Problem:** During `feed run`, the user stares at a spinner for 30+ seconds while LLM generates the digest. No incremental feedback.

**How summarize does it:** Streams tokens to terminal in real-time via provider streaming APIs. Uses `markdansi` for on-the-fly markdown rendering.

**What to build in feed:**

- Add `stream=True` support to each provider (all three SDKs support it)
- In `--format rich` mode, stream digest synthesis to terminal as it generates
- Keep non-streaming for structured JSON responses (article summaries need schema validation)
- Best candidates: `overall_synthesis` and `category_synthesis` calls in `digest_builder.py`

**Consideration:** Streaming conflicts with structured output (JSON schema). Only applicable to free-form text generation steps.

---

### 10. State Resolution / Dependency Injection

**Problem:** `get_settings()` is a singleton accessed deep in modules. Testing requires monkeypatching. Configuration source is opaque at call sites.

**How summarize does it:** Each resolver is a pure function that takes explicit dependencies and returns an immutable state object. No singletons. Full traceability of config sources.

```typescript
export function resolveConfigState({envForRun, programOpts, ...}): ConfigState {
  return { config, configPath, outputLanguage, ... }  // immutable
}
```

**What to build in feed:**

- Create a `RunContext` dataclass at CLI entry, populated from Settings
- Thread it through the pipeline explicitly: `run_ingestion(ctx, ...)`, `run_analysis(ctx, ...)`
- Modules receive what they need, don't reach for globals
- Selective refactor — not a full rewrite, just wrap at the boundary

**Trade-off:** Higher effort, primarily a testability and maintainability improvement. Pydantic Settings is already good enough for the current project size.

---

## What `feed` Already Does Well

These areas are already at parity or better than `summarize`:

| Area | feed | summarize |
|---|---|---|
| Config convention | XDG Base Dir (standard) | Custom `~/.summarize/` |
| Config validation | Pydantic Settings (Pythonic, typed) | JSON5 parser (custom) |
| CLI framework | Typer (auto-help, type inference) | Commander.js (manual setup) |
| Terminal output | Rich (panels, tables, progress) | ora + markdansi (comparable) |
| Database | SQLite WAL | SQLite WAL |
| Concurrent I/O | ThreadPoolExecutor(10) for feeds | Similar concurrency model |
| Error cascading | Partial success at pipeline level | Similar fail-safe pattern |
| Provider abstraction | Protocol-based with lazy imports | Interface-based with lazy imports |

---

## Implementation Notes

- Start with **caching + retry** — they compound: cache prevents re-work, retry prevents transient failures from creating re-work.
- **Configurable timeouts** are a prerequisite for retry (need to know when to give up on an attempt).
- **Cost tracking** is trivial since `LLMResponse` already carries token counts.
- **Token estimation** and **model fallback** build on the retry infrastructure.
- **Streaming** is a separate track that doesn't depend on the above.
