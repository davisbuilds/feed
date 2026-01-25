"""Quick healthcheck for the digest agent."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.storage.db import Database


def main() -> int:
    """Run healthcheck and return exit code."""
    settings = get_settings()
    
    issues = []
    
    # Check database exists
    db_path = settings.data_dir / "articles.db"
    if not db_path.exists():
        issues.append("Database not found")
    else:
        db = Database(db_path)
        
        # Check for recent activity
        with db._connection() as conn:
            last_article = conn.execute("""
                SELECT MAX(created_at) FROM articles
            """).fetchone()[0]
            
            if last_article:
                last_time = datetime.fromisoformat(last_article)
                age_hours = (datetime.now() - last_time).total_seconds() / 3600
                
                # Warning if no ingestion in 48 hours
                if age_hours > 48:
                    issues.append(f"No new articles in {age_hours:.0f} hours")
            else:
                issues.append("No articles in database")
    
    # Check config
    if not settings.google_api_key:
        issues.append("Missing Google API key")
    
    if not settings.resend_api_key:
        issues.append("Missing Resend API key")
    
    # Output
    if issues:
        print("UNHEALTHY")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("HEALTHY")
        return 0


if __name__ == "__main__":
    sys.exit(main())
