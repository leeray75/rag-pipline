"""HTML to Markdown conversion using markitdown with pre/post processing."""

import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone

from markitdown import MarkItDown

import structlog

logger = structlog.get_logger()


@dataclass
class ConversionResult:
    """Result of converting HTML to Markdown."""
    markdown: str
    title: str
    word_count: int
    source_url: str
    error: str | None = None


def _sanitize_html(html: str) -> str:
    """Remove noise elements before conversion."""
    # Remove script and style tags
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove common noise elements
    html = re.sub(r"<(nav|footer|header)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove cookie banners
    html = re.sub(r'<div[^>]*class="[^"]*cookie[^"]*"[^>]*>.*?</div>', "", html, flags=re.DOTALL | re.IGNORECASE)
    return html


def _extract_title(html: str) -> str:
    """Extract title from HTML."""
    # Try <title> tag
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try first <h1>
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if match:
        # Strip HTML tags from h1 content
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return "Untitled"


def _add_frontmatter(markdown: str, title: str, source_url: str, description: str = "") -> str:
    """Prepend YAML frontmatter to the Markdown content."""
    now = datetime.now(timezone.utc).isoformat()
    frontmatter = f"""---
title: "{title}"
description: "{description}"
source_url: "{source_url}"
fetched_at: "{now}"
tags: []
---

"""
    return frontmatter + markdown


def _post_process_markdown(markdown: str) -> str:
    """Clean up common markitdown artifacts."""
    # Remove excessive blank lines (more than 2 consecutive)
    markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)
    # Fix code blocks without language identifier
    markdown = re.sub(r"```\n", "```text\n", markdown)
    # Remove residual HTML tags
    markdown = re.sub(r"</?(?:div|span|section|article)[^>]*>", "", markdown)
    return markdown.strip()


def convert_html_to_markdown(html: str, source_url: str) -> ConversionResult:
    """Convert HTML to clean Markdown with frontmatter."""
    try:
        title = _extract_title(html)
        sanitized = _sanitize_html(html)

        # Use markitdown for conversion via temporary file
        converter = MarkItDown()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(sanitized)
            temp_path = f.name
        
        try:
            result = converter.convert_local(temp_path)
            markdown = result.text_content
        finally:
            import os
            os.unlink(temp_path)

        # Post-process
        markdown = _post_process_markdown(markdown)

        # Generate description from first 200 chars
        desc_text = re.sub(r"[#*\[\]`]", "", markdown[:300]).strip()
        description = desc_text[:200] if len(desc_text) > 200 else desc_text

        # Add frontmatter
        markdown = _add_frontmatter(markdown, title, source_url, description)

        word_count = len(markdown.split())

        logger.info("html_converted", url=source_url, words=word_count)
        return ConversionResult(
            markdown=markdown,
            title=title,
            word_count=word_count,
            source_url=source_url,
        )
    except Exception as e:
        logger.error("conversion_failed", url=source_url, error=str(e))
        return ConversionResult(
            markdown="", title="", word_count=0,
            source_url=source_url, error=str(e),
        )
