"""Test email delivery with Resend."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from src.config import get_settings
from src.deliver import EmailSender
from src.logging_config import setup_logging
from src.models import Article, CategoryDigest, DailyDigest


def create_sample_digest() -> DailyDigest:
    """Create a sample digest for testing."""
    articles = [
        Article(
            id="1",
            url="https://example.com/article1",
            title="The Future of AI in Content Creation",
            author="Jane Smith",
            feed_name="Tech Insights",
            feed_url="https://techinsights.substack.com/feed",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=1500,
            category="Technology",
            summary="AI is revolutionizing content creation, enabling personalized experiences at scale while raising questions about authenticity and creative ownership.",
            key_takeaways=[
                "AI tools can now generate human-quality content in seconds",
                "Authenticity verification becoming crucial for trust",
                "Creative professionals shifting to curation and editing roles",
            ],
            action_items=["Explore AI writing assistants for your workflow"],
        ),
        Article(
            id="2",
            url="https://example.com/article2",
            title="Remote Work: Three Years Later",
            author="Bob Johnson",
            feed_name="Workplace Weekly",
            feed_url="https://workplace.substack.com/feed",
            published=datetime.now(timezone.utc),
            content="Sample content...",
            word_count=1200,
            category="Business",
            summary="New data reveals hybrid work is here to stay, with most companies settling on 2-3 office days per week as the new standard.",
            key_takeaways=[
                "Productivity remains stable in hybrid arrangements",
                "Company culture requires intentional effort to maintain",
            ],
            action_items=[],
        ),
    ]
    
    categories = [
        CategoryDigest(
            name="Technology",
            article_count=1,
            articles=[articles[0]],
            synthesis="Today's tech coverage focuses on the transformative impact of AI on creative industries.",
            top_takeaways=[
                "AI content generation has reached a quality threshold that demands attention",
                "The line between human and AI-generated content is blurring",
            ],
        ),
        CategoryDigest(
            name="Business",
            article_count=1,
            articles=[articles[1]],
            synthesis="Workplace trends continue to evolve as companies find their footing in the post-pandemic era.",
            top_takeaways=[
                "Hybrid work is becoming the dominant model",
            ],
        ),
    ]
    
    return DailyDigest(
        id="test-001",
        date=datetime.now(timezone.utc),
        categories=categories,
        total_articles=2,
        total_feeds=2,
        processing_time_seconds=3.7,
        overall_themes=[
            "Technology reshaping traditional workflows",
            "Adaptability as a key professional skill",
        ],
        must_read=["https://example.com/article1"],
    )


def main() -> None:
    """Test email delivery."""
    setup_logging("INFO")
    settings = get_settings()
    
    print("=" * 60)
    print("Testing Email Delivery")
    print("=" * 60)
    
    print(f"\nConfiguration:")
    print(f"  From: {settings.email_from}")
    print(f"  To: {settings.email_to}")
    
    sender = EmailSender()
    
    # Test 1: Send test email
    print("\n" + "-" * 60)
    print("Test 1: Sending test email...")
    print("-" * 60)
    
    result = sender.send_test_email()
    
    if result.success:
        print(f"✅ Test email sent successfully")
        print(f"   Email ID: {result.email_id}")
    else:
        print(f"❌ Test email failed: {result.error}")
        return
    
    # Test 2: Send sample digest
    print("\n" + "-" * 60)
    print("Test 2: Sending sample digest...")
    print("-" * 60)
    
    digest = create_sample_digest()
    
    result = sender.send_digest(digest)
    
    if result.success:
        print(f"✅ Digest sent successfully")
        print(f"   Email ID: {result.email_id}")
    else:
        print(f"❌ Digest failed: {result.error}")
        return
    
    print("\n" + "=" * 60)
    print("All tests passed! Check your inbox.")
    print("=" * 60)


if __name__ == "__main__":
    main()
