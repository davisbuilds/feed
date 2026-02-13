# Caching & Retry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add LLM retry with exponential backoff and response caching so the pipeline is resilient to transient failures and doesn't waste API credits on repeat runs.

**Architecture:** A `RetryClient` wrapper decorates any `LLMClient` with retry logic. A `CacheStore` backed by a new `cache` table in the existing SQLite DB stores article summaries keyed on `sha256(article_id:model)`. Both integrate at the `Summarizer` layer.

**Tech Stack:** Python 3.12, SQLite (WAL), Pydantic Settings, Typer, pytest

**Design doc:** `docs/plans/2026-02-12-caching-retry-design.md`

---

### Task 1: Config — Add retry, timeout, and cache settings

**Files:**
- Modify: `src/config.py:16-67` (Settings class)
- Test: `tests/test_config.py`

**Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_settings_retry_defaults(monkeypatch) -> None:
    """Retry and cache settings should have sensible defaults."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("RESEND_API_KEY", "resend-key")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")

    settings = Settings()

    assert settings.llm_retries == 2
    assert settings.llm_timeout == 120
    assert settings.cache_ttl_days == 7


def test_settings_retry_custom_values(monkeypatch) -> None:
    """Retry and cache settings should be configurable via env vars."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("RESEND_API_KEY", "resend-key")
    monkeypatch.setenv("EMAIL_FROM", "from@example.com")
    monkeypatch.setenv("EMAIL_TO", "to@example.com")
    monkeypatch.setenv("LLM_RETRIES", "4")
    monkeypatch.setenv("LLM_TIMEOUT", "60")
    monkeypatch.setenv("CACHE_TTL_DAYS", "14")

    settings = Settings()

    assert settings.llm_retries == 4
    assert settings.llm_timeout == 60
    assert settings.cache_ttl_days == 14
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py::test_settings_retry_defaults tests/test_config.py::test_settings_retry_custom_values -v`
Expected: FAIL — `Settings` has no `llm_retries` attribute

**Step 3: Add fields to Settings**

In `src/config.py`, add after the `max_tokens_per_summary` field (line 59):

```python
    # Retry & cache
    llm_retries: int = Field(default=2, ge=0, le=5, description="Max LLM retry attempts")
    llm_timeout: int = Field(default=120, ge=10, description="LLM timeout in seconds")
    cache_ttl_days: int = Field(default=7, ge=1, description="Cache TTL in days")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add retry, timeout, and cache config fields"
```

---

### Task 2: RetryClient — Wrapping decorator with exponential backoff

**Files:**
- Create: `src/llm/retry.py`
- Test: `tests/test_retry.py`

**Step 1: Write the failing tests**

Create `tests/test_retry.py`:

```python
"""Tests for LLM retry logic."""

import time

import pytest

from src.llm.base import LLMError, LLMResponse
from src.llm.retry import RetryClient, _is_retryable


class FakeClient:
    """Fake LLM client that can be configured to fail."""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.call_count = 0

    def generate(self, prompt, system, response_schema):
        self.call_count += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


OK_RESPONSE = LLMResponse(
    parsed={"summary": "ok"},
    raw_text="{}",
    input_tokens=10,
    output_tokens=5,
)


class TestIsRetryable:
    def test_timeout_is_retryable(self):
        assert _is_retryable(LLMError("request timed out")) is True

    def test_deadline_exceeded_is_retryable(self):
        assert _is_retryable(LLMError("deadline exceeded")) is True

    def test_rate_limit_429_is_retryable(self):
        assert _is_retryable(LLMError("429 Too Many Requests")) is True

    def test_server_error_500_is_retryable(self):
        assert _is_retryable(LLMError("500 Internal Server Error")) is True

    def test_server_error_503_is_retryable(self):
        assert _is_retryable(LLMError("503 Service Unavailable")) is True

    def test_overloaded_529_is_retryable(self):
        assert _is_retryable(LLMError("529 overloaded")) is True

    def test_auth_error_not_retryable(self):
        assert _is_retryable(LLMError("401 Unauthorized")) is False

    def test_parse_error_not_retryable(self):
        assert _is_retryable(LLMError("response parsing failed")) is False

    def test_unknown_error_not_retryable(self):
        assert _is_retryable(LLMError("something unexpected")) is False


