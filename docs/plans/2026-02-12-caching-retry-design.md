# Design: LLM Response Caching & Retry

> Date: 2026-02-12
> Status: Approved

## Problem

1. **No retry:** A single timeout or transient 429/500 from any LLM provider kills the entire summarization batch. All three providers have zero retry logic.
2. **No caching:** Re-running `feed analyze` or `feed run` re-summarizes the same articles, burning API credits every time.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Retry layer | Wrapping decorator via `RetryClient` | Providers stay untouched; one place to tune retry |
| Cache storage | `cache` table in existing `articles.db` | Reuses WAL mode, no new files |
| Cache key | `sha256(article_id + ":" + model)` | Stable IDs, invalidates on model change |
| Cache scope | Article summaries only | Digest synthesis is cheap and changes every run |
| Cache TTL | 7 days default + `feed cache clear` | Auto-expire stale data, manual override available |

## Design

### 1. Retry — `src/llm/retry.py`

A `RetryClient` class that wraps any `LLMClient` and delegates `generate()` with retry logic.

```python
class RetryClient:
    def __init__(self, inner: LLMClient, max_retries: int = 2, base_delay: float = 1.0):
        self.inner = inner
        self.max_retries = max_retries
        self.base_delay = base_delay

    def generate(self, prompt, system, response_schema) -> LLMResponse:
        for attempt in range(self.max_retries + 1):
            try:
                return self.inner.generate(prompt, system, response_schema)
            except LLMError as e:
                if not _is_retryable(e) or attempt == self.max_retries:
                    raise
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Retry {attempt+1}/{self.max_retries} after {delay}s: {e}")
                time.sleep(delay)
```

**Retryable errors** (detected by inspecting `LLMError` message):
- Timeout / deadline exceeded
- Rate limit (429)
- Server error (500, 502, 503, 529)

**Not retryable** (fail immediately):
- Auth errors (401, 403)
- Bad request / parse failures
- Unknown errors (conservative default)

**Integration:** `create_client()` in `src/llm/__init__.py` wraps the provider with `RetryClient`:

```python
def create_client(provider, api_key, model, max_retries=2, timeout=120):
    inner = _create_provider(provider, api_key, resolved_model)
    return RetryClient(inner, max_retries=max_retries)
```

### 2. Cache — `src/storage/cache.py`

A `CacheStore` class backed by a `cache` table in the existing SQLite database.

**Schema** (added to `db.py._ensure_schema()`):

```sql
CREATE TABLE IF NOT EXISTS cache (
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (kind, key)
);
```

**CacheStore interface:**

```python
class CacheStore:
    def __init__(self, db_path: Path, default_ttl_days: int = 7): ...
    def get(self, kind: str, key: str) -> dict | None: ...
    def set(self, kind: str, key: str, value: dict, ttl_days: int | None = None) -> None: ...
    def clear(self, kind: str | None = None) -> int: ...
    def stats(self) -> dict: ...
```

- `get()` returns `None` for missing or expired entries
- `set()` upserts with `INSERT OR REPLACE`, computes `expires_at`
- `clear()` deletes all entries (or by kind), returns count deleted
- `stats()` returns `{total_entries, expired_entries, kinds}` for the `feed cache` CLI
- Expired rows cleaned lazily on each `set()` call

**Cache key construction:**

```python
import hashlib

def make_cache_key(article_id: str, model: str) -> str:
    raw = f"{article_id}:{model}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

### 3. Summarizer Integration

In `Summarizer.summarize_article()`, check cache before calling LLM:

```python
def summarize_article(self, article, cache=None, model_name=None):
    if cache:
        key = make_cache_key(article.id, model_name)
        cached = cache.get("summary", key)
        if cached:
            logger.info(f"Cache hit: {article.title[:50]}...")
            return SummaryResult(**cached)

    # ... existing LLM call ...

    if cache and result["success"]:
        cache.set("summary", key, result)

    return result
```

The `cache` and `model_name` are passed in from `run_analysis()`, which creates the `CacheStore` unless `--no-cache` is set.

### 4. Config additions

New fields in `src/config.py` `Settings`:

```python
llm_retries: int = Field(default=2, ge=0, le=5, description="Max LLM retry attempts")
llm_timeout: int = Field(default=120, ge=10, description="LLM timeout in seconds")
cache_ttl_days: int = Field(default=7, ge=1, description="Cache TTL in days")
```

### 5. CLI additions

**`feed cache clear`** — new command:

```python
@app.command("cache")
def cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Clear all cached results"),
):
    """Manage the response cache."""
    # show stats, or clear if --clear
```

**`--no-cache` flag** on `feed run` and `feed analyze`:

```python
@app.command()
def run(
    send: bool = ...,
    output_format: str = ...,
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache, re-summarize all"),
):
```

The `no_cache` flag is threaded through to `run_analysis()` which skips creating the `CacheStore`.

## File Changes

| File | Change |
|---|---|
| `src/llm/retry.py` | **New** — `RetryClient` wrapper, `_is_retryable()` |
| `src/llm/__init__.py` | Wrap client with `RetryClient` in `create_client()` |
| `src/storage/cache.py` | **New** — `CacheStore` class, `make_cache_key()` |
| `src/storage/db.py` | Add `cache` table to `_ensure_schema()` |
| `src/analyze/summarizer.py` | Cache check before LLM, cache store after success |
| `src/analyze/__init__.py` | Create `CacheStore`, pass to `Summarizer`, thread `no_cache` |
| `src/config.py` | Add `llm_retries`, `llm_timeout`, `cache_ttl_days` |
| `src/cli.py` | Add `cache` command, `--no-cache` flag on `run`/`analyze` |
| `tests/test_retry.py` | **New** — retry logic tests |
| `tests/test_cache.py` | **New** — cache store tests |
| `tests/test_summarizer.py` | Update for cache integration |
| `tests/test_config.py` | Test new config fields |

## What stays unchanged

- Provider implementations (`gemini.py`, `openai.py`, `anthropic.py`)
- `LLMClient` Protocol interface
- `DigestBuilder` — no caching
- Database schema for articles/feeds/digests
- Delivery module
