"""Tests for the analysis module."""

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from src.analyze.digest_builder import DigestBuilder
from src.analyze.summarizer import Summarizer
from src.llm.base import LLMResponse
from src.models import Article
from src.storage.cache import CacheStore, make_cache_key


@pytest.fixture
def sample_article() -> Article:
    """Create a sample article for testing."""
    return Article(
        id="test123456789012",
        url="https://example.com/test",
        title="Test Article About AI",
        author="Test Author",
        feed_name="Test Feed",
        feed_url="https://example.com/feed",
        published=datetime.now(UTC),
        content="This is a test article about artificial intelligence and its impact on society. "
        * 20,
        word_count=200,
        category="Technology",
    )


class TestSummarizer:
    """Tests for the Summarizer class."""

    def test_summarize_article_success(self, sample_article: Article) -> None:
        """Test successful article summarization."""
        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "summary": "Test summary",
                "key_takeaways": ["insight1"],
                "action_items": [],
            },
            raw_text="{}",
            input_tokens=100,
            output_tokens=50,
        )

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is True
        assert result["summary"] == "Test summary"
        assert result["key_takeaways"] == ["insight1"]
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50

    def test_summarize_article_handles_api_error(self, sample_article: Article) -> None:
        """Test handling of API errors."""
        mock_client = Mock()
        mock_client.generate.side_effect = Exception("API Error")

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is False
        assert "API Error" in (result["error"] or "")


