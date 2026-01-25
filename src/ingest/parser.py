"""
Article content extraction and cleaning.

Handles HTML parsing, text extraction, and content normalization.
"""

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.logging_config import get_logger
from src.models import Article

logger = get_logger("parser")

# Tags to remove entirely (including content)
REMOVE_TAGS = {
    "script", "style", "nav", "header", "footer", "aside",
    "form", "button", "input", "iframe", "noscript",
    "svg", "canvas", "video", "audio",
}

# Tags that typically contain the main content
CONTENT_TAGS = {"article", "main", "div.post-content", "div.entry-content"}

# Minimum word count to consider content valid
MIN_WORD_COUNT = 50


def fetch_article_content(article: Article, timeout: int = 30) -> Article:
    """
    Fetch and parse the full content of an article.
    
    Args:
        article: Article with URL to fetch
        timeout: Request timeout in seconds
    
    Returns:
        Article with content and word_count populated
    """
    logger.debug(f"Fetching content: {article.title}")
    
    try:
        response = httpx.get(
            str(article.url),
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()
        
        html = response.text
        content = extract_text_content(html, str(article.url))
        word_count = len(content.split())
        
        # Update article
        article.content = content
        article.word_count = word_count
        
        logger.debug(f"Extracted {word_count} words from {article.title}")
        
        return article
        
    except httpx.HTTPError as e:
        logger.warning(f"HTTP error fetching {article.url}: {e}")
        return article
    except Exception as e:
        logger.error(f"Error fetching {article.url}: {e}")
        return article


def extract_text_content(html: str, base_url: str = "") -> str:
    """
    Extract clean text content from HTML.
    
    Args:
        html: Raw HTML string
        base_url: Base URL for resolving relative links
    
    Returns:
        Cleaned text content
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Remove unwanted tags
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()
    
    # Try to find main content container
    content_element = None
    
    # Try Substack-specific selectors first
    for selector in [
        "div.body.markup",           # Substack posts
        "article.post",              # Many blogs
        "div.post-content",          # Common pattern
        "article",                   # Semantic HTML
        "main",                      # Semantic HTML
        "div.entry-content",         # WordPress
        "div.article-content",       # News sites
    ]:
        if "." in selector:
            tag, class_name = selector.split(".", 1)
            content_element = soup.find(tag, class_=class_name)
        else:
            content_element = soup.find(selector)
        
        if content_element:
            break
    
    # Fall back to body
    if not content_element:
        content_element = soup.body or soup
    
    # Extract text with some structure
    text_parts: list[str] = []
    
    for element in content_element.descendants:
        if element.name in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"}:
            text = element.get_text(separator=" ", strip=True)
            if text:
                # Add heading markers for context
                if element.name.startswith("h"):
                    text = f"\n## {text}\n"
                elif element.name == "blockquote":
                    text = f"> {text}"
                text_parts.append(text)
    
    # Join and clean
    content = "\n\n".join(text_parts)
    content = clean_text(content)
    
    return content


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    - Remove excessive whitespace
    - Normalize unicode
    - Remove common artifacts
    """
    # Normalize unicode whitespace
    text = re.sub(r"[\u00a0\u2000-\u200b\u2028\u2029\u202f\u205f\u3000]", " ", text)
    
    # Remove excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove excessive spaces
    text = re.sub(r" {2,}", " ", text)
    
    # Remove common newsletter artifacts
    patterns_to_remove = [
        r"Subscribe to .+? newsletter",
        r"Share this post",
        r"Leave a comment",
        r"Read more at .+",
        r"Click here to .+",
        r"Unsubscribe",
        r"View in browser",
        r"Forward to a friend",
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    return text.strip()


def process_articles(
    articles: list[Article],
    fetch_content: bool = True,
    min_word_count: int = MIN_WORD_COUNT,
) -> list[Article]:
    """
    Process a list of articles, optionally fetching content.
    
    Args:
        articles: List of articles to process
        fetch_content: Whether to fetch full article content
        min_word_count: Minimum words to keep article
    
    Returns:
        List of processed articles (may be fewer than input)
    """
    processed: list[Article] = []
    
    for article in articles:
        if fetch_content:
            article = fetch_article_content(article)
        
        # Skip articles with too little content
        if article.word_count < min_word_count:
            logger.debug(f"Skipping article with {article.word_count} words: {article.title}")
            continue
        
        processed.append(article)
    
    return processed
