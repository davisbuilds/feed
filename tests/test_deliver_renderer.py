"""Tests for email template rendering."""

from datetime import UTC, datetime

from src.deliver.renderer import EmailRenderer
from src.models import Article, CategoryDigest, DailyDigest


def make_sample_digest() -> DailyDigest:
    """Build a small digest payload for template assertions."""
    article = Article(
        id="article-1",
        url="https://example.com/article",
        title="AI Infrastructure Trends",
        author="Jane Doe",
        feed_name="Example Feed",
        feed_url="https://example.com/feed.xml",
        published=datetime(2026, 2, 21, 8, 30, tzinfo=UTC),
        summary="Cloud and model-serving stacks are consolidating.",
        key_takeaways=["Inference costs are dropping."],
    )

    category = CategoryDigest(
        name="Technology",
        article_count=1,
        articles=[article],
        synthesis="Teams are standardizing around fewer model runtimes.",
        top_takeaways=["Infrastructure spend is moving toward inference."],
    )

    return DailyDigest(
        id="digest-2026-02-21",
        date=datetime(2026, 2, 21, 9, 0, tzinfo=UTC),
        categories=[category],
        total_articles=1,
        total_feeds=1,
        processing_time_seconds=1.2,
        overall_themes=["Inference efficiency"],
    )


def test_render_html_includes_dark_mode_meta_tags() -> None:
    renderer = EmailRenderer()
    html = renderer.render_html(make_sample_digest(), "Digest Subject")

    assert '<meta name="color-scheme" content="dark light" />' in html
    assert '<meta name="supported-color-schemes" content="dark light" />' in html


def test_render_html_uses_dark_theme_palette() -> None:
    renderer = EmailRenderer()
    html = renderer.render_html(make_sample_digest(), "Digest Subject")

    assert "background-color: #020617" in html
    assert "background-color: #111827" in html
    assert "background-color: #332701" in html
    assert "color: #f8fafc" in html
    assert "color: #94a3b8" in html
