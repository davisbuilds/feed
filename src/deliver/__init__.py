"""
Email delivery module.

Handles rendering and sending of digest emails.
"""

from .email import EmailSender, SendResult
from .renderer import EmailRenderer

__all__ = ["EmailSender", "EmailRenderer", "SendResult", "send_digest"]


def send_digest(digest, **kwargs) -> SendResult:
    """Convenience function to send a digest."""
    sender = EmailSender()
    return sender.send_digest(digest, **kwargs)
