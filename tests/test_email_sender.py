"""Tests for Resend email sender behavior."""

from datetime import UTC, datetime
from types import SimpleNamespace

from feed.deliver.email import EmailSender
from feed.models import Article, CategoryDigest, DailyDigest


def _sample_digest() -> DailyDigest:
    article = Article(
        id="article-1",
        url="https://example.com/article",
        title="Infrastructure Notes",
        feed_name="Example",
        feed_url="https://example.com/feed.xml",
        published=datetime(2026, 5, 13, 9, 0, tzinfo=UTC),
        summary="The platform team reduced deployment variance.",
    )
    category = CategoryDigest(
        name="Engineering",
        article_count=1,
        articles=[article],
        synthesis="Teams are converging on a smaller toolchain.",
    )
    return DailyDigest(
        id="digest-2026-05-13",
        date=datetime(2026, 5, 13, 9, 30, tzinfo=UTC),
        categories=[category],
        total_articles=1,
        total_feeds=1,
    )


def test_send_digest_posts_rendered_payload_to_resend(monkeypatch) -> None:
    """Digest sends should include rendered bodies, metadata tags, and recipient override."""
    import feed.deliver.email as email_module

    sent_payloads: list[dict] = []

    monkeypatch.setattr(
        email_module,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key="settings-key",
            email_from="from@example.com",
            email_to="default@example.com",
        ),
    )
    monkeypatch.setattr(
        email_module.resend.Emails,
        "send",
        lambda payload: sent_payloads.append(payload) or {"id": "email-123"},
    )

    sender = EmailSender(api_key="explicit-key", from_address="digest@example.com")
    result = sender.send_digest(_sample_digest(), to="reader@example.com")

    assert result.success is True
    assert result.email_id == "email-123"
    assert email_module.resend.api_key == "explicit-key"
    assert sent_payloads[0]["from"] == "digest@example.com"
    assert sent_payloads[0]["to"] == ["reader@example.com"]
    assert sent_payloads[0]["subject"] == "📬 Your Daily Digest - May 13, 2026"
    assert "Infrastructure Notes" in sent_payloads[0]["html"]
    assert "Infrastructure Notes" in sent_payloads[0]["text"]
    assert {"name": "date", "value": "2026-05-13"} in sent_payloads[0]["tags"]


def test_send_test_email_reports_string_response_id(monkeypatch) -> None:
    """Test email sends should normalize non-dict SDK responses to an email id."""
    import feed.deliver.email as email_module

    sent_payloads: list[dict] = []
    monkeypatch.setattr(
        email_module,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key="settings-key",
            email_from="from@example.com",
            email_to="default@example.com",
        ),
    )
    monkeypatch.setattr(
        email_module.resend.Emails,
        "send",
        lambda payload: sent_payloads.append(payload) or "queued-456",
    )

    result = EmailSender().send_test_email(to="test@example.com")

    assert result.success is True
    assert result.email_id == "queued-456"
    assert sent_payloads[0]["to"] == ["test@example.com"]
    assert sent_payloads[0]["subject"] == "🧪 Feed - Test Email"
    assert "configuration is working" in sent_payloads[0]["text"]


def test_send_digest_returns_failure_when_resend_raises(monkeypatch) -> None:
    """Provider exceptions should be returned as SendResult failures."""
    import feed.deliver.email as email_module

    monkeypatch.setattr(
        email_module,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key="settings-key",
            email_from="from@example.com",
            email_to="default@example.com",
        ),
    )

    def fail_send(_payload: dict) -> None:
        raise RuntimeError("resend unavailable")

    monkeypatch.setattr(email_module.resend.Emails, "send", fail_send)

    result = EmailSender().send_digest(_sample_digest())

    assert result.success is False
    assert result.email_id is None
    assert result.error == "resend unavailable"
