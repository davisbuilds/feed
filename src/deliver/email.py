"""
Email delivery via Resend.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import resend

from src.config import get_settings
from src.logging_config import get_logger
from src.models import DailyDigest

from .renderer import EmailRenderer

logger = get_logger("email")


@dataclass
class SendResult:
    """Result of sending an email."""
    
    success: bool
    email_id: str | None
    error: str | None = None


class EmailSender:
    """Handles email delivery via Resend."""
    
    def __init__(
        self, 
        api_key: str | None = None,
        from_address: str | None = None,
        to_address: str | None = None,
    ):
        settings = get_settings()
        
        resend.api_key = api_key or settings.resend_api_key
        self.from_address = from_address or settings.email_from
        self.to_address = to_address or settings.email_to
        
        self.renderer = EmailRenderer()
    
    def send_digest(
        self, 
        digest: DailyDigest,
        subject: str | None = None,
        to: str | None = None,
    ) -> SendResult:
        """
        Send a daily digest email.
        
        Args:
            digest: DailyDigest to send
            subject: Optional custom subject line
            to: Optional recipient override
        
        Returns:
            SendResult with success status
        """
        recipient = to or self.to_address
        
        if subject is None:
            subject = f"📬 Your Daily Digest - {digest.date.strftime('%B %d, %Y')}"
        
        logger.info(f"Sending digest to {recipient}")
        
        try:
            # Render email
            html, text = self.renderer.render(digest, subject)
            
            # Send via Resend
            response = resend.Emails.send({
                "from": self.from_address,
                "to": [recipient],
                "subject": subject,
                "html": html,
                "text": text,
                "tags": [
                    {"name": "type", "value": "daily_digest"},
                    {"name": "date", "value": digest.date.strftime("%Y-%m-%d")},
                ],
            })
            
            email_id = response.get("id") if isinstance(response, dict) else str(response)
            
            logger.info(f"Email sent successfully: {email_id}")
            
            return SendResult(
                success=True,
                email_id=email_id,
            )
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return SendResult(
                success=False,
                email_id=None,
                error=str(e),
            )
    
    def send_test_email(self, to: str | None = None) -> SendResult:
        """
        Send a test email to verify configuration.
        
        Args:
            to: Optional recipient override
        
        Returns:
            SendResult with success status
        """
        recipient = to or self.to_address
        
        logger.info(f"Sending test email to {recipient}")
        
        try:
            response = resend.Emails.send({
                "from": self.from_address,
                "to": [recipient],
                "subject": "🧪 Feed - Test Email",
                "html": """
                    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #18181b;">Test Email</h1>
                        <p style="color: #3f3f46;">
                            If you're reading this, your Feed email configuration is working correctly!
                        </p>
                        <p style="color: #71717a; font-size: 14px;">
                            Sent at: {time}
                        </p>
                    </div>
                """.format(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "text": "Test email from Feed. If you're reading this, your configuration is working!",
            })
            
            email_id = response.get("id") if isinstance(response, dict) else str(response)
            
            logger.info(f"Test email sent: {email_id}")
            
            return SendResult(
                success=True,
                email_id=email_id,
            )
            
        except Exception as e:
            logger.error(f"Test email failed: {e}")
            return SendResult(
                success=False,
                email_id=None,
                error=str(e),
            )