class TestRetryClient:
    def test_success_no_retry(self):
        inner = FakeClient([OK_RESPONSE])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        result = client.generate("prompt", "system", object)

        assert result.parsed == {"summary": "ok"}
        assert inner.call_count == 1

    def test_retries_on_retryable_error_then_succeeds(self):
        inner = FakeClient([
            LLMError("request timed out"),
            OK_RESPONSE,
        ])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        result = client.generate("prompt", "system", object)

        assert result.parsed == {"summary": "ok"}
        assert inner.call_count == 2

    def test_raises_after_max_retries_exhausted(self):
        inner = FakeClient([
            LLMError("request timed out"),
            LLMError("request timed out"),
            LLMError("request timed out"),
        ])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        with pytest.raises(LLMError, match="timed out"):
            client.generate("prompt", "system", object)

        assert inner.call_count == 3  # initial + 2 retries

    def test_non_retryable_error_fails_immediately(self):
        inner = FakeClient([LLMError("401 Unauthorized")])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        with pytest.raises(LLMError, match="401"):
            client.generate("prompt", "system", object)

        assert inner.call_count == 1

    def test_zero_retries_means_no_retry(self):
        inner = FakeClient([LLMError("request timed out")])
        client = RetryClient(inner, max_retries=0, base_delay=0.01)

        with pytest.raises(LLMError, match="timed out"):
            client.generate("prompt", "system", object)

        assert inner.call_count == 1

    def test_backoff_delay_increases(self):
        inner = FakeClient([
            LLMError("request timed out"),
            LLMError("request timed out"),
            OK_RESPONSE,
        ])
        client = RetryClient(inner, max_retries=2, base_delay=0.05)

        start = time.monotonic()
        client.generate("prompt", "system", object)
        elapsed = time.monotonic() - start

        # base_delay=0.05: first wait 0.05, second wait 0.10 = 0.15 total minimum
        assert elapsed >= 0.12  # allow some slack
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_retry.py -v`
Expected: FAIL — `src.llm.retry` does not exist

**Step 3: Implement RetryClient**

Create `src/llm/retry.py`:

```python
"""LLM client wrapper with retry and exponential backoff."""

import re
import time

from pydantic import BaseModel

from src.llm.base import LLMClient, LLMError, LLMResponse
from src.logging_config import get_logger

logger = get_logger("llm.retry")

# Patterns that indicate a retryable error
_RETRYABLE_PATTERNS = re.compile(
    r"timed?\s*out|deadline exceeded|"
    r"\b429\b|\brate.?limit|"
    r"\b500\b|\b502\b|\b503\b|\b529\b|"
    r"overloaded|unavailable",
    re.IGNORECASE,
)


def _is_retryable(error: LLMError) -> bool:
    """Check if an LLM error is worth retrying."""
    return bool(_RETRYABLE_PATTERNS.search(str(error)))


class RetryClient:
    """Wraps an LLMClient with retry logic and exponential backoff."""

    def __init__(
        self,
        inner: LLMClient,
        max_retries: int = 2,
        base_delay: float = 1.0,
    ):
        self.inner = inner
        self.max_retries = max_retries
        self.base_delay = base_delay

    def generate(
        self,
        prompt: str,
        system: str,
        response_schema: type[BaseModel],
    ) -> LLMResponse:
        """Generate with retry on transient failures."""
        for attempt in range(self.max_retries + 1):
            try:
                return self.inner.generate(prompt, system, response_schema)
            except LLMError as exc:
                if not _is_retryable(exc) or attempt == self.max_retries:
                    raise
                delay = self.base_delay * (2**attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s: {exc}"
                )
                time.sleep(delay)
        raise LLMError("Unexpected: retry loop exited without return or raise")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_retry.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/llm/retry.py tests/test_retry.py
