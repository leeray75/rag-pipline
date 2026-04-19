"""Tests for the LangGraph Audit Agent."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.agents.audit_agent import AuditAgent, run_audit
from src.agents.audit_state import AuditDocument, AuditState
from src.agents.schema_validator import SchemaValidator, validate_markdown


class TestSchemaValidator:
    """Test cases for the SchemaValidator."""

    def test_validate_frontmatter_required_fields(self):
        """Test that frontmatter validation catches missing required fields."""
        content = """---
title: Test
---
Some content"""
        result = validate_markdown(content)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_frontmatter_title_length(self):
        """Test title length constraints."""
        # Too short title
        content = """---
title: Short
description: This is a valid description for testing
---
Content"""
        result = validate_markdown(content)
        assert any("short" in str(e.message).lower() for e in result.warnings)

        # Valid title
        content = """---
title: This is a much longer title that meets the minimum length requirement
description: This is a valid description for testing
---
Content"""
        result = validate_markdown(content)
        # Should have no title-related warnings for a valid title

    def test_validate_heading_hierarchy(self):
        """Test heading hierarchy rules."""
        # Valid hierarchy
        content = """---
title: Test Title
description: Test Description
---
# Main Heading
## Sub Heading
### Sub Sub Heading"""
        result = validate_markdown(content)
        # Should not have heading hierarchy warnings

        # Invalid hierarchy (skipped level)
        content = """---
title: Test Title
description: Test Description
---
# Main Heading
### Skipped Level"""
        result = validate_markdown(content)
        assert len(result.warnings) > 0

    def test_validate_code_block_language(self):
        """Test code block language validation."""
        # Missing language label
        content = """---
title: Test Title
description: Test Description
---
```python
print("Hello")
```"""
        result = validate_markdown(content)
        # Should not have warnings for valid language label

        # Missing language label
        content = """---
title: Test Title
description: Test Description
---
```
No language here
```"""
        result = validate_markdown(content)
        assert len(result.warnings) > 0


class TestAuditAgent:
    """Test cases for the AuditAgent."""

    @pytest.mark.asyncio
    async def test_audit_agent_compiles(self):
        """Test that the audit agent graph compiles correctly."""
        agent = AuditAgent()
        assert agent.graph is not None
        assert agent.validator is not None

    @pytest.mark.asyncio
    async def test_audit_agent_loads_documents(self):
        """Test that the audit agent can load documents."""
        agent = AuditAgent()

        # Create a temporary directory with test documents
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test markdown file
            test_content = """---
title: Test Document Title
description: This is a test document description
url: https://example.com/test
tags: ["test", "example"]
status: published
---
# Test Document

This is a test document with some content.

## Section 1

Some more content here."""
            test_file = tmpdir_path / "test.md"
            test_file.write_text(test_content, encoding="utf-8")

            # Test with the temporary directory
            agent.staging_dir = tmpdir_path

            # Create initial state
            initial_state = {
                "state": AuditState(),
                "current_doc_path": None,
                "result": None,
            }

            # Run the load_documents node
            result = await agent._load_documents(initial_state)
            audit_state = result["state"]

            assert len(audit_state.documents) > 0
            assert audit_state.documents[0].file_path == str(test_file)

    @pytest.mark.asyncio
    async def test_audit_agent_validates_schema(self):
        """Test that the audit agent validates schema correctly."""
        agent = AuditAgent()

        # Create test document
        test_content = """---
title: Test Document Title
description: This is a test document description
url: https://example.com/test
tags: ["test"]
status: published
---
# Test Document

This is a test document with some content."""
        doc = AuditDocument(
            file_path="/test/test.md",
            content=test_content,
            file_name="test.md",
            file_extension=".md",
            file_size=len(test_content),
        )

        # Create state with document
        state = AuditState()
        state.add_document(doc)

        audit_state = {"state": state, "current_doc_path": None, "result": None}

        result = await agent._validate_schema(audit_state)
        audit_state_result = result["state"]

        assert len(audit_state_result.validation_results) > 0

    @pytest.mark.asyncio
    async def test_audit_agent_checks_duplicates(self):
        """Test that the audit agent detects duplicates."""
        agent = AuditAgent()

        # Create two identical documents
        test_content = """---
title: Test Document
description: Test description
---
Content"""
        doc1 = AuditDocument(
            file_path="/test/doc1.md",
            content=test_content,
            file_name="doc1.md",
            file_extension=".md",
            file_size=len(test_content),
        )
        doc2 = AuditDocument(
            file_path="/test/doc2.md",
            content=test_content,
            file_name="doc2.md",
            file_extension=".md",
            file_size=len(test_content),
        )

        state = AuditState()
        state.add_document(doc1)
        state.add_document(doc2)

        audit_state = {"state": state, "current_doc_path": None, "result": None}

        result = await agent._check_duplicates(audit_state)
        audit_state_result = result["state"]

        # Should detect doc2 as duplicate of doc1
        assert len(audit_state_result.duplicate_results) > 0

    def test_audit_agent_should_continue(self):
        """Test the conditional edge logic."""
        agent = AuditAgent()

        # Test when there are more documents
        state = AuditState()
        state.add_document(AuditDocument(
            file_path="/test/doc1.md",
            content="test",
            file_name="doc1.md",
            file_extension=".md",
            file_size=4,
        ))
        state.add_document(AuditDocument(
            file_path="/test/doc2.md",
            content="test",
            file_name="doc2.md",
            file_extension=".md",
            file_size=4,
        ))
        state.current_document_index = 0

        graph_state = {
            "state": state,
            "current_doc_path": None,
            "result": None,
        }

        result = agent._should_continue(graph_state)
        assert result == "process_next"

        # Test when at the last document
        state.current_document_index = 1
        result = agent._should_continue(graph_state)
        assert result == "END"
