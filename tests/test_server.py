"""Tests for MCP server module."""

import datetime
import tempfile
from pathlib import Path

import frontmatter
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


class TestQueryInspect:
    """Tests for query_inspect tool."""

    def test_basic_schema(self, temp_base_dir: Path) -> None:
        """Get schema from files."""
        result = server_module.query_inspect("*.md")

        assert result["file_count"] == 2
        assert "date" in result["schema"]
        assert "tags" in result["schema"]

    def test_recursive_glob(self, temp_base_dir: Path) -> None:
        """Get schema with recursive glob."""
        result = server_module.query_inspect("**/*.md")

        assert result["file_count"] == 3
        assert "summary" in result["schema"]


class TestQuery:
    """Tests for query tool."""

    def test_select_all(self, temp_base_dir: Path) -> None:
        """Select all files."""
        result = server_module.query("**/*.md", "SELECT path FROM files ORDER BY path")

        assert result["row_count"] == 3
        assert "path" in result["columns"]

    def test_where_clause(self, temp_base_dir: Path) -> None:
        """Filter by date."""
        result = server_module.query(
            "**/*.md", "SELECT path FROM files WHERE date >= '2025-11-26'"
        )

        assert result["row_count"] == 2
        paths = [r["path"] for r in result["results"]]
        assert "a.md" in paths
        assert "b.md" in paths

    def test_tag_contains(self, temp_base_dir: Path) -> None:
        """Filter by tag using from_json."""
        result = server_module.query(
            "**/*.md",
            """SELECT path FROM files
               WHERE list_contains(from_json(tags, '["VARCHAR"]'), 'python')""",
        )

        assert result["row_count"] == 2

    def test_tag_aggregation(self, temp_base_dir: Path) -> None:
        """Aggregate tags using from_json."""
        result = server_module.query(
            "**/*.md",
            """
            SELECT tag, COUNT(*) AS count
            FROM files, UNNEST(from_json(tags, '["VARCHAR"]')) AS t(tag)
            GROUP BY tag
            ORDER BY count DESC
            """,
        )

        assert result["row_count"] == 3
        assert result["results"][0]["tag"] == "python"
        assert result["results"][0]["count"] == 2


class TestUpdate:
    """Tests for update tool."""

    def test_set_property(self, temp_base_dir: Path) -> None:
        """Set a property on a file."""
        result = server_module.update("a.md", set={"status": "published"})
        assert result["path"] == "a.md"
        assert result["frontmatter"]["status"] == "published"
        assert result["frontmatter"]["date"] == datetime.date(2025, 11, 27)

    def test_unset_property(self, temp_base_dir: Path) -> None:
        """Unset a property from a file."""
        result = server_module.update("b.md", unset=["tags"])
        assert "tags" not in result["frontmatter"]

    def test_set_and_unset(self, temp_base_dir: Path) -> None:
        """Set and unset properties."""
        result = server_module.update(
            "subdir/c.md", set={"status": "done"}, unset=["summary"]
        )
        assert result["path"] == "subdir/c.md"
        assert result["frontmatter"]["status"] == "done"
        assert "summary" not in result["frontmatter"]

    def test_file_not_found(self, temp_base_dir: Path) -> None:
        """Error when file does not exist."""
        with pytest.raises(FileNotFoundError):
            server_module.update("nonexistent.md", set={"x": 1})

    def test_path_outside_base_dir(self, temp_base_dir: Path) -> None:
        """Error when path is outside base_dir."""
        with pytest.raises(ValueError):
            server_module.update("../outside.md", set={"x": 1})


class TestBatchUpdate:
    """Tests for batch_update tool."""

    def test_set_property_all_files(self, temp_base_dir: Path) -> None:
        """Set a property on all matching files."""
        result = server_module.batch_update("*.md", set={"status": "reviewed"})
        assert result["updated_count"] == 2
        assert "a.md" in result["updated_files"]
        assert "b.md" in result["updated_files"]

        post = frontmatter.load(temp_base_dir / "a.md")
        assert post["status"] == "reviewed"

    def test_recursive_glob(self, temp_base_dir: Path) -> None:
        """Update all files including subdirectories."""
        result = server_module.batch_update("**/*.md", set={"batch": True})
        assert result["updated_count"] == 3
        assert "subdir/c.md" in result["updated_files"]

    def test_unset_property(self, temp_base_dir: Path) -> None:
        """Unset a property from all matching files."""
        result = server_module.batch_update("**/*.md", unset=["tags"])
        assert result["updated_count"] == 3

        post = frontmatter.load(temp_base_dir / "a.md")
        assert "tags" not in post.keys()

    def test_set_and_unset(self, temp_base_dir: Path) -> None:
        """Set and unset properties in batch."""
        result = server_module.batch_update(
            "**/*.md", set={"new_prop": "value"}, unset=["date"]
        )
        assert result["updated_count"] == 3

        post = frontmatter.load(temp_base_dir / "b.md")
        assert post["new_prop"] == "value"
        assert "date" not in post.keys()

    def test_no_matching_files(self, temp_base_dir: Path) -> None:
        """Handle no matching files gracefully."""
        result = server_module.batch_update("*.txt", set={"x": 1})
        assert result["updated_count"] == 0
        assert result["updated_files"] == []

    def test_no_warnings_key_when_success(self, temp_base_dir: Path) -> None:
        """Warnings key is absent when all updates succeed."""
        result = server_module.batch_update("*.md", set={"status": "ok"})
        assert result["updated_count"] == 2
        assert "warnings" not in result

    def test_warnings_on_malformed_frontmatter(self, temp_base_dir: Path) -> None:
        """Warnings are populated when file has malformed frontmatter."""
        # Create a file with malformed YAML frontmatter
        (temp_base_dir / "malformed.md").write_text(
            "---\ninvalid: [unclosed\n---\n# Content"
        )

        result = server_module.batch_update("*.md", set={"status": "ok"})
        # a.md and b.md should succeed, malformed.md should fail
        assert result["updated_count"] == 2
        assert "warnings" in result
        assert len(result["warnings"]) == 1
        assert "malformed.md" in result["warnings"][0]