git commit -m "feat: add RetryClient with exponential backoff"
```

---

### Task 3: Integrate RetryClient into create_client factory

**Files:**
- Modify: `src/llm/__init__.py`
- Test: `tests/test_llm.py`

**Step 1: Write the failing test**

Add to `tests/test_llm.py`:

```python
from src.llm.retry import RetryClient


def test_create_client_wraps_with_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should wrap provider client with RetryClient."""
    module = ModuleType("src.llm.gemini")
    module.GeminiClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "src.llm.gemini", module)

    client = create_client(provider="gemini", api_key="test-key")

    assert isinstance(client, RetryClient)
    assert isinstance(client.inner, _DummyClient)


def test_create_client_passes_retry_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should pass max_retries to RetryClient."""
    module = ModuleType("src.llm.gemini")
    module.GeminiClient = _DummyClient
    monkeypatch.setitem(__import__("sys").modules, "src.llm.gemini", module)

    client = create_client(provider="gemini", api_key="test-key", max_retries=5)

    assert isinstance(client, RetryClient)
    assert client.max_retries == 5
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm.py::test_create_client_wraps_with_retry tests/test_llm.py::test_create_client_passes_retry_config -v`
Expected: FAIL — `create_client` doesn't accept `max_retries` / doesn't return `RetryClient`

**Step 3: Update create_client**

Modify `src/llm/__init__.py`:

```python
"""LLM provider factory and shared exports."""

from typing import Literal

from .base import LLMClient, LLMError, LLMResponse
from .retry import RetryClient

Provider = Literal["gemini", "openai", "anthropic"]

PROVIDER_DEFAULTS: dict[Provider, str] = {
    "gemini": "gemini-3-flash-preview",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


def create_client(
    provider: Provider,
    api_key: str,
    model: str | None = None,
    max_retries: int = 2,
) -> RetryClient:
    """Create an LLM client for the given provider, wrapped with retry logic."""
    if provider not in PROVIDER_DEFAULTS:
        raise LLMError(f"Unknown LLM provider: {provider}")

    resolved_model = model or PROVIDER_DEFAULTS[provider]

    try:
        match provider:
            case "gemini":
                from .gemini import GeminiClient

                inner = GeminiClient(api_key=api_key, model=resolved_model)
            case "openai":
                from .openai import OpenAIClient

                inner = OpenAIClient(api_key=api_key, model=resolved_model)
            case "anthropic":
                from .anthropic import AnthropicClient

                inner = AnthropicClient(api_key=api_key, model=resolved_model)
    except ImportError as exc:
        raise LLMError(
            f"Missing dependency for provider '{provider}'. "
            f"Install the '{provider}' extra to continue."
        ) from exc

    return RetryClient(inner, max_retries=max_retries)


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "PROVIDER_DEFAULTS",
    "Provider",
    "RetryClient",
    "create_client",
]
```

**Step 4: Run all LLM tests to verify they pass**

Run: `uv run pytest tests/test_llm.py tests/test_retry.py -v`
Expected: All PASS. Existing tests still pass because `RetryClient` delegates `generate()` to the inner client.

**Step 5: Run full test suite to check for regressions**

Run: `uv run pytest -v`
Expected: All PASS. The `test_analyze.py` tests use `Mock()` clients passed directly to `Summarizer(client=mock_client)`, so they bypass the factory and aren't affected.

**Step 6: Commit**

```bash
git add src/llm/__init__.py tests/test_llm.py
git commit -m "feat: integrate RetryClient into create_client factory"
```

---

### Task 4: CacheStore — SQLite-backed cache with TTL

**Files:**
- Create: `src/storage/cache.py`
- Modify: `src/storage/db.py:31-84` (add cache table to schema)
- Test: `tests/test_cache.py`

**Step 1: Write the failing tests**

Create `tests/test_cache.py`:

```python
"""Tests for the response cache."""

