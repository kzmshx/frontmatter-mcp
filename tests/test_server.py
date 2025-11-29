"""Tests for MCP server module."""

import json
import tempfile
from pathlib import Path

import pytest

import frontmatter_mcp.server as server_module


@pytest.fixture
def temp_base_dir():
    """Create a temporary directory with test markdown files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create test files
        (base / "a.md").write_text(
            """---
date: 2025-11-27
tags: [python, mcp]
---
# File A
"""
        )
        (base / "b.md").write_text(
            """---
date: 2025-11-26
tags: [duckdb]
---
# File B
"""
        )
        (base / "subdir").mkdir()
        (base / "subdir" / "c.md").write_text(
            """---
date: 2025-11-25
tags: [python]
summary: A summary
---
# File C
"""
        )

        # Set the global base_dir
        server_module._base_dir = base
        yield base
        server_module._base_dir = None


class TestInspectFrontmatter:
    """Tests for inspect_frontmatter tool."""

    def test_basic_schema(self, temp_base_dir: Path) -> None:
        """Get schema from files."""
        result_json = server_module.inspect_frontmatter("*.md")
        result = json.loads(result_json)

        assert result["file_count"] == 2
        assert "date" in result["schema"]
        assert "tags" in result["schema"]

    def test_recursive_glob(self, temp_base_dir: Path) -> None:
        """Get schema with recursive glob."""
        result_json = server_module.inspect_frontmatter("**/*.md")
        result = json.loads(result_json)

        assert result["file_count"] == 3
        assert "summary" in result["schema"]


class TestQueryFrontmatter:
    """Tests for query_frontmatter tool."""

    def test_select_all(self, temp_base_dir: Path) -> None:
        """Select all files."""
        result_json = server_module.query_frontmatter(
            "**/*.md", "SELECT path FROM files ORDER BY path"
        )
        result = json.loads(result_json)

        assert result["row_count"] == 3
        assert "path" in result["columns"]

    def test_where_clause(self, temp_base_dir: Path) -> None:
        """Filter by date."""
        result_json = server_module.query_frontmatter(
            "**/*.md", "SELECT path FROM files WHERE date >= '2025-11-26'"
        )
        result = json.loads(result_json)

        assert result["row_count"] == 2
        paths = [r["path"] for r in result["results"]]
        assert "a.md" in paths
        assert "b.md" in paths

    def test_tag_contains(self, temp_base_dir: Path) -> None:
        """Filter by tag using from_json."""
        result_json = server_module.query_frontmatter(
            "**/*.md",
            """SELECT path FROM files
               WHERE list_contains(from_json(tags, '["VARCHAR"]'), 'python')""",
        )
        result = json.loads(result_json)

        assert result["row_count"] == 2

    def test_tag_aggregation(self, temp_base_dir: Path) -> None:
        """Aggregate tags using from_json."""
        result_json = server_module.query_frontmatter(
            "**/*.md",
            """
            SELECT tag, COUNT(*) AS count
            FROM files, UNNEST(from_json(tags, '["VARCHAR"]')) AS t(tag)
            GROUP BY tag
            ORDER BY count DESC
            """,
        )
        result = json.loads(result_json)

        assert result["row_count"] == 3
        assert result["results"][0]["tag"] == "python"
        assert result["results"][0]["count"] == 2


class TestUpdateFrontmatter:
    """Tests for update_frontmatter tool."""

    def test_set_property(self, temp_base_dir: Path) -> None:
        """Set a property on a file."""
        result_json = server_module.update_frontmatter(
            "a.md", set={"status": "published"}
        )
        result = json.loads(result_json)

        assert result["path"] == "a.md"
        assert result["frontmatter"]["status"] == "published"
        assert result["frontmatter"]["date"] == "2025-11-27"

    def test_unset_property(self, temp_base_dir: Path) -> None:
        """Unset a property from a file."""
        result_json = server_module.update_frontmatter("b.md", unset=["tags"])
        result = json.loads(result_json)

        assert "tags" not in result["frontmatter"]

    def test_set_and_unset(self, temp_base_dir: Path) -> None:
        """Set and unset properties."""
        result_json = server_module.update_frontmatter(
            "subdir/c.md", set={"status": "done"}, unset=["summary"]
        )
        result = json.loads(result_json)

        assert result["path"] == "subdir/c.md"
        assert result["frontmatter"]["status"] == "done"
        assert "summary" not in result["frontmatter"]

    def test_file_not_found(self, temp_base_dir: Path) -> None:
        """Error when file does not exist."""
        with pytest.raises(FileNotFoundError):
            server_module.update_frontmatter("nonexistent.md", set={"x": 1})

    def test_path_outside_base_dir(self, temp_base_dir: Path) -> None:
        """Error when path is outside base_dir."""
        with pytest.raises(ValueError):
            server_module.update_frontmatter("../outside.md", set={"x": 1})
