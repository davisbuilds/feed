"""Tests for the ingestion module."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from src.models import Article, ArticleStatus
from src.storage.db import Database
from src.ingest.feeds import generate_article_id, fetch_feed
from src.ingest.parser import clean_text, extract_text_content


class TestArticleId:
    """Tests for article ID generation."""
    
    def test_same_url_same_id(self):
        """Same URL should produce same ID."""
        url = "https://example.com/article"
        assert generate_article_id(url) == generate_article_id(url)
    
    def test_different_url_different_id(self):
        """Different URLs should produce different IDs."""
        url1 = "https://example.com/article1"
        url2 = "https://example.com/article2"
        assert generate_article_id(url1) != generate_article_id(url2)
    
    def test_id_length(self):
        """ID should be 16 characters."""
        url = "https://example.com/article"
        assert len(generate_article_id(url)) == 16


class TestDatabase:
    """Tests for database operations."""
    
    @pytest.fixture
    def db(self):
        """Create a temporary database."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield Database(db_path)
    
    def test_article_not_exists(self, db):
        """Non-existent article should return False."""
        assert not db.article_exists("nonexistent")
    
    def test_save_and_check_exists(self, db):
        """Saved article should exist."""
        article = Article(
            id="test123",
            url="https://example.com/test",
            title="Test Article",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(timezone.utc),
        )
        
        assert db.save_article(article) is True
        assert db.article_exists("test123")
    
    def test_save_duplicate_returns_false(self, db):
        """Saving duplicate should return False."""
        article = Article(
            id="test123",
            url="https://example.com/test",
            title="Test Article",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(timezone.utc),
        )
        
        assert db.save_article(article) is True
        assert db.save_article(article) is False


class TestTextCleaning:
    """Tests for text cleaning."""
    
    def test_removes_excessive_whitespace(self):
        """Should normalize whitespace."""
        text = "Hello    world"
        assert clean_text(text) == "Hello world"
    
    def test_removes_excessive_newlines(self):
        """Should reduce multiple newlines."""
        text = "Hello\n\n\n\nWorld"
        assert clean_text(text) == "Hello\n\nWorld"
    
    def test_removes_newsletter_artifacts(self):
        """Should remove common newsletter text."""
        text = "Great content here. Subscribe to our newsletter for more."
        cleaned = clean_text(text)
        assert "Subscribe" not in cleaned


class TestContentExtraction:
    """Tests for HTML content extraction."""
    
    def test_extracts_paragraph_text(self):
        """Should extract text from paragraphs."""
        html = "<html><body><p>Hello World</p></body></html>"
        content = extract_text_content(html)
        assert "Hello World" in content
    
    def test_removes_scripts(self):
        """Should remove script content."""
        html = "<html><body><script>alert('bad')</script><p>Good</p></body></html>"
        content = extract_text_content(html)
        assert "alert" not in content
        assert "Good" in content
    
    def test_preserves_headings(self):
        """Should mark headings."""
        html = "<html><body><h2>Title</h2><p>Content</p></body></html>"
        content = extract_text_content(html)
        assert "## Title" in content