import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.storage.cache import CacheStore, make_cache_key


class TestMakeCacheKey:
    def test_deterministic(self):
        k1 = make_cache_key("article-1", "gemini-flash")
        k2 = make_cache_key("article-1", "gemini-flash")
        assert k1 == k2

    def test_different_article_different_key(self):
        k1 = make_cache_key("article-1", "gemini-flash")
        k2 = make_cache_key("article-2", "gemini-flash")
        assert k1 != k2

    def test_different_model_different_key(self):
        k1 = make_cache_key("article-1", "gemini-flash")
        k2 = make_cache_key("article-1", "gpt-4o-mini")
        assert k1 != k2

    def test_key_is_hex_string(self):
        key = make_cache_key("article-1", "gemini-flash")
        assert len(key) == 64  # SHA256 hex digest
        int(key, 16)  # should not raise


class TestCacheStore:
    @pytest.fixture
    def cache(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield CacheStore(db_path, default_ttl_days=7)

    def test_get_missing_returns_none(self, cache):
        assert cache.get("summary", "nonexistent") is None

    def test_set_then_get(self, cache):
        data = {"summary": "test", "key_takeaways": ["a"]}
        cache.set("summary", "key1", data)

        result = cache.get("summary", "key1")

        assert result == data

    def test_get_expired_returns_none(self, cache):
        """Expired entries should not be returned."""
        data = {"summary": "old"}
        cache.set("summary", "key1", data, ttl_days=-1)  # already expired

        assert cache.get("summary", "key1") is None

    def test_different_kinds_are_separate(self, cache):
        cache.set("summary", "key1", {"a": 1})
        cache.set("other", "key1", {"b": 2})

        assert cache.get("summary", "key1") == {"a": 1}
        assert cache.get("other", "key1") == {"b": 2}

    def test_set_overwrites_existing(self, cache):
        cache.set("summary", "key1", {"v": 1})
        cache.set("summary", "key1", {"v": 2})

        assert cache.get("summary", "key1") == {"v": 2}

    def test_clear_all(self, cache):
        cache.set("summary", "k1", {"a": 1})
        cache.set("summary", "k2", {"b": 2})

        count = cache.clear()

        assert count == 2
        assert cache.get("summary", "k1") is None
        assert cache.get("summary", "k2") is None

    def test_clear_by_kind(self, cache):
        cache.set("summary", "k1", {"a": 1})
        cache.set("other", "k2", {"b": 2})

        count = cache.clear(kind="summary")

        assert count == 1
        assert cache.get("summary", "k1") is None
        assert cache.get("other", "k2") == {"b": 2}

    def test_stats(self, cache):
        cache.set("summary", "k1", {"a": 1})
        cache.set("summary", "k2", {"b": 2})
        cache.set("summary", "k3", {"c": 3}, ttl_days=-1)  # expired

        stats = cache.stats()

        assert stats["total_entries"] == 3
        assert stats["expired_entries"] == 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cache.py -v`
Expected: FAIL — `src.storage.cache` does not exist

**Step 3: Add cache table to DB schema**

In `src/storage/db.py`, add inside `_ensure_schema()` after the `digests` table (before the closing `"""`):

```sql
                -- Response cache with TTL
                CREATE TABLE IF NOT EXISTS cache (
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (kind, key)
                );
```

**Step 4: Implement CacheStore**

Create `src/storage/cache.py`:

```python
"""SQLite-backed response cache with TTL."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

from src.logging_config import get_logger

logger = get_logger("cache")


def make_cache_key(article_id: str, model: str) -> str:
    """Build a deterministic cache key from article ID and model name."""
    raw = f"{article_id}:{model}"
    return hashlib.sha256(raw.encode()).hexdigest()


class CacheStore:
    """SQLite-backed cache with TTL expiration."""

    def __init__(self, db_path: Path, default_ttl_days: int = 7):
        self.db_path = db_path
        self.default_ttl_days = default_ttl_days
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS cache (
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (kind, key)
                );
            """)

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, kind: str, key: str) -> dict[str, Any] | None:
        """Get a cached value. Returns None if missing or expired."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM cache WHERE kind = ? AND key = ? AND expires_at > ?",
                (kind, key, now),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def set(
        self,
        kind: str,
        key: str,
        value: dict[str, Any],
        ttl_days: int | None = None,
    ) -> None:
        """Store a value with TTL. Overwrites existing entries."""
        ttl = ttl_days if ttl_days is not None else self.default_ttl_days
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl)
        with self._connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache (kind, key, value, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (kind, key, json.dumps(value), expires_at.isoformat()),
            )
            # Lazy cleanup of expired rows
            conn.execute(
                "DELETE FROM cache WHERE expires_at <= ?",
                (datetime.now(timezone.utc).isoformat(),),
            )

    def clear(self, kind: str | None = None) -> int:
        """Delete cached entries. Returns count deleted."""
        with self._connection() as conn:
            if kind:
                cursor = conn.execute("DELETE FROM cache WHERE kind = ?", (kind,))
            else:
                cursor = conn.execute("DELETE FROM cache")
            return cursor.rowcount

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at <= ?", (now,)
            ).fetchone()[0]
        return {
            "total_entries": total,
            "expired_entries": expired,
        }
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cache.py -v`
Expected: All PASS

**Step 6: Run full suite to check for regressions**

Run: `uv run pytest -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/storage/cache.py src/storage/db.py tests/test_cache.py
git commit -m "feat: add CacheStore with TTL and lazy expiration"
```

---

### Task 5: Integrate cache into Summarizer and run_analysis

**Files:**
- Modify: `src/analyze/summarizer.py`
- Modify: `src/analyze/__init__.py`
- Test: `tests/test_analyze.py`

**Step 1: Write the failing tests**

Add to `tests/test_analyze.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from src.storage.cache import CacheStore, make_cache_key


