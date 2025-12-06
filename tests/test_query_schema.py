"""Tests for query_schema module."""

from datetime import date

from frontmatter_mcp.query_schema import create_base_schema


class TestCreateBaseSchema:
    """Tests for create_base_schema function."""

    def test_basic_types(self) -> None:
        """Detect string and array types."""
        records = [
            {"path": "a.md", "date": date(2025, 11, 27), "tags": ["mcp"]},
            {"path": "b.md", "date": date(2025, 11, 26), "tags": ["python", "duckdb"]},
        ]
        schema = create_base_schema(records)

        # path is always included
        assert "path" in schema
        assert schema["path"]["type"] == "string"
        assert schema["path"]["nullable"] is False

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
        schema = create_base_schema(records)

        assert schema["title"]["nullable"] is False
        assert schema["summary"]["nullable"] is True
        # path is never nullable
        assert schema["path"]["nullable"] is False

    def test_examples_unique(self) -> None:
        """Examples are unique and limited by max_samples."""
        records = [
            {"path": "a.md", "category": "tech"},
            {"path": "b.md", "category": "life"},
            {"path": "c.md", "category": "tech"},
        ]
        schema = create_base_schema(records, max_samples=2)

        assert len(schema["category"]["examples"]) == 2
        assert "tech" in schema["category"]["examples"]
        assert "life" in schema["category"]["examples"]

    def test_path_included(self) -> None:
        """Path property should appear in schema."""
        records = [{"path": "a.md", "title": "A"}]
        schema = create_base_schema(records)

        assert "path" in schema
        assert "title" in schema

    def test_empty_records(self) -> None:
        """Empty records return empty schema."""
        schema = create_base_schema([])
        assert schema == {}
