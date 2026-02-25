"""Analysis module - LLM-powered intelligence layer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, NamedTuple

from src.config import get_settings
from src.llm import create_client
from src.logging_config import get_logger
from src.models import Article, ArticleStatus, DailyDigest
from src.storage.db import Database

from .digest_builder import DigestBuilder
from .summarizer import Summarizer

if TYPE_CHECKING:
    from src.storage.cache import CacheStore

logger = get_logger("analyze")

__all__ = ["run_analysis", "AnalysisResult"]


class AnalysisResult(NamedTuple):
    """Result of the analysis pipeline."""

    digest: DailyDigest | None
    articles_analyzed: int
    input_tokens: int
    output_tokens: int
    cost_estimate_usd: float | None
    duration_seconds: float
    errors: list[str]

    @property
    def tokens_used(self) -> int:
        """Total tokens (backward compat for CLI display)."""
        return self.input_tokens + self.output_tokens


def run_analysis(
    db: Database | None = None,
    lookback_hours: int | None = None,
    no_cache: bool = False,
) -> AnalysisResult:
    """Run the full analysis pipeline."""
    import time

    from src import pricing

    start_time = time.time()

    settings = get_settings()
    lookback_hours = lookback_hours or settings.lookback_hours
    provider = settings.llm_provider
    api_key = settings.llm_api_key
    model = settings.llm_model

    errors: list[str] = []
    total_in = 0
    total_out = 0

    if db is None:
        db = Database(settings.data_dir / "articles.db")

    # Set up cache unless disabled
    cache: CacheStore | None = None
    if not no_cache:
        from src.storage.cache import CacheStore

        cache = CacheStore(
            db_path=db.db_path,
            default_ttl_days=settings.cache_ttl_days,
        )

    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    articles = db.get_articles_since(since, status=ArticleStatus.PENDING)

    if not articles:
        logger.info("No pending articles to analyze")
        return AnalysisResult(
            digest=None,
            articles_analyzed=0,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_usd=0.0,
            duration_seconds=time.time() - start_time,
            errors=[],
        )

    logger.info(f"Analyzing {len(articles)} articles")

    llm_client = create_client(
        provider=provider,
        api_key=api_key,
        model=model,
        max_retries=settings.llm_retries,
    )
    summarizer = Summarizer(client=llm_client)
    digest_builder = DigestBuilder(
        client=llm_client,
        insights_mode=settings.insights_mode,
        insight_min_confidence=settings.insight_min_confidence,
        max_insights_per_digest=settings.max_insights_per_digest,
    )

    summarized_articles: list[Article] = []

    def on_progress(i: int, total: int, article: Article) -> None:
        logger.info(f"[{i + 1}/{total}] {article.title[:40]}...")

    summary_results = summarizer.summarize_batch(
        articles,
        on_progress=on_progress,
        cache=cache,
        model_name=model,
    )

    for article, result in zip(articles, summary_results, strict=False):
        total_in += result["input_tokens"]
        total_out += result["output_tokens"]

        if result["success"]:
            article.summary = result["summary"]
            article.key_takeaways = result["key_takeaways"]
            article.action_items = result["action_items"]
            article.status = ArticleStatus.SUMMARIZED

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
            input_tokens=total_in,
            output_tokens=total_out,
            cost_estimate_usd=pricing.estimate_cost(model, total_in, total_out),
            duration_seconds=time.time() - start_time,
            errors=errors,
        )

    logger.info("Building digest...")
    digest, digest_in, digest_out = digest_builder.build_digest(summarized_articles)

    total_in += digest_in
    total_out += digest_out

    duration = time.time() - start_time
    digest.processing_time_seconds = duration

    logger.info(
        f"Analysis complete: {len(summarized_articles)} articles, "
        f"{total_in + total_out} tokens, {duration:.1f}s"
    )

    return AnalysisResult(
        digest=digest,
        articles_analyzed=len(summarized_articles),
        input_tokens=total_in,
        output_tokens=total_out,
        cost_estimate_usd=pricing.estimate_cost(model, total_in, total_out),
        duration_seconds=duration,
        errors=errors,
    )