class TestSummarizerCache:
    """Tests for cache integration in Summarizer."""

    @pytest.fixture
    def cache(self):
        with TemporaryDirectory() as tmpdir:
            yield CacheStore(Path(tmpdir) / "test.db")

    def test_cache_hit_skips_llm_call(self, sample_article: Article, cache) -> None:
        """Cached summaries should be returned without calling LLM."""
        mock_client = Mock()
        model_name = "gemini-3-flash-preview"
        key = make_cache_key(sample_article.id, model_name)
        cached_data = {
            "success": True,
            "article_id": sample_article.id,
            "summary": "cached summary",
            "key_takeaways": ["cached insight"],
            "action_items": [],
            "tokens_used": 100,
            "error": None,
        }
        cache.set("summary", key, cached_data)

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(
            sample_article, cache=cache, model_name=model_name
        )

        assert result["summary"] == "cached summary"
        assert result["key_takeaways"] == ["cached insight"]
        mock_client.generate.assert_not_called()

    def test_cache_miss_calls_llm_and_stores(self, sample_article: Article, cache) -> None:
        """Cache miss should call LLM and store the result."""
        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "summary": "fresh summary",
                "key_takeaways": ["new"],
                "action_items": [],
                "topics": ["AI"],
                "sentiment": "neutral",
                "importance": 3,
            },
            raw_text="{}",
            input_tokens=100,
            output_tokens=50,
        )
        model_name = "gemini-3-flash-preview"
        key = make_cache_key(sample_article.id, model_name)

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(
            sample_article, cache=cache, model_name=model_name
        )

        assert result["summary"] == "fresh summary"
        mock_client.generate.assert_called_once()

        # Verify it was stored
        cached = cache.get("summary", key)
        assert cached is not None
        assert cached["summary"] == "fresh summary"

    def test_no_cache_still_works(self, sample_article: Article) -> None:
        """Summarizer should work without a cache (backward compatible)."""
        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "summary": "normal summary",
                "key_takeaways": [],
                "action_items": [],
                "topics": [],
                "sentiment": "neutral",
                "importance": 3,
            },
            raw_text="{}",
            input_tokens=10,
            output_tokens=5,
        )

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is True
        assert result["summary"] == "normal summary"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analyze.py::TestSummarizerCache -v`
Expected: FAIL — `summarize_article()` doesn't accept `cache`/`model_name`

**Step 3: Update Summarizer.summarize_article**

Modify `src/analyze/summarizer.py`. Change the `summarize_article` method signature and add cache logic:

```python
    def summarize_article(
        self,
        article: Article,
        cache: "CacheStore | None" = None,
        model_name: str | None = None,
    ) -> SummaryResult:
        """Generate a summary for a single article."""
        # Check cache first
        if cache and model_name:
            from src.storage.cache import make_cache_key

            cache_key = make_cache_key(article.id, model_name)
            cached = cache.get("summary", cache_key)
            if cached is not None:
                logger.info(f"Cache hit: {article.title[:50]}...")
                return SummaryResult(**cached)
        else:
            cache_key = None

        logger.info(f"Summarizing: {article.title[:50]}...")

        content = article.content
        if len(content) > 30000:
            content = content[:30000] + "\n\n[Content truncated...]"

        user_prompt = ARTICLE_SUMMARY_USER.format(
            title=article.title,
            author=article.author,
            feed_name=article.feed_name,
            published=article.published.strftime("%Y-%m-%d"),
            content=content,
        )

        try:
            response = self.client.generate(
                prompt=user_prompt,
                system=ARTICLE_SUMMARY_SYSTEM,
                response_schema=ArticleSummaryResponse,
            )
            parsed = response.parsed
            tokens_used = response.input_tokens + response.output_tokens

            logger.debug(f"Summary generated ({tokens_used} tokens)")
            result = SummaryResult(
                success=True,
                article_id=article.id,
                summary=parsed.get("summary"),
                key_takeaways=parsed.get("key_takeaways", []),
                action_items=parsed.get("action_items", []),
                tokens_used=tokens_used,
                error=None,
            )

            # Store in cache on success
            if cache and cache_key:
                cache.set("summary", cache_key, dict(result))

            return result

        except Exception as exc:
            logger.error(f"Summarization error: {exc}")
            return SummaryResult(
                success=False,
                article_id=article.id,
                summary=None,
                key_takeaways=[],
                action_items=[],
                tokens_used=0,
                error=str(exc),
            )
