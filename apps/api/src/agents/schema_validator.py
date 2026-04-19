"""Document Schema Validator for Markdown documents.

This module provides rule-based validation for Markdown documents,
checking frontmatter structure, title/description constraints,
URL formats, heading hierarchy, code blocks, and word count.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger(__name__)


class ValidationError(BaseModel):
    """Represents a single validation error."""
    field: str
    message: str
    severity: str = Field(default="error")  # "error", "warning", "info"
    line_number: Optional[int] = None


class ValidationSummary(BaseModel):
    """Summary of validation results."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    info: List[ValidationError]
    document_path: Optional[str] = None
    word_count: int = 0
    frontmatter_valid: bool = False


class Frontmatter(BaseModel):
    """Frontmatter model for validation."""
    title: str = ""
    description: str = ""
    url: str = ""
    tags: List[str] = Field(default_factory=list)
    authors: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    status: str = "draft"  # draft, published, archived
    priority: int = Field(default=5, ge=1, le=10)


class MarkdownDocument(BaseModel):
    """Represents a parsed Markdown document."""
    raw_content: str
    frontmatter_raw: str = ""
    frontmatter: Optional[Frontmatter] = None
    body: str = ""
    path: Optional[str] = None


class SchemaValidator:
    """Rule-based schema validator for Markdown documents."""

    # Title constraints
    TITLE_MIN_LENGTH = 10
    TITLE_MAX_LENGTH = 150

    # Description constraints
    DESCRIPTION_MIN_LENGTH = 50
    DESCRIPTION_MAX_LENGTH = 500

    # Word count constraints
    WORD_COUNT_MIN = 100
    WORD_COUNT_MAX = 50000

    # Heading hierarchy rules
    ALLOWED_HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
    H1_MAX_COUNT = 1

    # URL patterns
    URL_PATTERN = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the validator with optional configuration."""
        self.config = config or {}
        self._validate_rules()

    def _validate_rules(self) -> None:
        """Validate that configuration rules are properly set."""
        logger.info("schema_validator.initialized", config=self.config)

    def parse_document(self, content: str, path: Optional[str] = None) -> MarkdownDocument:
        """Parse a Markdown document into its components."""
        raw_content = content.strip()
        frontmatter_raw = ""
        body = raw_content
        frontmatter = None

        # Try to extract frontmatter (YAML format between ---)
        if raw_content.startswith("---"):
            parts = raw_content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_raw = parts[1].strip()
                body = parts[2].strip()

        # Parse YAML frontmatter
        if frontmatter_raw:
            try:
                import yaml
                fm_data = yaml.safe_load(frontmatter_raw) or {}
                frontmatter = Frontmatter(**fm_data)
            except Exception as e:
                logger.warning(
                    "schema_validator.frontmatter_parse_error",
                    error=str(e),
                    raw_content=frontmatter_raw[:100]
                )

        return MarkdownDocument(
            raw_content=raw_content,
            frontmatter_raw=frontmatter_raw,
            frontmatter=frontmatter,
            body=body,
            path=path
        )

    def validate_frontmatter(self, doc: MarkdownDocument) -> List[ValidationError]:
        """Validate frontmatter structure and required fields."""
        errors = []
        fm = doc.frontmatter

        if fm is None:
            errors.append(ValidationError(
                field="frontmatter",
                message="Document missing frontmatter (missing --- delimiters)",
                severity="error"
            ))
            return errors

        # Check required fields
        if not fm.title or fm.title.strip() == "":
            errors.append(ValidationError(
                field="title",
                message="Title is required",
                severity="error"
            ))

        if not fm.description or fm.description.strip() == "":
            errors.append(ValidationError(
                field="description",
                message="Description is required",
                severity="error"
            ))

        # Validate title length
        if fm.title:
            title_len = len(fm.title.strip())
            if title_len < self.TITLE_MIN_LENGTH:
                errors.append(ValidationError(
                    field="title",
                    message=f"Title too short ({title_len} chars), minimum {self.TITLE_MIN_LENGTH}",
                    severity="warning"
                ))
            if title_len > self.TITLE_MAX_LENGTH:
                errors.append(ValidationError(
                    field="title",
                    message=f"Title too long ({title_len} chars), maximum {self.TITLE_MAX_LENGTH}",
                    severity="error"
                ))

        # Validate description length
        if fm.description:
            desc_len = len(fm.description.strip())
            if desc_len < self.DESCRIPTION_MIN_LENGTH:
                errors.append(ValidationError(
                    field="description",
                    message=f"Description too short ({desc_len} chars), minimum {self.DESCRIPTION_MIN_LENGTH}",
                    severity="warning"
                ))
            if desc_len > self.DESCRIPTION_MAX_LENGTH:
                errors.append(ValidationError(
                    field="description",
                    message=f"Description too long ({desc_len} chars), maximum {self.DESCRIPTION_MAX_LENGTH}",
                    severity="error"
                ))

        # Validate URL format
        if fm.url and fm.url.strip():
            if not self.URL_PATTERN.match(fm.url.strip()):
                errors.append(ValidationError(
                    field="url",
                    message=f"Invalid URL format: {fm.url}",
                    severity="error"
                ))

        # Validate priority range
        if fm.priority < 1 or fm.priority > 10:
            errors.append(ValidationError(
                field="priority",
                message=f"Priority must be between 1 and 10, got {fm.priority}",
                severity="error"
            ))

        # Validate status value
        valid_statuses = ["draft", "published", "archived"]
        if fm.status not in valid_statuses:
            errors.append(ValidationError(
                field="status",
                message=f"Invalid status '{fm.status}', must be one of: {valid_statuses}",
                severity="error"
            ))

        return errors

    def validate_heading_hierarchy(self, body: str) -> List[ValidationError]:
        """Validate heading hierarchy and rules."""
        errors = []
        lines = body.split("\n")

        h1_count = 0
        current_level = 0
        prev_level = 0

        for i, line in enumerate(lines, 1):
            # Check for headings
            if line.startswith("#"):
                match = re.match(r"^(#+)\s+(.+)$", line)
                if match:
                    level = len(match.group(1))
                    heading_text = match.group(2).strip()

                    # Count H1s
                    if level == 1:
                        h1_count += 1
                        if h1_count > self.H1_MAX_COUNT:
                            errors.append(ValidationError(
                                field=f"heading_level_1",
                                message=f"Multiple H1 headings found (#{h1_count}). Document should have only one H1.",
                                severity="error",
                                line_number=i
                            ))

                    # Check heading hierarchy
                    if level > prev_level + 1 and prev_level > 0:
                        errors.append(ValidationError(
                            field=f"heading_level_{level}",
                            message=f"Skipped heading level. Found H{level} after H{prev_level}. Should be H{prev_level + 1}.",
                            severity="warning",
                            line_number=i
                        ))

                    prev_level = level

        return errors

    def validate_code_blocks(self, body: str) -> List[ValidationError]:
        """Validate code block language labels."""
        errors = []
        lines = body.split("\n")
        in_code_block = False
        code_block_start = 0

        for i, line in enumerate(lines, 1):
            # Check for code block start/end
            if line.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_block_start = i
                else:
                    in_code_block = False

            # Check language label in opening fence
            if in_code_block and i == code_block_start:
                # Extract language from fence
                match = re.match(r"^```(\w*)", line)
                if match:
                    language = match.group(1)
                    if not language:
                        errors.append(ValidationError(
                            field="code_block",
                            message="Code block missing language label",
                            severity="warning",
                            line_number=i
                        ))

        return errors

    def count_words(self, body: str) -> int:
        """Count words in document body."""
        # Remove code blocks and frontmatter for word count
        text = body

        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`[^`]+`", "", text)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Count words
        words = re.findall(r"\b\w+\b", text)
        return len(words)

    def validate_document(self, content: str, path: Optional[str] = None) -> ValidationSummary:
        """Perform complete validation on a Markdown document."""
        doc = self.parse_document(content, path)

        all_errors: List[ValidationError] = []
        all_warnings: List[ValidationError] = []
        all_info: List[ValidationError] = []

        # Validate frontmatter
        fm_errors = self.validate_frontmatter(doc)
        all_errors.extend(fm_errors)

        # Validate heading hierarchy
        heading_errors = self.validate_heading_hierarchy(doc.body)
        all_warnings.extend(heading_errors)

        # Validate code blocks
        code_errors = self.validate_code_blocks(doc.body)
        all_warnings.extend(code_errors)

        # Count words
        word_count = self.count_words(doc.body)

        # Check word count
        if word_count < self.WORD_COUNT_MIN:
            all_warnings.append(ValidationError(
                field="word_count",
                message=f"Word count ({word_count}) is below minimum ({self.WORD_COUNT_MIN})",
                severity="warning"
            ))
        if word_count > self.WORD_COUNT_MAX:
            all_errors.append(ValidationError(
                field="word_count",
                message=f"Word count ({word_count}) exceeds maximum ({self.WORD_COUNT_MAX})",
                severity="error"
            ))

        # Determine if valid
        is_valid = len(all_errors) == 0
        fm_valid = doc.frontmatter is not None or len(all_errors) == 0

        summary = ValidationSummary(
            is_valid=is_valid,
            errors=all_errors,
            warnings=all_warnings,
            info=all_info,
            document_path=path,
            word_count=word_count,
            frontmatter_valid=fm_valid
        )

        logger.info(
            "schema_validator.validation_complete",
            document_path=path,
            is_valid=is_valid,
            error_count=len(all_errors),
            warning_count=len(all_warnings),
            word_count=word_count
        )

        return summary

    def validate_file(self, file_path: str) -> ValidationSummary:
        """Validate a Markdown file from disk."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text(encoding="utf-8")
        return self.validate_document(content, str(path))


# Convenience function for quick validation
def validate_markdown(
    content: str,
    path: Optional[str] = None
) -> ValidationSummary:
    """Convenience function to validate Markdown content."""
    validator = SchemaValidator()
    return validator.validate_document(content, path)


# Alias for backward compatibility
validate_document = validate_markdown


def validate_file(file_path: str) -> ValidationSummary:
    """Convenience function to validate a Markdown file."""
    validator = SchemaValidator()
    return validator.validate_file(file_path)
