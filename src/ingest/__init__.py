"""
Content ingestion module.

Coordinates feed fetching, content parsing, and storage.
"""

from datetime import datetime, timezone
from pathlib import Path

from src.config import FeedConfig, get_settings
from src.logging_config import get_logger
from src.models import Article, ArticleStatus, DigestStats
from src.storage.db import Database

from .feeds import fetch_all_feeds
from .parser import process_articles

logger = get_logger("ingest")

__all__ = ["run_ingestion", "IngestResult"]


class IngestResult:
    """Result of an ingestion run."""
    
    def __init__(self):
        self.feeds_checked: int = 0
        self.feeds_successful: int = 0
        self.feeds_failed: int = 0
        self.articles_found: int = 0
        self.articles_new: int = 0
        self.articles_processed: int = 0
        self.errors: list[str] = []
        self.duration_seconds: float = 0.0
    
    def __str__(self) -> str:
        return (
            f"Ingestion: {self.feeds_successful}/{self.feeds_checked} feeds, "
            f"{self.articles_new} new articles ({self.duration_seconds:.1f}s)"
        )


def run_ingestion(
    db: Database | None = None,
    feed_config: FeedConfig | None = None,
    fetch_content: bool = True,
) -> IngestResult:
    """
    Run the full ingestion pipeline.
    
    1. Load feed configuration
    2. Fetch all feeds
    3. Parse and extract content
    4. Deduplicate and store
    
    Args:
        db: Database instance (creates one if not provided)
        feed_config: Feed configuration (loads from default if not provided)
        fetch_content: Whether to fetch full article content
    
    Returns:
        IngestResult with statistics
    """
    import time
    start_time = time.time()
    
    settings = get_settings()
    result = IngestResult()
    
    # Initialize database if needed
    if db is None:
        db = Database(settings.data_dir / "articles.db")
    
    # Load feed config if needed
    if feed_config is None:
        feed_config = FeedConfig(settings.config_dir / "feeds.yaml")
    
    feeds = feed_config.feeds
    if not feeds:
        logger.warning("No feeds configured")
        return result
    
    logger.info(f"Starting ingestion for {len(feeds)} feeds")
    result.feeds_checked = len(feeds)
    
    # Fetch all feeds
    feed_results = fetch_all_feeds(
        feeds_config=feeds,
        lookback_hours=settings.lookback_hours,
        max_articles_per_feed=settings.max_articles_per_feed,
    )
    
    # Process each feed result
    all_articles: list[Article] = []
    
    for feed_result in feed_results:
        # Update feed status in database
        db.update_feed_status(
            feed_url=feed_result.feed_url,
            feed_name=feed_result.feed_name,
            success=feed_result.success,
            error=feed_result.error,
        )
        
        if feed_result.success:
            result.feeds_successful += 1
            all_articles.extend(feed_result.articles)
        else:
            result.feeds_failed += 1
            result.errors.append(f"{feed_result.feed_name}: {feed_result.error}")
    
    result.articles_found = len(all_articles)
    logger.info(f"Found {result.articles_found} articles from {result.feeds_successful} feeds")
    
    # Deduplicate against existing articles
    new_articles: list[Article] = []
    for article in all_articles:
        if not db.article_exists(article.id):
            new_articles.append(article)
    
    result.articles_new = len(new_articles)
    logger.info(f"{result.articles_new} articles are new")
    
    if not new_articles:
        result.duration_seconds = time.time() - start_time
        return result
    
    # Fetch and process content
    if fetch_content:
        logger.info("Fetching article content...")
        new_articles = process_articles(new_articles, fetch_content=True)
    
    result.articles_processed = len(new_articles)
    
    # Store articles
    for article in new_articles:
        db.save_article(article)
    
    logger.info(f"Stored {result.articles_processed} articles")
    
    result.duration_seconds = time.time() - start_time
    logger.info(str(result))
    
    return result
