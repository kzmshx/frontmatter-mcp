"""Tests for query_schema module."""

from datetime import date
from typing import Any

from frontmatter_mcp.query_schema import add_frontmatter_columns


class TestAddFrontmatterColumns:
    """Tests for add_frontmatter_columns function."""

    def test_basic_types(self) -> None:
        """Detect string and array types."""
        records = [
            {"path": "a.md", "date": date(2025, 11, 27), "tags": ["mcp"]},
            {"path": "b.md", "date": date(2025, 11, 26), "tags": ["python", "duckdb"]},
        ]
        schema: dict[str, Any] = {}
        add_frontmatter_columns(schema, records)

        # All non-array values are reported as "string"
        assert schema["date"]["type"] == "string"
        assert schema["date"]["nullable"] is False

        # Arrays are detected
        assert schema["tags"]["type"] == "array"

    def test_nullable_detection(self) -> None:
        """Detect nullable fields when some records lack the property."""
        records = [
            {"path": "a.md", "title": "Title A", "summary": "Summary"},
            {"path": "b.md", "title": "Title B"},
        ]
        schema: dict[str, Any] = {}
        add_frontmatter_columns(schema, records)

        assert schema["title"]["nullable"] is False
        assert schema["summary"]["nullable"] is True

    def test_examples_unique(self) -> None:
        """Examples are unique and limited by max_samples."""
        records = [
            {"path": "a.md", "category": "tech"},
            {"path": "b.md", "category": "life"},
            {"path": "c.md", "category": "tech"},
        ]
        schema: dict[str, Any] = {}
        add_frontmatter_columns(schema, records, max_samples=2)

        assert len(schema["category"]["examples"]) == 2
        assert "tech" in schema["category"]["examples"]
        assert "life" in schema["category"]["examples"]

    def test_excludes_path(self) -> None:
        """Path property should not appear in schema."""
        records = [{"path": "a.md", "title": "A"}]
        schema: dict[str, Any] = {}
        add_frontmatter_columns(schema, records)

        assert "path" not in schema
        assert "title" in schema
