"""Tests for link discovery."""

from src.crawlers.link_discovery import extract_links_with_selectors


def test_extracts_nav_links():
    """Should extract links from nav elements."""
    html = """
    <html><body>
    <nav>
        <a href="/docs/intro">Introduction</a>
        <a href="/docs/guide">Guide</a>
        <a href="https://external.com">External</a>
    </nav>
    </body></html>
    """
    links = extract_links_with_selectors(html, "https://example.com")
    hrefs = [l.href for l in links]
    assert "https://example.com/docs/intro" in hrefs
    assert "https://example.com/docs/guide" in hrefs
    # External link should be excluded
    assert not any("external.com" in h for h in hrefs)


def test_deduplicates_links():
    """Duplicate links should be removed."""
    html = """
    <html><body>
    <nav>
        <a href="/docs/intro">Intro</a>
        <a href="/docs/intro">Introduction</a>
    </nav>
    </body></html>
    """
    links = extract_links_with_selectors(html, "https://example.com")
    hrefs = [l.href for l in links]
    assert hrefs.count("https://example.com/docs/intro") == 1