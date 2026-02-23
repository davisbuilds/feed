"""Builds the daily digest by synthesizing summarized articles."""

import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from src.config import get_settings
from src.llm import LLMClient, create_client
from src.logging_config import get_logger
from src.models import Article, CategoryDigest, DailyDigest, NonObviousInsight

from .prompts import (
    CATEGORY_SYNTHESIS_USER,
    DIGEST_SYNTHESIS_SYSTEM,
    OVERALL_SYNTHESIS_SYSTEM,
    OVERALL_SYNTHESIS_USER,
)

logger = get_logger("digest_builder")


class InsightResponse(BaseModel):
    """Structured response for a non-obvious insight."""

    insight: str = Field(..., description="One-sentence non-obvious finding")
    why_unintuitive: str = Field(
        ...,
        description="One-sentence explanation of why the finding is unintuitive",
    )
    confidence: int = Field(..., ge=1, le=5, description="Confidence score")
    supporting_urls: list[str] = Field(
        default_factory=list,
        description="Source URLs backing the insight",
    )


class CategorySynthesisResponse(BaseModel):
    """Structured response for category synthesis."""

    synthesis: str = Field(..., description="2-4 sentence summary of the category")
    top_takeaways: list[str] = Field(default_factory=list, description="Top category insights")
    non_obvious_insight: InsightResponse | None = Field(
        default=None,
        description="Optional non-obvious but evidence-backed insight",
    )


class OverallSynthesisResponse(BaseModel):
    """Structured response for overall digest synthesis."""

    overall_themes: list[str] = Field(
        default_factory=list,
        description="List of major cross-cutting themes",
    )
    must_read_overall: list[str] = Field(
        default_factory=list,
        description="URLs of exceptionally valuable articles"
    )
    cross_category_insights: list[InsightResponse] = Field(
        default_factory=list,
        description="Optional non-obvious insights that span categories",
    )


