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
