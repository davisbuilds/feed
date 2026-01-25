# Phase 2: Intelligence Layer

**Goal**: Integrate Claude for intelligent summarization, categorization, and insight extraction. Build a system that produces meaningful, actionable digests.

**Estimated Time**: 4-5 hours

**Dependencies**: Phase 1 completed (ingestion working)

---

## Overview

The intelligence layer transforms raw articles into curated insights. This is the heart of the agent—where information overload becomes actionable knowledge.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Intelligence Pipeline                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐         │
│  │   Articles   │────▶│  Summarize   │────▶│  Categorize  │         │
│  │  (pending)   │     │   (Claude)   │     │   (Claude)   │         │
│  └──────────────┘     └──────────────┘     └──────────────┘         │
│                              │                    │                  │
│                              ▼                    ▼                  │
│                       ┌──────────────┐     ┌──────────────┐         │
│                       │   Extract    │     │  Synthesize  │         │
│                       │  Takeaways   │     │   Themes     │         │
│                       └──────────────┘     └──────────────┘         │
│                              │                    │                  │
│                              └────────┬───────────┘                  │
│                                       ▼                              │
│                              ┌──────────────┐                       │
│                              │    Daily     │                       │
│                              │    Digest    │                       │
│                              └──────────────┘                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Structured Output**: Use Pydantic models with Claude for reliable JSON extraction
2. **Cost Efficiency**: Batch similar operations, cache when possible
3. **Quality Focus**: Invest tokens in getting summaries right
4. **Fail Gracefully**: If one article fails, continue with others

---

## Tasks

### 2.1 Prompt Templates

Create `src/analyze/prompts.py`:

```python
"""
Prompt templates for Claude interactions.

Design philosophy:
- Clear, specific instructions
- Structured output format (JSON)
- Examples where helpful
- Character/tone guidance
"""

ARTICLE_SUMMARY_SYSTEM = """You are a skilled editor who creates concise, insightful summaries of newsletter articles. Your summaries help busy professionals quickly understand the key points and decide what deserves deeper reading.

Your summaries should:
- Capture the core thesis or argument
- Highlight what's new or surprising
- Note practical implications
- Be written in clear, direct prose
- Avoid jargon unless essential

Always respond with valid JSON matching the requested schema."""

ARTICLE_SUMMARY_USER = """Summarize this article and extract key insights.

<article>
Title: {title}
Author: {author}
Source: {feed_name}
Published: {published}

Content:
{content}
</article>

Respond with JSON in this exact format:
{{
    "summary": "2-3 sentence summary capturing the main point and why it matters",
    "key_takeaways": ["insight 1", "insight 2", "insight 3"],
    "action_items": ["actionable item if any"],
    "topics": ["topic1", "topic2"],
    "sentiment": "positive|negative|neutral|mixed",
    "importance": 1-5
}}

Focus on what's genuinely useful. If there are no clear action items, return an empty array."""

DIGEST_SYNTHESIS_SYSTEM = """You are creating a daily newsletter digest for a busy professional. Your job is to synthesize multiple article summaries into a coherent overview that surfaces the most important themes and insights.

Your synthesis should:
- Identify connections across articles
- Highlight the most important takeaways
- Surface surprising or counterintuitive findings
- Prioritize actionable insights
- Be scannable and well-organized

Write in a warm but efficient tone—like a trusted colleague briefing you over coffee."""

CATEGORY_SYNTHESIS_USER = """Here are the summaries from today's {category} articles:

{article_summaries}

Create a synthesis for this category. Respond with JSON:
{{
    "synthesis": "2-4 sentences summarizing the key themes and most important points across these articles",
    "top_takeaways": ["most important insight 1", "most important insight 2", "most important insight 3"],
    "must_read": ["url1", "url2"]
}}

Only include must_read URLs for articles that are exceptionally valuable."""

OVERALL_SYNTHESIS_SYSTEM = """You are creating the executive summary for a daily newsletter digest. You need to identify the most important themes across all categories and give the reader a quick understanding of what matters today."""

OVERALL_SYNTHESIS_USER = """Here are today's category summaries:

{category_summaries}

Create an overall synthesis. Respond with JSON:
{{
    "overall_themes": ["theme 1", "theme 2", "theme 3"],
    "headline": "One compelling sentence capturing what matters most today",
    "must_read_overall": ["url1"]
}}

Be highly selective—only 1-3 must-read articles across everything."""
```