class DigestBuilder:
    """Builds a complete daily digest from summarized articles."""

    def __init__(
        self,
        client: LLMClient | None = None,
        insights_mode: Literal["off", "auto", "always"] = "auto",
        insight_min_confidence: int = 4,
        max_insights_per_digest: int = 2,
    ):
        if client is None:
            settings = get_settings()
            client = create_client(
                provider=settings.llm_provider,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )

        self.client = client
        self.insights_mode = insights_mode
        self.insight_min_confidence = insight_min_confidence
        self.max_insights_per_digest = max_insights_per_digest

    def build_digest(self, articles: list[Article]) -> DailyDigest:
        """Build a complete daily digest from articles."""
        logger.info(f"Building digest from {len(articles)} articles")

        by_category: dict[str, list[Article]] = defaultdict(list)
        for article in articles:
            by_category[article.category].append(article)

        category_digests: list[CategoryDigest] = []
        for category_name, category_articles in sorted(by_category.items()):
            logger.info(f"Processing category: {category_name} ({len(category_articles)} articles)")
            category_digest = self._build_category_digest(category_name, category_articles)
            category_digests.append(category_digest)

        overall_themes, must_read, non_obvious_insights = self._synthesize_overall(
            category_digests
        )

        digest = DailyDigest(
            id=str(uuid4())[:8],
            date=datetime.now(UTC),
            categories=category_digests,
            total_articles=len(articles),
            total_feeds=len({article.feed_url for article in articles}),
            overall_themes=overall_themes,
            must_read=must_read,
            non_obvious_insights=non_obvious_insights,
        )

        logger.info(
            f"Digest built: {digest.total_articles} articles, {len(digest.categories)} categories"
        )
        return digest

    def _build_category_digest(
        self,
        category_name: str,
        articles: list[Article],
    ) -> CategoryDigest:
        """Build digest for a single category."""
        summaries_text = "\n\n".join(
            [
                f"**{article.title}** ({article.feed_name})\n"
                f"URL: {article.url}\n"
                f"Summary: {article.summary or 'No summary available'}\n"
                "Key points: "
                f"{', '.join(article.key_takeaways) if article.key_takeaways else 'None'}"
                for article in articles
            ]
        )

        synthesis = ""
        top_takeaways: list[str] = []
        non_obvious_insight: NonObviousInsight | None = None
        allowed_urls = {self._normalize_url(str(article.url)) for article in articles}

        if len(articles) > 1:
            try:
                response = self.client.generate(
                    prompt=CATEGORY_SYNTHESIS_USER.format(
                        category=category_name,
                        article_summaries=summaries_text,
                    ),
                    system=DIGEST_SYNTHESIS_SYSTEM,
                    response_schema=CategorySynthesisResponse,
                )
                parsed = CategorySynthesisResponse.model_validate(response.parsed)
                synthesis = parsed.synthesis
                top_takeaways = parsed.top_takeaways
                non_obvious_insight = self._approve_insight(
                    insight=parsed.non_obvious_insight,
                    allowed_urls=allowed_urls,
                    existing_texts=top_takeaways,
                )
            except Exception as exc:
                logger.warning(f"Category synthesis failed: {exc}")
                synthesis = f"Today's {category_name} coverage includes {len(articles)} articles."
                for article in articles[:3]:
                    if article.key_takeaways:
                        top_takeaways.append(article.key_takeaways[0])
        else:
            article = articles[0]
            synthesis = article.summary or f"One article from {article.feed_name}."
            top_takeaways = article.key_takeaways[:3]

        return CategoryDigest(
            name=category_name,
            article_count=len(articles),
            articles=articles,
            synthesis=synthesis,
            top_takeaways=top_takeaways,
            non_obvious_insight=non_obvious_insight,
        )

    def _synthesize_overall(
        self,
        category_digests: list[CategoryDigest],
    ) -> tuple[list[str], list[str], list[NonObviousInsight]]:
        """Generate overall themes across all categories."""
        if not category_digests:
            return [], [], []

        summaries_text = "\n\n".join(
            [
                f"**{digest.name}** ({digest.article_count} articles)\n"
                f"Synthesis: {digest.synthesis}\n"
                "Key takeaways: "
                f"{', '.join(digest.top_takeaways) if digest.top_takeaways else 'None'}"
                for digest in category_digests
            ]
        )
        allowed_urls = {
            self._normalize_url(str(article.url))
            for digest in category_digests
            for article in digest.articles
        }

        try:
            response = self.client.generate(
                prompt=OVERALL_SYNTHESIS_USER.format(category_summaries=summaries_text),
                system=OVERALL_SYNTHESIS_SYSTEM,
                response_schema=OverallSynthesisResponse,
            )
            parsed = OverallSynthesisResponse.model_validate(response.parsed)
            return (
                parsed.overall_themes,
                self._filter_urls(parsed.must_read_overall, allowed_urls)[:3],
                self._approve_insights(
                    insights=parsed.cross_category_insights,
                    allowed_urls=allowed_urls,
                    existing_texts=parsed.overall_themes,
                    max_count=self.max_insights_per_digest,
                ),
            )
        except Exception as exc:
            logger.warning(f"Overall synthesis failed: {exc}")
            return [], [], []

    def _approve_insight(
        self,
        insight: InsightResponse | None,
        allowed_urls: set[str],
        existing_texts: list[str],
    ) -> NonObviousInsight | None:
        """Apply confidence/source/duplication gates to a single insight."""
        if self.insights_mode == "off" or insight is None:
            return None

        if (
            self.insights_mode == "auto"
            and insight.confidence < self.insight_min_confidence
        ):
            return None

        insight_text = insight.insight.strip()
        why_text = insight.why_unintuitive.strip()
        if not insight_text or not why_text:
            return None

        supporting_urls = self._filter_urls(insight.supporting_urls, allowed_urls)
        if not supporting_urls:
            return None

        if self._is_near_duplicate(insight_text, existing_texts):
            return None

        return NonObviousInsight(
            insight=insight_text,
            why_unintuitive=why_text,
            confidence=insight.confidence,
            supporting_urls=supporting_urls,
        )

    def _approve_insights(
        self,
        insights: list[InsightResponse],
        allowed_urls: set[str],
        existing_texts: list[str],
        max_count: int,
    ) -> list[NonObviousInsight]:
        """Apply gating and cap logic to multiple insight candidates."""
        approved: list[NonObviousInsight] = []

        for candidate in insights:
            current_context = [item.insight for item in approved]
            filtered = self._approve_insight(
                insight=candidate,
                allowed_urls=allowed_urls,
                existing_texts=existing_texts + current_context,
            )
            if filtered is None:
                continue

            approved.append(filtered)
            if len(approved) >= max_count:
                break

        return approved

    @staticmethod
    def _filter_urls(urls: list[str], allowed_urls: set[str]) -> list[str]:
        """Keep unique URLs that are present in the provided source set."""
        filtered: list[str] = []
        seen: set[str] = set()

        for url in urls:
            normalized = DigestBuilder._normalize_url(url)
            if normalized in allowed_urls and normalized not in seen:
                filtered.append(normalized)
                seen.add(normalized)

        return filtered

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for deterministic membership checks."""
        return url.strip().rstrip("/")

    @staticmethod
    def _is_near_duplicate(candidate: str, existing_texts: list[str]) -> bool:
        """Treat highly overlapping statements as duplicates."""
        normalized = DigestBuilder._normalize_text(candidate)
        if not normalized:
            return True

        candidate_tokens = set(re.findall(r"[a-z0-9]+", normalized))
        if not candidate_tokens:
            return True

        for text in existing_texts:
            existing_normalized = DigestBuilder._normalize_text(text)
            if not existing_normalized:
                continue

            if normalized == existing_normalized:
                return True

            existing_tokens = set(re.findall(r"[a-z0-9]+", existing_normalized))
            if not existing_tokens:
                continue

            overlap = len(candidate_tokens & existing_tokens) / min(
                len(candidate_tokens), len(existing_tokens)
            )
            if overlap >= 0.8:
                return True

        return False

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize prose snippets for duplication checks."""
        return " ".join(text.lower().split())
