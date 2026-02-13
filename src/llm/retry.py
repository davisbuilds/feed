"""LLM client wrapper with retry and exponential backoff."""

import re
import time

from pydantic import BaseModel

from src.llm.base import LLMError, LLMResponse
from src.logging_config import get_logger

logger = get_logger("llm.retry")

_RETRYABLE_PATTERNS = re.compile(
    r"timed?\s*out|deadline exceeded|"
    r"\b429\b|\brate.?limit|"
    r"\b500\b|\b502\b|\b503\b|\b529\b|"
    r"overloaded|unavailable",
    re.IGNORECASE,
)


def _is_retryable(error: LLMError) -> bool:
    """Check if an LLM error is worth retrying."""
    return bool(_RETRYABLE_PATTERNS.search(str(error)))


class RetryClient:
    """Wraps an LLMClient with retry logic and exponential backoff."""

    def __init__(
        self,
        inner,
        max_retries: int = 2,
        base_delay: float = 1.0,
    ):
        self.inner = inner
        self.max_retries = max_retries
        self.base_delay = base_delay

    def generate(
        self,
        prompt: str,
        system: str,
        response_schema: type[BaseModel],
    ) -> LLMResponse:
        """Generate with retry on transient failures."""
        for attempt in range(self.max_retries + 1):
            try:
                return self.inner.generate(prompt, system, response_schema)
            except LLMError as exc:
                if not _is_retryable(exc) or attempt == self.max_retries:
                    raise
                delay = self.base_delay * (2 ** attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s: {exc}"
                )
                time.sleep(delay)
        raise LLMError("Unexpected: retry loop exited without return or raise")
