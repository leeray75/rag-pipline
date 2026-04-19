"""Tests for the Markdown converter."""

from src.converters.markdown_converter import convert_html_to_markdown


def test_basic_html_conversion():
    """Simple HTML converts to Markdown with frontmatter."""
    html = "<html><head><title>Test Page</title></head><body><h1>Hello</h1><p>World</p></body></html>"
    result = convert_html_to_markdown(html, "https://example.com/test")
    assert result.error is None
    assert "---" in result.markdown  # frontmatter present
    assert "title:" in result.markdown
    assert "source_url:" in result.markdown
    assert result.word_count > 0


def test_sanitization_removes_scripts():
    """Script tags should be removed before conversion."""
    html = '<html><body><h1>Hi</h1><script>alert("xss")</script><p>Content</p></body></html>'
    result = convert_html_to_markdown(html, "https://example.com")
    assert "alert" not in result.markdown
    assert "script" not in result.markdown.lower()


def test_empty_html_returns_error():
    """Empty HTML should still return a result without crashing."""
    result = convert_html_to_markdown("", "https://example.com")
    # Should not raise, may have error or minimal content
    assert result is not None