```

Also update `summarize_batch` to pass `cache` and `model_name` through:

```python
    def summarize_batch(
        self,
        articles: list[Article],
        on_progress: Callable[[int, int, Article], None] | None = None,
        cache: "CacheStore | None" = None,
        model_name: str | None = None,
    ) -> list[SummaryResult]:
        """Summarize multiple articles concurrently."""
        if not articles:
            return []

        results: list[SummaryResult] = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_article = {
                executor.submit(
                    self.summarize_article, article, cache, model_name
                ): article
                for article in articles
            }
            # ... rest unchanged ...
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_analyze.py -v`
Expected: All PASS (new cache tests + existing tests still pass)

**Step 5: Update run_analysis to create and pass CacheStore**

Modify `src/analyze/__init__.py`. Add `no_cache` parameter and wire up `CacheStore`:

```python
def run_analysis(
    db: Database | None = None,
    lookback_hours: int | None = None,
    no_cache: bool = False,
) -> AnalysisResult:
    """Run the full analysis pipeline."""
    import time

    start_time = time.time()

    settings = get_settings()
    lookback_hours = lookback_hours or settings.lookback_hours
    provider = settings.llm_provider
    api_key = settings.llm_api_key
    model = settings.llm_model

    errors: list[str] = []
    total_tokens = 0

    if db is None:
        db = Database(settings.data_dir / "articles.db")

    # Set up cache unless disabled
    cache = None
    if not no_cache:
        from src.storage.cache import CacheStore

        cache = CacheStore(
            db_path=settings.data_dir / "articles.db",
            default_ttl_days=settings.cache_ttl_days,
        )

    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    articles = db.get_articles_since(since, status=ArticleStatus.PENDING)

    if not articles:
        logger.info("No pending articles to analyze")
        return AnalysisResult(
            digest=None,
            articles_analyzed=0,
            tokens_used=0,
            cost_estimate_usd=0.0,
            duration_seconds=time.time() - start_time,
            errors=[],
        )

    logger.info(f"Analyzing {len(articles)} articles")

    llm_client = create_client(
        provider=provider,
        api_key=api_key,
        model=model,
        max_retries=settings.llm_retries,
    )
    summarizer = Summarizer(client=llm_client)
    digest_builder = DigestBuilder(client=llm_client)

    summarized_articles: list[Article] = []

    def on_progress(i: int, total: int, article: Article) -> None:
        logger.info(f"[{i + 1}/{total}] {article.title[:40]}...")

    summary_results = summarizer.summarize_batch(
        articles,
        on_progress=on_progress,
        cache=cache,
        model_name=model,
    )

    # ... rest of function unchanged from line 86 onward ...
