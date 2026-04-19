from src.agents.schema_validator import SchemaValidator, ValidationSummary, validate_markdown

# Alias for backward compatibility
validate_document = validate_markdown

__all__ = ["SchemaValidator", "ValidationSummary", "validate_markdown", "validate_document"]
