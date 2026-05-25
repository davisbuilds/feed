"""Additional tests for src/ingest/feeds.py covering parsing helpers."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx

from src.ingest.feeds import (
    _extract_author,
    _format_http_error,
    _parse_entry_date,
    fetch_all_feeds,
    fetch_feed,
)


def test_parse_entry_date_uses_published_parsed():
    struct = time.gmtime(1_700_000_000)
    dt = _parse_entry_date({"published_parsed": struct})
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2023


def test_parse_entry_date_falls_back_to_updated_string():
    dt = _parse_entry_date({"updated": "2024-06-15T12:00:00"})
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2024


def test_parse_entry_date_returns_none_when_unparseable():
    dt = _parse_entry_date({"published": "not-a-date"})
    assert dt is None


def test_parse_entry_date_returns_none_when_missing():
    assert _parse_entry_date({}) is None


def test_extract_author_prefers_top_level_author():
    assert _extract_author({"author": "Alice"}) == "Alice"


def test_extract_author_falls_back_to_author_detail():
    assert _extract_author({"author_detail": {"name": "Bob"}}) == "Bob"


def test_extract_author_falls_back_to_authors_list():
    assert _extract_author({"authors": [{"name": "Carol"}]}) == "Carol"


def test_extract_author_unknown_when_missing():
    assert _extract_author({}) == "Unknown"


def test_format_http_error_includes_status_and_attempts():
    response = MagicMock()
    response.status_code = 503
    response.url = "https://example.com/feed"
    response.headers = {"content-type": "text/html"}
    msg = _format_http_error(response, ["503 (feed)", "503 (browser)"])
    assert "HTTP 503" in msg
    assert "503 (feed)" in msg
    assert "content-type" in msg


@patch("src.ingest.feeds.httpx.get")
def test_fetch_feed_handles_generic_exception(mock_get):
    mock_get.side_effect = RuntimeError("boom")

    result = fetch_feed(feed_url="https://example.com/feed", feed_name="x")

    assert result.success is False
    assert "boom" in (result.error or "")


@patch("src.ingest.feeds.httpx.get")
def test_fetch_feed_handles_generic_http_error(mock_get):
    mock_get.side_effect = httpx.HTTPError("conn-reset")

    result = fetch_feed(feed_url="https://example.com/feed", feed_name="x")

    assert result.success is False
    assert "conn-reset" in (result.error or "")


@patch("src.ingest.feeds.httpx.get")
def test_fetch_feed_returns_articles_within_lookback(mock_get):
    recent = datetime.now(UTC) - timedelta(hours=1)
    pub_str = recent.strftime("%a, %d %b %Y %H:%M:%S +0000")
    rss = f"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>My Feed</title>
        <item>
          <title>Hello</title>
          <link>https://example.com/post-1</link>
          <pubDate>{pub_str}</pubDate>
          <author>writer@example.com (Writer)</author>
        </item>
      </channel>
    </rss>
    """.strip().encode()

    resp = MagicMock()
    resp.status_code = 200
    resp.url = "https://example.com/feed"
    resp.headers = {"content-type": "application/rss+xml"}
    resp.content = rss
    mock_get.return_value = resp

    result = fetch_feed(
        feed_url="https://example.com/feed",
        feed_name="MyFeed",
        lookback_hours=48,
    )

    assert result.success is True
    assert len(result.articles) == 1
    assert result.articles[0].title == "Hello"
    assert result.feed_name == "My Feed"


@patch("src.ingest.feeds.httpx.get")
def test_fetch_feed_filters_old_articles(mock_get):
    old = datetime.now(UTC) - timedelta(days=30)
    pub_str = old.strftime("%a, %d %b %Y %H:%M:%S +0000")
    rss = f"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Old Feed</title>
        <item>
          <title>Ancient</title>
          <link>https://example.com/ancient</link>
          <pubDate>{pub_str}</pubDate>
        </item>
      </channel>
    </rss>
    """.strip().encode()

    resp = MagicMock()
    resp.status_code = 200
    resp.url = "https://example.com/feed"
    resp.headers = {"content-type": "application/rss+xml"}
    resp.content = rss
    mock_get.return_value = resp

    result = fetch_feed(
        feed_url="https://example.com/feed",
        feed_name="OldFeed",
        lookback_hours=24,
    )

    assert result.success is True
    assert result.articles == []


@patch("src.ingest.feeds.httpx.get")
def test_fetch_feed_skips_entries_without_link(mock_get):
    recent = datetime.now(UTC) - timedelta(hours=1)
    pub_str = recent.strftime("%a, %d %b %Y %H:%M:%S +0000")
    rss = f"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>NoLink</title>
        <item>
          <title>No Link Article</title>
          <pubDate>{pub_str}</pubDate>
        </item>
      </channel>
    </rss>
    """.strip().encode()

    resp = MagicMock()
    resp.status_code = 200
    resp.url = "https://example.com/feed"
    resp.headers = {"content-type": "application/rss+xml"}
    resp.content = rss
    mock_get.return_value = resp

    result = fetch_feed(feed_url="https://example.com/feed", feed_name="NoLink")
    assert result.success is True
    assert result.articles == []


@patch("src.ingest.feeds.fetch_feed")
def test_fetch_all_feeds_warns_on_missing_url(mock_fetch):
    """Feeds without 'url' should be skipped, no fetch attempted."""
    cfg = {
        "good": {"url": "https://example.com/feed", "category": "x"},
        "broken": {"category": "x"},
    }
    mock_fetch.return_value = MagicMock(
        feed_url="https://example.com/feed",
        feed_name="good",
        articles=[],
        success=True,
        error=None,
    )

    results = fetch_all_feeds(cfg, lookback_hours=24, max_articles_per_feed=5)

    assert mock_fetch.call_count == 1
    assert len(results) == 1


@patch("src.ingest.feeds.fetch_feed")
def test_fetch_all_feeds_captures_top_level_exception(mock_fetch):
    """If fetch_feed raises, fetch_all_feeds should wrap it as a FeedResult."""
    cfg = {"a": {"url": "https://example.com/a"}}
    mock_fetch.side_effect = RuntimeError("inner-boom")

    results = fetch_all_feeds(cfg, lookback_hours=24, max_articles_per_feed=5)

    assert len(results) == 1
    assert results[0].success is False
    assert "inner-boom" in (results[0].error or "")