class TestDigestBuilder:
    """Tests for the DigestBuilder class."""

    def test_groups_articles_by_category(self, sample_article: Article) -> None:
        """Test that articles are grouped correctly."""
        articles = [
            sample_article,
            Article(
                id="test456789012345",
                url="https://example.com/test2",
                title="Another Article",
                author="Another Author",
                feed_name="Another Feed",
                feed_url="https://example.com/feed2",
                published=datetime.now(UTC),
                content="Different content",
                word_count=100,
                category="Business",
                summary="Test summary",
            ),
        ]

        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "overall_themes": [],
                "must_read_overall": [],
                "cross_category_insights": [],
            },
            raw_text="{}",
            input_tokens=50,
            output_tokens=25,
        )

        builder = DigestBuilder(client=mock_client)
        digest, in_tok, out_tok = builder.build_digest(articles)

        assert len(digest.categories) == 2
        category_names = {category.name for category in digest.categories}
        assert "Technology" in category_names
        assert "Business" in category_names
        assert in_tok == 50
        assert out_tok == 25

    def test_category_insight_included_when_gate_passes(self, sample_article: Article) -> None:
        """Category insight should be included when confidence and sources pass gates."""
        second_article = Article(
            id="test222222222222",
            url="https://example.com/test-2",
            title="Second Article About AI",
            author="Test Author Two",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(UTC),
            content="More details on AI deployment patterns.",
            word_count=120,
            category="Technology",
        )

        mock_client = Mock()
        mock_client.generate.side_effect = [
            LLMResponse(
                parsed={
                    "synthesis": "Category synthesis",
                    "top_takeaways": ["Inference efficiency is becoming strategic."],
                    "non_obvious_insight": {
                        "insight": "Smaller teams are shipping faster by narrowing model scope.",
                        "why_unintuitive": (
                            "The common assumption is that more model variety "
                            "increases velocity."
                        ),
                        "confidence": 4,
                        "supporting_urls": [str(sample_article.url)],
                    },
                },
                raw_text="{}",
                input_tokens=50,
                output_tokens=25,
            ),
            LLMResponse(
                parsed={
                    "overall_themes": ["Inference efficiency"],
                    "must_read_overall": [str(sample_article.url)],
                    "cross_category_insights": [],
                },
                raw_text="{}",
                input_tokens=40,
                output_tokens=20,
            ),
        ]

        builder = DigestBuilder(client=mock_client, insights_mode="auto", insight_min_confidence=4)
        digest, _, _ = builder.build_digest([sample_article, second_article])

        assert len(digest.categories) == 1
        insight = digest.categories[0].non_obvious_insight
        assert insight is not None
        assert insight.confidence == 4
        assert str(sample_article.url) in insight.supporting_urls

    def test_category_insight_dropped_when_confidence_low(self, sample_article: Article) -> None:
        """Auto mode should drop low-confidence insights."""
        second_article = Article(
            id="test333333333333",
            url="https://example.com/test-3",
            title="Third Article About AI",
            author="Test Author Three",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(UTC),
            content="Another article for synthesis coverage.",
            word_count=110,
            category="Technology",
        )

        mock_client = Mock()
        mock_client.generate.side_effect = [
            LLMResponse(
                parsed={
                    "synthesis": "Category synthesis",
                    "top_takeaways": ["The market is standardizing quickly."],
                    "non_obvious_insight": {
                        "insight": "Cross-team experimentation has slowed despite more tooling.",
                        "why_unintuitive": (
                            "Tooling growth is usually associated with faster "
                            "experimentation."
                        ),
                        "confidence": 2,
                        "supporting_urls": [str(sample_article.url)],
                    },
                },
                raw_text="{}",
                input_tokens=50,
                output_tokens=25,
            ),
            LLMResponse(
                parsed={
                    "overall_themes": ["Standardization"],
                    "must_read_overall": [str(sample_article.url)],
                    "cross_category_insights": [],
                },
                raw_text="{}",
                input_tokens=40,
                output_tokens=20,
            ),
        ]

        builder = DigestBuilder(client=mock_client, insights_mode="auto", insight_min_confidence=4)
        digest, _, _ = builder.build_digest([sample_article, second_article])

        assert digest.categories[0].non_obvious_insight is None

    def test_category_insight_dropped_when_source_url_missing(
        self, sample_article: Article
    ) -> None:
        """Insights must reference URLs present in the category input."""
        second_article = Article(
            id="test444444444444",
            url="https://example.com/test-4",
            title="Fourth Article About AI",
            author="Test Author Four",
            feed_name="Test Feed",
            feed_url="https://example.com/feed",
            published=datetime.now(UTC),
            content="Category synthesis source check content.",
            word_count=105,
            category="Technology",
        )

        mock_client = Mock()
        mock_client.generate.side_effect = [
            LLMResponse(
                parsed={
                    "synthesis": "Category synthesis",
                    "top_takeaways": ["Model serving stacks are converging."],
                    "non_obvious_insight": {
                        "insight": "Teams are reducing complexity by owning less infrastructure.",
                        "why_unintuitive": (
                            "Engineering organizations often assume in-house ownership "
                            "improves control."
                        ),
                        "confidence": 5,
                        "supporting_urls": ["https://not-in-input.example.com/article"],
                    },
                },
                raw_text="{}",
                input_tokens=50,
                output_tokens=25,
            ),
            LLMResponse(
                parsed={
                    "overall_themes": ["Convergence"],
                    "must_read_overall": [str(sample_article.url)],
                    "cross_category_insights": [],
                },
                raw_text="{}",
                input_tokens=40,
                output_tokens=20,
            ),
        ]

        builder = DigestBuilder(client=mock_client, insights_mode="auto", insight_min_confidence=4)
        digest, _, _ = builder.build_digest([sample_article, second_article])

        assert digest.categories[0].non_obvious_insight is None

    def test_overall_insights_capped_and_must_read_filtered(self, sample_article: Article) -> None:
        """Overall insights should respect caps and source URL filtering."""
        business_article = Article(
            id="test555555555555",
            url="https://example.com/business",
            title="Business Article",
            author="Biz Author",
            feed_name="Business Feed",
            feed_url="https://example.com/business-feed",
            published=datetime.now(UTC),
            content="Business content.",
            word_count=90,
            category="Business",
            summary="Margins are tightening.",
            key_takeaways=["Cost discipline is increasing."],
        )

        tech_article = sample_article.model_copy(
            update={
                "summary": "Inference costs keep declining.",
                "key_takeaways": ["Efficiency is becoming a default requirement."],
            }
        )

        mock_client = Mock()
        mock_client.generate.return_value = LLMResponse(
            parsed={
                "overall_themes": ["Efficiency focus"],
                "must_read_overall": [
                    str(sample_article.url),
                    "https://not-in-input.example.com/ghost",
                    str(business_article.url),
                ],
                "cross_category_insights": [
                    {
                        "insight": (
                            "Cost pressure is driving model simplification across "
                            "departments."
                        ),
                        "why_unintuitive": (
                            "Product teams often treat model complexity as a sign "
                            "of progress."
                        ),
                        "confidence": 5,
                        "supporting_urls": [str(sample_article.url), str(business_article.url)],
                    },
                    {
                        "insight": "Teams are standardizing faster than their roadmaps predict.",
                        "why_unintuitive": (
                            "Roadmaps usually over-index on experimentation velocity."
                        ),
                        "confidence": 5,
                        "supporting_urls": [str(sample_article.url)],
                    },
                    {
                        "insight": (
                            "Procurement choices are setting architecture direction "
                            "earlier."
                        ),
                        "why_unintuitive": (
                            "Architecture decisions are often assumed to precede "
                            "vendor decisions."
                        ),
                        "confidence": 5,
                        "supporting_urls": [str(business_article.url)],
                    },
                ],
            },
            raw_text="{}",
            input_tokens=60,
            output_tokens=30,
        )

        builder = DigestBuilder(client=mock_client, max_insights_per_digest=2)
        digest, _, _ = builder.build_digest([tech_article, business_article])

        assert len(digest.non_obvious_insights) == 2
        assert digest.must_read == [str(sample_article.url), str(business_article.url)]


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
            "input_tokens": 70,
            "output_tokens": 30,
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
            },
            raw_text="{}",
            input_tokens=10,
            output_tokens=5,
        )

        summarizer = Summarizer(client=mock_client)
        result = summarizer.summarize_article(sample_article)

        assert result["success"] is True
        assert result["summary"] == "normal summary"
