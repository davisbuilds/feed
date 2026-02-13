"""Tests for LLM retry logic."""

import time

import pytest

from src.llm.base import LLMError, LLMResponse
from src.llm.retry import RetryClient, _is_retryable


class FakeClient:
    """Fake LLM client that can be configured to fail."""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.call_count = 0

    def generate(self, prompt, system, response_schema):
        self.call_count += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


OK_RESPONSE = LLMResponse(
    parsed={"summary": "ok"},
    raw_text="{}",
    input_tokens=10,
    output_tokens=5,
)


class TestIsRetryable:
    def test_timeout_is_retryable(self):
        assert _is_retryable(LLMError("request timed out")) is True

    def test_deadline_exceeded_is_retryable(self):
        assert _is_retryable(LLMError("deadline exceeded")) is True

    def test_rate_limit_429_is_retryable(self):
        assert _is_retryable(LLMError("429 Too Many Requests")) is True

    def test_server_error_500_is_retryable(self):
        assert _is_retryable(LLMError("500 Internal Server Error")) is True

    def test_server_error_503_is_retryable(self):
        assert _is_retryable(LLMError("503 Service Unavailable")) is True

    def test_overloaded_529_is_retryable(self):
        assert _is_retryable(LLMError("529 overloaded")) is True

    def test_auth_error_not_retryable(self):
        assert _is_retryable(LLMError("401 Unauthorized")) is False

    def test_parse_error_not_retryable(self):
        assert _is_retryable(LLMError("response parsing failed")) is False

    def test_unknown_error_not_retryable(self):
        assert _is_retryable(LLMError("something unexpected")) is False


class TestRetryClient:
    def test_success_no_retry(self):
        inner = FakeClient([OK_RESPONSE])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        result = client.generate("prompt", "system", object)

        assert result.parsed == {"summary": "ok"}
        assert inner.call_count == 1

    def test_retries_on_retryable_error_then_succeeds(self):
        inner = FakeClient([
            LLMError("request timed out"),
            OK_RESPONSE,
        ])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        result = client.generate("prompt", "system", object)

        assert result.parsed == {"summary": "ok"}
        assert inner.call_count == 2

    def test_raises_after_max_retries_exhausted(self):
        inner = FakeClient([
            LLMError("request timed out"),
            LLMError("request timed out"),
            LLMError("request timed out"),
        ])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        with pytest.raises(LLMError, match="timed out"):
            client.generate("prompt", "system", object)

        assert inner.call_count == 3

    def test_non_retryable_error_fails_immediately(self):
        inner = FakeClient([LLMError("401 Unauthorized")])
        client = RetryClient(inner, max_retries=2, base_delay=0.01)

        with pytest.raises(LLMError, match="401"):
            client.generate("prompt", "system", object)

        assert inner.call_count == 1

    def test_zero_retries_means_no_retry(self):
        inner = FakeClient([LLMError("request timed out")])
        client = RetryClient(inner, max_retries=0, base_delay=0.01)

        with pytest.raises(LLMError, match="timed out"):
            client.generate("prompt", "system", object)

        assert inner.call_count == 1

    def test_backoff_delay_increases(self):
        inner = FakeClient([
            LLMError("request timed out"),
            LLMError("request timed out"),
            OK_RESPONSE,
        ])
        client = RetryClient(inner, max_retries=2, base_delay=0.05)

        start = time.monotonic()
        client.generate("prompt", "system", object)
        elapsed = time.monotonic() - start

        assert elapsed >= 0.12
