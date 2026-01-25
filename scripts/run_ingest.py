"""Test the ingestion pipeline with real feeds."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import FeedConfig, get_settings
from src.ingest import run_ingestion
from src.logging_config import setup_logging
from src.storage.db import Database


def main() -> None:
    """Run a test ingestion."""
    setup_logging("DEBUG")
    settings = get_settings()
    
    print("=" * 60)
    print("Testing Ingestion Pipeline")
    print("=" * 60)
    
    # Use test database
    db_path = settings.data_dir / "test_articles.db"
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    db = Database(db_path)
    print(f"\nUsing database: {db_path}")
    
    # Load feeds
    feed_config = FeedConfig(settings.config_dir / "feeds.yaml")
    feeds = feed_config.feeds
    print(f"Found {len(feeds)} configured feeds:")
    for name, config in feeds.items():
        print(f"  • {name}: {config.get('url', 'NO URL')}")
    
    print("\n" + "-" * 60)
    print("Running ingestion...")
    print("-" * 60 + "\n")
    
    result = run_ingestion(db=db, feed_config=feed_config)
    
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Feeds checked:    {result.feeds_checked}")
    print(f"Feeds successful: {result.feeds_successful}")
    print(f"Feeds failed:     {result.feeds_failed}")
    print(f"Articles found:   {result.articles_found}")
    print(f"Articles new:     {result.articles_new}")
    print(f"Articles stored:  {result.articles_processed}")
    print(f"Duration:         {result.duration_seconds:.2f}s")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  ✗ {error}")
    
    # Show sample articles
    print("\n" + "-" * 60)
    print("Sample Articles")
    print("-" * 60)
    
    articles = db.get_pending_articles(limit=5)
    if not articles:
        print("No articles found.")
    
    for article in articles:
        print(f"\n📰 {article.title}")
        print(f"   Author: {article.author}")
        print(f"   Feed: {article.feed_name}")
        print(f"   Words: {article.word_count}")
        print(f"   Published: {article.published}")
        if article.content:
            preview = article.content[:200].replace("\n", " ")
            print(f"   Preview: {preview}...")


if __name__ == "__main__":
    main()