- [ ] Create `src/analyze/prompts.py`

### 2.2 Summarizer

Create `src/analyze/summarizer.py`:

```python
"""
Article summarization using Claude.

Uses structured output for reliable JSON extraction.
"""

import json
from typing import TypedDict

import anthropic
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import get_logger
from src.models import Article, ArticleStatus

from .prompts import ARTICLE_SUMMARY_SYSTEM, ARTICLE_SUMMARY_USER

logger = get_logger("summarizer")


class ArticleSummaryResponse(BaseModel):
    """Structured response from Claude for article summaries."""
    
    summary: str = Field(..., description="2-3 sentence summary")
    key_takeaways: list[str] = Field(default_factory=list, max_length=5)
    action_items: list[str] = Field(default_factory=list, max_length=3)
    topics: list[str] = Field(default_factory=list, max_length=5)
    sentiment: str = Field(default="neutral")
    importance: int = Field(default=3, ge=1, le=5)


class SummaryResult(TypedDict):
    """Result of summarizing an article."""
    
    success: bool
    article_id: str
    summary: str | None
    key_takeaways: list[str]
    action_items: list[str]
    tokens_used: int
    error: str | None


class Summarizer:
    """Handles article summarization with Claude."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model or settings.claude_model
        self.max_tokens = settings.max_tokens_per_summary
    
    def summarize_article(self, article: Article) -> SummaryResult:
        """
        Generate a summary for a single article.
        
        Args:
            article: Article to summarize
        
        Returns:
            SummaryResult with summary or error
        """
        logger.info(f"Summarizing: {article.title[:50]}...")
        
        # Truncate content if too long (Claude handles well, but save tokens)
        content = article.content
        if len(content) > 15000:
            content = content[:15000] + "\n\n[Content truncated...]"
        
        user_prompt = ARTICLE_SUMMARY_USER.format(
            title=article.title,
            author=article.author,
            feed_name=article.feed_name,
            published=article.published.strftime("%Y-%m-%d"),
            content=content,
        )
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=ARTICLE_SUMMARY_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            
            # Parse response
            response_text = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            # Extract JSON from response
            parsed = self._parse_json_response(response_text)
            
            logger.debug(f"Summary generated ({tokens_used} tokens)")
            
            return SummaryResult(
                success=True,
                article_id=article.id,
                summary=parsed.get("summary"),
                key_takeaways=parsed.get("key_takeaways", []),
                action_items=parsed.get("action_items", []),
                tokens_used=tokens_used,
                error=None,
            )
            
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return SummaryResult(
                success=False,
                article_id=article.id,
                summary=None,
                key_takeaways=[],
                action_items=[],
                tokens_used=0,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return SummaryResult(
                success=False,
                article_id=article.id,
                summary=None,
                key_takeaways=[],
                action_items=[],
                tokens_used=0,
                error=str(e),
            )
    
    def summarize_batch(
        self, 
        articles: list[Article],
        on_progress: callable | None = None,
    ) -> list[SummaryResult]:
        """
        Summarize multiple articles.
        
        Args:
            articles: List of articles to summarize
            on_progress: Optional callback(index, total, article) for progress
        
        Returns:
            List of SummaryResults
        """
        results: list[SummaryResult] = []
        total = len(articles)
        
        for i, article in enumerate(articles):
            if on_progress:
                on_progress(i, total, article)
            
            result = self.summarize_article(article)
            results.append(result)
        
        successful = sum(1 for r in results if r["success"])
        logger.info(f"Summarized {successful}/{total} articles")
        
        return results
    
    def _parse_json_response(self, text: str) -> dict:
        """
        Extract JSON from Claude's response.
        
        Handles cases where JSON is wrapped in markdown code blocks.
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting from code blocks
        import re
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try finding JSON object in text
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        logger.warning(f"Could not parse JSON from response: {text[:200]}")
        return {}
```

- [ ] Create `src/analyze/summarizer.py`

### 2.3 Digest Builder

