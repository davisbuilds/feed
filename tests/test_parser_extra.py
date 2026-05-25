"""Additional tests for src/ingest/parser.py to exercise fetch + process paths."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx

from src.ingest.parser import (
    clean_text,
    extract_text_content,
    fetch_article_content,
    process_articles,
)
from src.models import Article


def _article(url: str = "https://example.com/a") -> Article:
    return Article(
        id="aid",
        url=url,
        title="Title",
        feed_name="Feed",
        feed_url="https://example.com/feed",
        published=datetime.now(UTC),
    )


def test_clean_text_strips_unicode_whitespace():
    text = "a\xa0b\u2003c"
    assert clean_text(text) == "a b c"


def test_clean_text_strips_trailing_spaces():
    text = "  hello  \n\n  "
    assert clean_text(text) == "hello"


def test_clean_text_removes_unsubscribe_and_view_in_browser():
    text = "Cool article. Unsubscribe. View in browser if needed."
    cleaned = clean_text(text)
    assert "Unsubscribe" not in cleaned
    assert "View in browser" not in cleaned


def test_extract_text_content_prefers_substack_body_markup():
    html = """
    <html><body>
      <header>SITE HEADER</header>
      <div class="body markup">
        <p>Real article content here</p>
        <h2>Section</h2>
        <blockquote>quoted line</blockquote>
      </div>
      <footer>FOOTER</footer>
    </body></html>
    """
    content = extract_text_content(html)
    assert "Real article content here" in content
    assert "## Section" in content
    assert "> quoted line" in content
    assert "SITE HEADER" not in content
    assert "FOOTER" not in content


def test_extract_text_content_falls_back_to_body_when_no_known_container():
    html = "<html><body><p>Just a paragraph</p></body></html>"
    content = extract_text_content(html)
    assert "Just a paragraph" in content


def test_extract_text_content_picks_wordpress_entry_content():
    html = """
    <html><body>
      <div class="entry-content"><p>WP body content</p></div>
    </body></html>
    """
    content = extract_text_content(html)
    assert "WP body content" in content


def test_extract_text_content_finds_main():
    html = "<html><body><main><p>Main element content</p></main></body></html>"
    assert "Main element content" in extract_text_content(html)


@patch("src.ingest.parser.httpx.get")
def test_fetch_article_content_populates_word_count(mock_get):
    mock_response = MagicMock()
    mock_response.text = (
        "<html><body><article><p>" + " ".join(["word"] * 60) + "</p></article></body></html>"
    )
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    article = fetch_article_content(_article())

    assert article.word_count >= 60
    assert "word" in article.content


@patch("src.ingest.parser.httpx.get")
def test_fetch_article_content_returns_article_on_http_error(mock_get):
    mock_get.side_effect = httpx.HTTPError("boom")

    article = fetch_article_content(_article())

    assert article.word_count == 0
    assert article.content == ""


@patch("src.ingest.parser.httpx.get")
def test_fetch_article_content_returns_article_on_unknown_error(mock_get):
    mock_get.side_effect = RuntimeError("explode")

    article = fetch_article_content(_article())

    assert article.word_count == 0
    assert article.content == ""


@patch("src.ingest.parser.fetch_article_content")
def test_process_articles_drops_low_word_count(mock_fetch):
    def _short(article):
        article.content = "tiny"
        article.word_count = 5
        return article

    mock_fetch.side_effect = _short
    articles = [_article("https://example.com/1"), _article("https://example.com/2")]

    processed = process_articles(articles, fetch_content=True, min_word_count=50)

    assert processed == []


def test_process_articles_keeps_articles_above_threshold():
    # Pre-populate word_count so we don't need network fetch
    a = _article()
    a.content = " ".join(["w"] * 80)
    a.word_count = 80
    processed = process_articles([a], fetch_content=False)
    assert len(processed) == 1


def test_process_articles_empty_input_returns_empty():
    assert process_articles([], fetch_content=False) == []