```

**Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/analyze/summarizer.py src/analyze/__init__.py tests/test_analyze.py
git commit -m "feat: integrate cache into summarizer and analysis pipeline"
```

---

### Task 6: CLI — Add cache command and --no-cache flag

**Files:**
- Modify: `src/cli.py`

**Step 1: Add `--no-cache` flag to `run` and `analyze` commands**

In `src/cli.py`, update the `run` command signature:

```python
@app.command()
def run(
    send: bool = typer.Option(False, "--send", help="Send email instead of terminal output"),
    output_format: str = FormatChoice,
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache, re-summarize all"),
) -> None:
```

And thread it through to `run_analysis`:

```python
            analysis_result = run_analysis(db=db, no_cache=no_cache)
```

Same for `analyze`:

```python
@app.command()
def analyze(
    output_format: str | None = typer.Option(
        None, "--format", "-f", help="Show digest after analysis (rich, text, or json)",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache, re-summarize all"),
) -> None:
```

And:

```python
    result = run_analysis(db=db, no_cache=no_cache)
```

**Step 2: Add the `cache` command**

Add before the `cli()` function:

```python
@app.command("cache")
def cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Clear all cached LLM responses"),
) -> None:
    """Show cache statistics or clear cached responses."""
    settings = _load_settings()

    from src.storage.cache import CacheStore

    cache = CacheStore(
        db_path=settings.data_dir / "articles.db",
        default_ttl_days=settings.cache_ttl_days,
    )

    if clear:
        count = cache.clear()
        console.print(f"[green]Cleared {count} cached entries[/green]")
        return

    stats = cache.stats()
    table = Table(title="Cache Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total entries", str(stats["total_entries"]))
    table.add_row("Expired entries", str(stats["expired_entries"]))
    console.print(table)
```

**Step 3: Verify CLI wiring manually**

Run: `uv run feed --help`
Expected: `cache` appears in command list

Run: `uv run feed cache --help`
Expected: Shows `--clear` option

Run: `uv run feed run --help`
Expected: Shows `--no-cache` option

**Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

**Step 5: Lint**

Run: `uv run ruff check .`
Expected: No errors

**Step 6: Commit**

```bash
git add src/cli.py
git commit -m "feat: add 'feed cache' command and --no-cache flag"
```

---

### Task 7: Final integration test and cleanup

**Step 1: Run full test suite with coverage**

Run: `uv run pytest -v`
Expected: All PASS

**Step 2: Lint entire project**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: No errors

**Step 3: Verify CLI end-to-end**

Run: `uv run feed config`
Expected: Shows config including new fields without errors

Run: `uv run feed cache`
Expected: Shows cache stats table (0 entries if fresh DB)

**Step 4: Commit any final fixes**

If any lint/format changes needed:

```bash
git add -A
git commit -m "chore: lint and format cleanup"
```