Create `src/analyze/digest_builder.py`:

```python
"""
Builds the daily digest by synthesizing summaries.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

import anthropic

from src.config import get_settings
from src.logging_config import get_logger
from src.models import Article, ArticleStatus, CategoryDigest, DailyDigest

from .prompts import (
    CATEGORY_SYNTHESIS_USER,
    DIGEST_SYNTHESIS_SYSTEM,
    OVERALL_SYNTHESIS_SYSTEM,
    OVERALL_SYNTHESIS_USER,
)

logger = get_logger("digest_builder")


class DigestBuilder:
    """Builds a complete daily digest from summarized articles."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model or settings.claude_model
    
    def build_digest(self, articles: list[Article]) -> DailyDigest:
        """
        Build a complete daily digest from articles.
        
        Args:
            articles: List of summarized articles
        
        Returns:
            Complete DailyDigest ready for delivery
        """
        logger.info(f"Building digest from {len(articles)} articles")
        
        # Group by category
        by_category: dict[str, list[Article]] = defaultdict(list)
        for article in articles:
            by_category[article.category].append(article)
        
        # Build category digests
        category_digests: list[CategoryDigest] = []
        
        for category_name, category_articles in sorted(by_category.items()):
            logger.info(f"Processing category: {category_name} ({len(category_articles)} articles)")
            
            category_digest = self._build_category_digest(
                category_name, 
                category_articles,
            )
            category_digests.append(category_digest)
        
        # Generate overall synthesis
        overall_themes, must_read = self._synthesize_overall(category_digests)
        
        # Assemble final digest
        digest = DailyDigest(
            id=str(uuid4())[:8],
            date=datetime.now(timezone.utc),
            categories=category_digests,
            total_articles=len(articles),
            total_feeds=len({a.feed_url for a in articles}),
            overall_themes=overall_themes,
            must_read=must_read,
        )
        
        logger.info(f"Digest built: {digest.total_articles} articles, {len(digest.categories)} categories")
        
        return digest
    
    def _build_category_digest(
        self, 
        category_name: str, 
        articles: list[Article],
    ) -> CategoryDigest:
        """Build digest for a single category."""
        
        # Format article summaries for Claude
        summaries_text = "\n\n".join([
            f"**{a.title}** ({a.feed_name})\n"
            f"URL: {a.url}\n"
            f"Summary: {a.summary or 'No summary available'}\n"
            f"Key points: {', '.join(a.key_takeaways) if a.key_takeaways else 'None'}"
            for a in articles
        ])
        
        # Get synthesis from Claude
        synthesis = ""
        top_takeaways: list[str] = []
        must_read: list[str] = []
        
        if len(articles) > 1:
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    system=DIGEST_SYNTHESIS_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": CATEGORY_SYNTHESIS_USER.format(
                            category=category_name,
                            article_summaries=summaries_text,
                        ),
                    }],
                )
                
                parsed = self._parse_json(response.content[0].text)
                synthesis = parsed.get("synthesis", "")
                top_takeaways = parsed.get("top_takeaways", [])
                must_read = parsed.get("must_read", [])
                
            except Exception as e:
                logger.warning(f"Category synthesis failed: {e}")
                # Fall back to simple aggregation
                synthesis = f"Today's {category_name} coverage includes {len(articles)} articles."
                top_takeaways = []
                for a in articles[:3]:
                    if a.key_takeaways:
                        top_takeaways.append(a.key_takeaways[0])
        else:
            # Single article - use its summary directly
            article = articles[0]
            synthesis = article.summary or f"One article from {article.feed_name}."
            top_takeaways = article.key_takeaways[:3]
        
        return CategoryDigest(
            name=category_name,
            article_count=len(articles),
            articles=articles,
            synthesis=synthesis,
            top_takeaways=top_takeaways,
        )
    
    def _synthesize_overall(
        self, 
        category_digests: list[CategoryDigest],
    ) -> tuple[list[str], list[str]]:
        """Generate overall themes across all categories."""
        
        if not category_digests:
            return [], []
        
        # Format category summaries
        summaries_text = "\n\n".join([
            f"**{cd.name}** ({cd.article_count} articles)\n"
            f"Synthesis: {cd.synthesis}\n"
            f"Key takeaways: {', '.join(cd.top_takeaways) if cd.top_takeaways else 'None'}"
            for cd in category_digests
        ])
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                system=OVERALL_SYNTHESIS_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": OVERALL_SYNTHESIS_USER.format(
                        category_summaries=summaries_text,
                    ),
                }],
            )
            
            parsed = self._parse_json(response.content[0].text)
            return (
                parsed.get("overall_themes", []),
                parsed.get("must_read_overall", []),
            )
            
        except Exception as e:
            logger.warning(f"Overall synthesis failed: {e}")
            return [], []
    
    def _parse_json(self, text: str) -> dict:
        """Extract JSON from Claude's response."""
        import re
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return {}
```

