"""Tests for schema module."""

from datetime import date

from frontmatter_mcp.schema import infer_schema


class TestInferSchema:
    """Tests for infer_schema function."""

    def test_basic_types(self) -> None:
        """Detect string and array types."""
        records = [
            {"path": "a.md", "date": date(2025, 11, 27), "tags": ["mcp"]},
            {"path": "b.md", "date": date(2025, 11, 26), "tags": ["python", "duckdb"]},
        ]
        schema = infer_schema(records)

        # All non-array values are reported as "string"
        assert schema["date"]["type"] == "string"
        assert schema["date"]["count"] == 2
        assert schema["date"]["nullable"] is False

        # Arrays are detected
        assert schema["tags"]["type"] == "array"
        assert schema["tags"]["count"] == 2

    def test_nullable_detection(self) -> None:
        """Detect nullable fields when some records lack the property."""
        records = [
            {"path": "a.md", "title": "Title A", "summary": "Summary"},
            {"path": "b.md", "title": "Title B"},
        ]
        schema = infer_schema(records)

        assert schema["title"]["nullable"] is False
        assert schema["summary"]["nullable"] is True
        assert schema["summary"]["count"] == 1

    def test_sample_values_unique(self) -> None:
        """Sample values are unique and limited by max_samples."""
        records = [
            {"path": "a.md", "category": "tech"},
            {"path": "b.md", "category": "life"},
            {"path": "c.md", "category": "tech"},
        ]
        schema = infer_schema(records, max_samples=2)

        assert len(schema["category"]["sample_values"]) == 2
        assert "tech" in schema["category"]["sample_values"]
        assert "life" in schema["category"]["sample_values"]

    def test_excludes_path(self) -> None:
        """Path property should not appear in schema."""
        records = [{"path": "a.md", "title": "A"}]
        schema = infer_schema(records)

        assert "path" not in schema
        assert "title" in schema
