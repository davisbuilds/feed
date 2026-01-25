"""Verify that the project is set up correctly."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> None:
    """Run setup verification."""
    print("🔍 Verifying project setup...\n")
    
    errors: list[str] = []
    
    # Check Python version
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 12):
        errors.append("Python 3.12+ required")
    else:
        print("✅ Python version OK")
    
    # Check imports
    print("\nChecking dependencies...")
    try:
        import anthropic
        print(f"✅ anthropic {anthropic.__version__}")
    except ImportError as e:
        errors.append(f"anthropic: {e}")
    
    try:
        import feedparser
        print(f"✅ feedparser {feedparser.__version__}")
    except ImportError as e:
        errors.append(f"feedparser: {e}")
    
    try:
        import resend
        print("✅ resend")
    except ImportError as e:
        errors.append(f"resend: {e}")
    
    try:
        from bs4 import BeautifulSoup
        print("✅ beautifulsoup4")
    except ImportError as e:
        errors.append(f"beautifulsoup4: {e}")
    
    try:
        import yaml
        print("✅ pyyaml")
    except ImportError as e:
        errors.append(f"pyyaml: {e}")
    
    try:
        import pydantic
        print(f"✅ pydantic {pydantic.__version__}")
    except ImportError as e:
        errors.append(f"pydantic: {e}")
    
    # Check configuration
    print("\nChecking configuration...")
    try:
        from config import get_settings
        settings = get_settings()
        print(f"✅ Settings loaded")
        print(f"   Claude model: {settings.claude_model}")
        print(f"   Email from: {settings.email_from}")
    except Exception as e:
        errors.append(f"Configuration: {e}")
    
    # Check feeds config
    print("\nChecking feeds config...")
    feeds_path = Path("config/feeds.yaml")
    if feeds_path.exists():
        try:
            from config import FeedConfig
            feed_config = FeedConfig(feeds_path)
            urls = feed_config.get_feed_urls()
            print(f"✅ Found {len(urls)} configured feeds")
        except Exception as e:
            errors.append(f"Feeds config: {e}")
    else:
        errors.append("config/feeds.yaml not found")
    
    # Summary
    print("\n" + "=" * 50)
    if errors:
        print("❌ Setup verification FAILED")
        print("\nErrors:")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)
    else:
        print("✅ Setup verification PASSED")
        print("\nReady to proceed to Phase 1!")


if __name__ == "__main__":
    main()