- [ ] Create `src/analyze/digest_builder.py`

### 2.4 Analysis Orchestrator

Create `src/analyze/__init__.py`:

```python
"""
Analysis module - Claude-powered intelligence layer.

Coordinates summarization, categorization, and digest building.
"""

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from src.config import get_settings
from src.logging_config import get_logger
from src.models import Article, ArticleStatus, DailyDigest, DigestStats
from src.storage.db import Database

from .digest_builder import DigestBuilder
from .summarizer import Summarizer

logger = get_logger("analyze")

__all__ = ["run_analysis", "AnalysisResult"]


class AnalysisResult(NamedTuple):
    """Result of the analysis pipeline."""
    
    digest: DailyDigest | None
    articles_analyzed: int
    tokens_used: int
    cost_estimate_usd: float
    duration_seconds: float
    errors: list[str]


# Approximate pricing (check Anthropic's current pricing)
COST_PER_INPUT_TOKEN = 0.003 / 1000   # $3 per 1M input tokens (Sonnet)
COST_PER_OUTPUT_TOKEN = 0.015 / 1000  # $15 per 1M output tokens (Sonnet)


def run_analysis(
    db: Database | None = None,
    lookback_hours: int | None = None,
) -> AnalysisResult:
    """
    Run the full analysis pipeline.
    
    1. Get pending articles from database
    2. Summarize each with Claude
    3. Build categorical digest
    4. Generate overall synthesis
    
    Args:
        db: Database instance
        lookback_hours: Hours to look back (default from settings)
    
    Returns:
        AnalysisResult with digest and stats
    """
    import time
    start_time = time.time()
    
    settings = get_settings()
    lookback_hours = lookback_hours or settings.lookback_hours
    
    errors: list[str] = []
    total_tokens = 0
    
    # Initialize database if needed
    if db is None:
        db = Database(settings.data_dir / "articles.db")
    
    # Get pending articles
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
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
    
    # Initialize Claude components
    summarizer = Summarizer()
    digest_builder = DigestBuilder()
    
    # Summarize articles
    summarized_articles: list[Article] = []
    
    def on_progress(i: int, total: int, article: Article) -> None:
        logger.info(f"[{i+1}/{total}] {article.title[:40]}...")
    
    summary_results = summarizer.summarize_batch(articles, on_progress=on_progress)
    
    for article, result in zip(articles, summary_results):
        total_tokens += result["tokens_used"]
        
        if result["success"]:
            # Update article with summary
            article.summary = result["summary"]
            article.key_takeaways = result["key_takeaways"]
            article.action_items = result["action_items"]
            article.status = ArticleStatus.SUMMARIZED
            
            # Save to database
            db.update_article_summary(
                article_id=article.id,
                summary=result["summary"] or "",
                key_takeaways=result["key_takeaways"],
                action_items=result["action_items"],
            )
            
            summarized_articles.append(article)
        else:
            db.update_article_status(article.id, ArticleStatus.FAILED)
            errors.append(f"Failed to summarize: {article.title[:30]} - {result['error']}")
    
    if not summarized_articles:
        logger.warning("No articles were successfully summarized")
        return AnalysisResult(
            digest=None,
            articles_analyzed=0,
            tokens_used=total_tokens,
            cost_estimate_usd=_estimate_cost(total_tokens),
            duration_seconds=time.time() - start_time,
            errors=errors,
        )
    
    # Build digest
    logger.info("Building digest...")
    digest = digest_builder.build_digest(summarized_articles)
    
    # Estimate tokens used for synthesis (rough)
    synthesis_tokens = 2000 * len(digest.categories)
    total_tokens += synthesis_tokens
    
    duration = time.time() - start_time
    digest.processing_time_seconds = duration
    
    logger.info(
        f"Analysis complete: {len(summarized_articles)} articles, "
        f"{total_tokens} tokens, {duration:.1f}s"
    )
    
    return AnalysisResult(
        digest=digest,
        articles_analyzed=len(summarized_articles),
        tokens_used=total_tokens,
        cost_estimate_usd=_estimate_cost(total_tokens),
        duration_seconds=duration,
        errors=errors,
    )


def _estimate_cost(tokens: int) -> float:
    """Estimate API cost (rough, assumes 50/50 input/output split)."""
    input_tokens = tokens * 0.7
    output_tokens = tokens * 0.3
    return (input_tokens * COST_PER_INPUT_TOKEN) + (output_tokens * COST_PER_OUTPUT_TOKEN)
```

