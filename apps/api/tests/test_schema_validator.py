"""Tests for the rule-based schema validator."""

from src.agents.schema_validator import validate_document


def test_valid_document_passes():
    """A well-formed document should have zero critical issues."""
    content = """---
title: "Getting Started with MCP"
description: "A comprehensive guide to the Model Context Protocol for beginners and intermediate developers"
source_url: "https://modelcontextprotocol.io/docs/getting-started"
fetched_at: "2026-01-01T00:00:00Z"
tags: ["mcp", "protocol"]
---

# Getting Started with MCP

This is a comprehensive guide to understanding the Model Context Protocol.

""" + "Content paragraph. " * 50  # Ensure > 200 words

    result = validate_document(content, "test.md")
    critical_issues = [i for i in result.errors if i.severity == "error"]
    assert len(critical_issues) == 0
    assert result.is_valid is True


def test_missing_frontmatter_is_critical():
    """Document without frontmatter should have a critical issue."""
    content = "# No Frontmatter\n\nJust body content here."
    result = validate_document(content, "test.md")
    assert result.is_valid is False
    assert any(i.field == "frontmatter" for i in result.errors)


def test_missing_title_is_critical():
    """Missing title in frontmatter should be critical."""
    content = """---
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Heading

Content here.
"""
    result = validate_document(content, "test.md")
    assert any(
        "title" in str(i.message).lower()
        for i in result.errors
    )


def test_multiple_h1_detected():
    """Multiple H1 headings should generate a warning."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# First H1

Some content.

# Second H1

More content.
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.field == "heading_level_1" for i in result.warnings)


def test_skipped_heading_level():
    """H1 -> H3 skip should be detected."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Main Title

### Skipped to H3

Content.
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.field == "heading_level_3" for i in result.warnings)


def test_unlabeled_code_block():
    """Code blocks without language identifiers should be flagged."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Title

```
some code without language
```
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.field == "code_block" for i in result.warnings)


def test_short_content_warning():
    """Documents under 200 words should get a warning."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Title

Short content.
"""
    result = validate_document(content, "test.md")
    assert any(i.field == "word_count" for i in result.warnings)
