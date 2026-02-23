"""
Email template rendering using Jinja2.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.logging_config import get_logger
from src.models import DailyDigest

logger = get_logger("renderer")

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


class EmailRenderer:
    """Renders digest to HTML and plain text email formats."""

    def __init__(self, template_dir: Path | None = None):
        self.template_dir = template_dir or TEMPLATE_DIR

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_html(self, digest: DailyDigest, subject: str) -> str:
        """
        Render digest to HTML email.

        Args:
            digest: DailyDigest to render
            subject: Email subject line

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template("digest.html")
        return template.render(digest=digest, subject=subject)

    def render_text(self, digest: DailyDigest) -> str:
        """
        Render digest to plain text email.

        Args:
            digest: DailyDigest to render

        Returns:
            Rendered plain text string
        """
        template = self.env.get_template("digest.txt")
        return template.render(digest=digest)

    def render(self, digest: DailyDigest, subject: str | None = None) -> tuple[str, str]:
        """
        Render digest to both HTML and plain text.

        Args:
            digest: DailyDigest to render
            subject: Optional subject line

        Returns:
            Tuple of (html, text)
        """
        if subject is None:
            subject = f"📬 Your Daily Digest - {digest.date.strftime('%B %d, %Y')}"

        html = self.render_html(digest, subject)
        text = self.render_text(digest)

        logger.debug(f"Rendered email: {len(html)} chars HTML, {len(text)} chars text")

        return html, text