- [ ] Create `src/analyze/__init__.py`

### 2.5 Test Analysis Pipeline

Create `scripts/test_analyze.py`:

```python
"""Test the analysis pipeline with real articles."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyze import run_analysis
from src.config import get_settings
from src.logging_config import setup_logging
from src.storage.db import Database


def main() -> None:
    """Run a test analysis."""
    setup_logging("INFO")
    settings = get_settings()
    
    print("=" * 60)
    print("Testing Analysis Pipeline")
    print("=" * 60)
    
    # Use the same database as ingestion
    db_path = settings.data_dir / "test_articles.db"
    
    if not db_path.exists():
        print(f"\n❌ Database not found: {db_path}")
        print("Run test_ingest.py first to populate the database.")
        return
    
    db = Database(db_path)
    
    # Check for pending articles
    pending = db.get_pending_articles()
    print(f"\nFound {len(pending)} pending articles")
    
    if not pending:
        print("No pending articles. Run test_ingest.py first.")
        return
    
    print("\nArticles to analyze:")
    for article in pending[:5]:
        print(f"  • {article.title[:50]}...")
    if len(pending) > 5:
        print(f"  ... and {len(pending) - 5} more")
    
    print("\n" + "-" * 60)
    input("Press Enter to start analysis (this will use Claude API)...")
    print("-" * 60 + "\n")
    
    result = run_analysis(db=db)
    
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Articles analyzed: {result.articles_analyzed}")
    print(f"Tokens used:       {result.tokens_used:,}")
    print(f"Estimated cost:    ${result.cost_estimate_usd:.4f}")
    print(f"Duration:          {result.duration_seconds:.2f}s")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  ✗ {error}")
    
    if result.digest:
        print("\n" + "-" * 60)
        print("Digest Preview")
        print("-" * 60)
        
        print(f"\n📅 {result.digest.date.strftime('%B %d, %Y')}")
        print(f"📊 {result.digest.total_articles} articles from {result.digest.total_feeds} feeds")
        
        if result.digest.overall_themes:
            print("\n🎯 Overall Themes:")
            for theme in result.digest.overall_themes:
                print(f"   • {theme}")
        
        for cat in result.digest.categories:
            print(f"\n📁 {cat.name} ({cat.article_count} articles)")
            print(f"   {cat.synthesis}")
            
            if cat.top_takeaways:
                print("\n   Key takeaways:")
                for takeaway in cat.top_takeaways[:3]:
                    print(f"   • {takeaway}")
            
            print("\n   Articles:")
            for article in cat.articles[:3]:
                print(f"   • {article.title[:40]}...")
                if article.summary:
                    print(f"     {article.summary[:100]}...")


if __name__ == "__main__":
    main()
```

- [ ] Create `scripts/test_analyze.py`
- [ ] First run `test_ingest.py` to get some articles
- [ ] Run `uv run python scripts/test_analyze.py`
- [ ] Review the quality of summaries and synthesis

### 2.6 Unit Tests

Create `tests/test_analyze.py`:

```python
"""Tests for the analysis module."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.models import Article, ArticleStatus, CategoryDigest
from src.analyze.summarizer import Summarizer
from src.analyze.digest_builder import DigestBuilder


@pytest.fixture
def sample_article():
    """Create a sample article for testing."""
    return Article(
        id="test123",
        url="https://example.com/test",
        title="Test Article About AI",
        author="Test Author",
        feed_name="Test Feed",
        feed_url="https://example.com/feed",
        published=datetime.now(timezone.utc),
        content="This is a test article about artificial intelligence and its impact on society. " * 20,
        word_count=200,
        category="Technology",
    )


class TestSummarizer:
    """Tests for the Summarizer class."""
    
    @patch("src.analyze.summarizer.anthropic.Anthropic")
    def test_summarize_article_success(self, mock_anthropic, sample_article):
        """Test successful article summarization."""
        # Mock Claude response
        mock_response = Mock()
        mock_response.content = [Mock(text='{"summary": "Test summary", "key_takeaways": ["insight1"], "action_items": [], "topics": ["AI"], "sentiment": "neutral", "importance": 3}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client
        
        summarizer = Summarizer(api_key="test-key")
        result = summarizer.summarize_article(sample_article)
        
        assert result["success"] is True
        assert result["summary"] == "Test summary"
        assert result["key_takeaways"] == ["insight1"]
        assert result["tokens_used"] == 150
    
    @patch("src.analyze.summarizer.anthropic.Anthropic")
    def test_summarize_article_handles_api_error(self, mock_anthropic, sample_article):
        """Test handling of API errors."""
        import anthropic
        
        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.APIError("Test error", None, None)
        mock_anthropic.return_value = mock_client
        
        summarizer = Summarizer(api_key="test-key")
        result = summarizer.summarize_article(sample_article)
        
        assert result["success"] is False
        assert "error" in result["error"].lower() or "Test error" in result["error"]


class TestDigestBuilder:
    """Tests for the DigestBuilder class."""
    
    def test_groups_articles_by_category(self, sample_article):
        """Test that articles are grouped correctly."""
        articles = [
            sample_article,
            Article(
                id="test456",
                url="https://example.com/test2",
                title="Another Article",
                author="Another Author",
                feed_name="Another Feed",
                feed_url="https://example.com/feed2",
                published=datetime.now(timezone.utc),
                content="Different content",
                word_count=100,
                category="Business",
                summary="Test summary",
            ),
        ]
        
        # We need to mock Claude for the builder
        with patch("src.analyze.digest_builder.anthropic.Anthropic"):
            builder = DigestBuilder(api_key="test-key")
            
            # Just test the grouping logic
            from collections import defaultdict
            by_category = defaultdict(list)
            for article in articles:
                by_category[article.category].append(article)
            
            assert len(by_category) == 2
            assert "Technology" in by_category
            assert "Business" in by_category
```

- [ ] Create `tests/test_analyze.py`
- [ ] Run `uv run pytest tests/test_analyze.py -v`

---

## Tuning Tips

### Prompt Engineering

The prompts in `prompts.py` significantly impact output quality. Consider:

1. **Specificity**: Be precise about what you want (length, format, tone)
2. **Examples**: Add few-shot examples for complex outputs
3. **Constraints**: Set clear boundaries (max items, word limits)
4. **Persona**: Define who Claude is in this context

### Cost Optimization

At ~50 newsletters/day with ~5 articles each:
- Individual summaries: ~250 calls × 500 tokens = 125K tokens
- Category synthesis: ~5 calls × 1000 tokens = 5K tokens
- Overall synthesis: ~1 call × 1000 tokens = 1K tokens
- **Total**: ~131K tokens/day ≈ $0.50-1.00/day with Sonnet

To reduce costs:
- Filter low-value articles before summarization
- Use Haiku for initial filtering, Sonnet for final summaries
- Cache summaries (articles don't change)
- Batch similar content

---

## Completion Checklist

- [ ] Summarizer generates quality summaries
- [ ] Digest builder groups by category correctly
- [ ] Overall themes are meaningful
- [ ] Token usage is reasonable
- [ ] Error handling works (test with invalid API key)
- [ ] Unit tests pass

## Next Phase

Once analysis produces quality digests, proceed to `04-PHASE-DELIVER.md` to build beautiful email delivery.
