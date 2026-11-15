"""Tests for the write tools."""

import datetime
from pathlib import Path

import frontmatter
import pytest
from fastmcp.exceptions import ToolError

from frontmatter_mcp import server as tools
from frontmatter_mcp.dependencies import (
    AppState,
    get_settings,
)


class TestUpdate:
    """Tests for update tool."""

    def test_set_property(self, base_dir: Path, state: AppState) -> None:
        """Set a property on a file."""
        result = tools.update(
            path="a.md", set={"status": "published"}, settings=get_settings()
        )
        assert result["path"] == "a.md"
        assert result["frontmatter"]["status"] == "published"
        assert result["frontmatter"]["date"] == datetime.date(2025, 11, 27)

    def test_unset_property(self, base_dir: Path, state: AppState) -> None:
        """Unset a property from a file."""
        result = tools.update(path="b.md", unset=["tags"], settings=get_settings())
        assert "tags" not in result["frontmatter"]

    def test_set_and_unset(self, base_dir: Path, state: AppState) -> None:
        """Set and unset properties."""
        result = tools.update(
            path="subdir/c.md",
            set={"status": "done"},
            unset=["summary"],
            settings=get_settings(),
        )
        assert result["path"] == "subdir/c.md"
        assert result["frontmatter"]["status"] == "done"
        assert "summary" not in result["frontmatter"]

    def test_file_not_found(self, base_dir: Path, state: AppState) -> None:
        """Error when file does not exist."""
        with pytest.raises(ToolError, match="File not found"):
            tools.update(path="nonexistent.md", set={"x": 1}, settings=get_settings())

    def test_path_outside_base_dir(self, base_dir: Path, state: AppState) -> None:
        """Error when path is outside base_dir."""
        with pytest.raises(ToolError, match="within the base directory"):
            tools.update(path="../outside.md", set={"x": 1}, settings=get_settings())


class TestBatchUpdate:
    """Tests for batch_update tool."""

    def test_set_property_all_files(self, base_dir: Path, state: AppState) -> None:
        """Set a property on all matching files."""
        result = tools.batch_update(
            glob="*.md", set={"status": "reviewed"}, settings=get_settings()
        )
        assert result["updated_count"] == 2
        assert "a.md" in result["updated_files"]
        assert "b.md" in result["updated_files"]

        post = frontmatter.load(base_dir / "a.md")
        assert post["status"] == "reviewed"

    def test_recursive_glob(self, base_dir: Path, state: AppState) -> None:
        """Update all files including subdirectories."""
        result = tools.batch_update(
            glob="**/*.md", set={"batch": True}, settings=get_settings()
        )
        assert result["updated_count"] == 3
        assert "subdir/c.md" in result["updated_files"]

    def test_unset_property(self, base_dir: Path, state: AppState) -> None:
        """Unset a property from all matching files."""
        result = tools.batch_update(
            glob="**/*.md", unset=["tags"], settings=get_settings()
        )
        assert result["updated_count"] == 3

        post = frontmatter.load(base_dir / "a.md")
        assert "tags" not in post.keys()

    def test_set_and_unset(self, base_dir: Path, state: AppState) -> None:
        """Set and unset properties in batch."""
        result = tools.batch_update(
            glob="**/*.md",
            set={"new_prop": "value"},
            unset=["date"],
            settings=get_settings(),
        )
        assert result["updated_count"] == 3

        post = frontmatter.load(base_dir / "b.md")
        assert post["new_prop"] == "value"
        assert "date" not in post.keys()

    def test_no_matching_files(self, base_dir: Path, state: AppState) -> None:
        """Handle no matching files gracefully."""
        result = tools.batch_update(glob="*.txt", set={"x": 1}, settings=get_settings())
        assert result["updated_count"] == 0
        assert result["updated_files"] == []

    def test_no_warnings_key_when_success(
        self, base_dir: Path, state: AppState
    ) -> None:
        """Warnings key is absent when all updates succeed."""
        result = tools.batch_update(
            glob="*.md", set={"status": "ok"}, settings=get_settings()
        )
        assert result["updated_count"] == 2
        assert "warnings" not in result

    def test_warnings_on_malformed_frontmatter(
        self, base_dir: Path, state: AppState
    ) -> None:
        """Warnings are populated when file has malformed frontmatter."""
        # Create a file with malformed YAML frontmatter
        (base_dir / "malformed.md").write_text(
            "---\ninvalid: [unclosed\n---\n# Content"
        )

        result = tools.batch_update(
            glob="*.md", set={"status": "ok"}, settings=get_settings()
        )
        # a.md and b.md should succeed, malformed.md should fail
        assert result["updated_count"] == 2
        assert "warnings" in result
        assert len(result["warnings"]) == 1
        assert result["warnings"][0]["path"] == "malformed.md"


class TestBatchArrayAdd:
    """Tests for batch_array_add tool."""

    def test_add_value_to_existing_array(self, base_dir: Path, state: AppState) -> None:
        """Add a value to an existing array property."""
        result = tools.batch_array_add(
            glob="*.md", property="tags", value="new-tag", settings=get_settings()
        )
        assert result["updated_count"] == 2
        assert "a.md" in result["updated_files"]

        post = frontmatter.load(base_dir / "a.md")
        assert "new-tag" in post["tags"]

    def test_skip_duplicate_value(self, base_dir: Path, state: AppState) -> None:
        """Skip files where value already exists (allow_duplicates=False)."""
        result = tools.batch_array_add(
            glob="*.md", property="tags", value="python", settings=get_settings()
        )
        # a.md has [python, mcp], b.md has [duckdb]
        # a.md is skipped (python already exists), b.md is updated
        assert result["updated_count"] == 1
        assert "b.md" in result["updated_files"]

    def test_allow_duplicates(self, base_dir: Path, state: AppState) -> None:
        """Allow duplicate values when allow_duplicates=True."""
        result = tools.batch_array_add(
            glob="*.md",
            property="tags",
            value="python",
            allow_duplicates=True,
            settings=get_settings(),
        )
        assert result["updated_count"] == 2

        post = frontmatter.load(base_dir / "a.md")
        assert post["tags"].count("python") == 2

    def test_create_property_if_not_exists(
        self, base_dir: Path, state: AppState
    ) -> None:
        """Create array property if it doesn't exist."""
        result = tools.batch_array_add(
            glob="*.md", property="categories", value="blog", settings=get_settings()
        )
        assert result["updated_count"] == 2

        post = frontmatter.load(base_dir / "a.md")
        assert post["categories"] == ["blog"]

    def test_skip_non_array_property(self, base_dir: Path, state: AppState) -> None:
        """Skip and warn when property is not an array."""
        result = tools.batch_array_add(
            glob="*.md", property="date", value="value", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" in result
        assert len(result["warnings"]) == 2

    def test_value_as_array_not_flattened(
        self, base_dir: Path, state: AppState
    ) -> None:
        """Array value should be added as single element, not flattened."""
        result = tools.batch_array_add(
            glob="*.md",
            property="tags",
            value=["nested", "array"],
            settings=get_settings(),
        )
        assert result["updated_count"] == 2

        post = frontmatter.load(base_dir / "a.md")
        assert ["nested", "array"] in post["tags"]


class TestBatchArrayRemove:
    """Tests for batch_array_remove tool."""

    def test_remove_value_from_array(self, base_dir: Path, state: AppState) -> None:
        """Remove a value from array property."""
        result = tools.batch_array_remove(
            glob="**/*.md", property="tags", value="python", settings=get_settings()
        )
        # a.md and c.md have python tag
        assert result["updated_count"] == 2

        post = frontmatter.load(base_dir / "a.md")
        assert "python" not in post["tags"]

    def test_skip_if_value_not_exists(self, base_dir: Path, state: AppState) -> None:
        """Skip files where value doesn't exist."""
        result = tools.batch_array_remove(
            glob="*.md", property="tags", value="nonexistent", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_if_property_not_exists(self, base_dir: Path, state: AppState) -> None:
        """Skip files where property doesn't exist."""
        result = tools.batch_array_remove(
            glob="*.md", property="categories", value="value", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, base_dir: Path, state: AppState) -> None:
        """Skip and warn when property is not an array."""
        result = tools.batch_array_remove(
            glob="*.md", property="date", value="value", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestBatchArrayReplace:
    """Tests for batch_array_replace tool."""

    def test_replace_value_in_array(self, base_dir: Path, state: AppState) -> None:
        """Replace a value in array property."""
        result = tools.batch_array_replace(
            glob="**/*.md",
            property="tags",
            old_value="python",
            new_value="py",
            settings=get_settings(),
        )
        assert result["updated_count"] == 2

        post = frontmatter.load(base_dir / "a.md")
        assert "py" in post["tags"]
        assert "python" not in post["tags"]

    def test_skip_if_old_value_not_exists(
        self, base_dir: Path, state: AppState
    ) -> None:
        """Skip files where old_value doesn't exist."""
        result = tools.batch_array_replace(
            glob="*.md",
            property="tags",
            old_value="nonexistent",
            new_value="new",
            settings=get_settings(),
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_if_property_not_exists(self, base_dir: Path, state: AppState) -> None:
        """Skip files where property doesn't exist."""
        result = tools.batch_array_replace(
            glob="*.md",
            property="categories",
            old_value="old",
            new_value="new",
            settings=get_settings(),
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, base_dir: Path, state: AppState) -> None:
        """Skip and warn when property is not an array."""
        result = tools.batch_array_replace(
            glob="*.md",
            property="date",
            old_value="old",
            new_value="new",
            settings=get_settings(),
        )
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestBatchArraySort:
    """Tests for batch_array_sort tool."""

    def test_sort_array_ascending(self, base_dir: Path, state: AppState) -> None:
        """Sort array in ascending order."""
        result = tools.batch_array_sort(
            glob="*.md", property="tags", settings=get_settings()
        )
        # a.md has [python, mcp] -> [mcp, python] (updated)
        # b.md has [duckdb] (single element, already sorted, skipped)
        assert result["updated_count"] == 1
        assert "a.md" in result["updated_files"]

        post = frontmatter.load(base_dir / "a.md")
        assert post["tags"] == ["mcp", "python"]

    def test_sort_array_descending(self, base_dir: Path, state: AppState) -> None:
        """Sort array in descending order."""
        result = tools.batch_array_sort(
            glob="*.md", property="tags", reverse=True, settings=get_settings()
        )
        # a.md has [python, mcp] - already descending order (skipped)
        # b.md has [duckdb] (single element, already sorted, skipped)
        assert result["updated_count"] == 0

    def test_sort_array_descending_updated(
        self, base_dir: Path, state: AppState
    ) -> None:
        """Sort array in descending order when not already sorted."""
        # First sort ascending
        tools.batch_array_sort(glob="*.md", property="tags", settings=get_settings())
        # Now a.md has [mcp, python], reverse should update it
        result = tools.batch_array_sort(
            glob="*.md", property="tags", reverse=True, settings=get_settings()
        )
        assert result["updated_count"] == 1

        post = frontmatter.load(base_dir / "a.md")
        assert post["tags"] == ["python", "mcp"]

    def test_skip_if_already_sorted(self, base_dir: Path, state: AppState) -> None:
        """Skip files where array is already sorted."""
        # First sort
        tools.batch_array_sort(glob="*.md", property="tags", settings=get_settings())
        # Second sort should skip
        result = tools.batch_array_sort(
            glob="*.md", property="tags", settings=get_settings()
        )
        assert result["updated_count"] == 0

    def test_skip_empty_array(self, base_dir: Path, state: AppState) -> None:
        """Skip files with empty array."""
        (base_dir / "empty.md").write_text("---\ntags: []\n---\n# Empty")

        result = tools.batch_array_sort(
            glob="empty.md", property="tags", settings=get_settings()
        )
        assert result["updated_count"] == 0

    def test_skip_if_property_not_exists(self, base_dir: Path, state: AppState) -> None:
        """Skip files where property doesn't exist."""
        result = tools.batch_array_sort(
            glob="*.md", property="categories", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, base_dir: Path, state: AppState) -> None:
        """Skip and warn when property is not an array."""
        result = tools.batch_array_sort(
            glob="*.md", property="date", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestBatchArrayUnique:
    """Tests for batch_array_unique tool."""

    def test_remove_duplicates(self, base_dir: Path, state: AppState) -> None:
        """Remove duplicate values from array."""
        (base_dir / "dup.md").write_text("---\ntags: [a, b, a, c, b]\n---\n# Dup")

        result = tools.batch_array_unique(
            glob="dup.md", property="tags", settings=get_settings()
        )
        assert result["updated_count"] == 1
        assert "dup.md" in result["updated_files"]

        post = frontmatter.load(base_dir / "dup.md")
        assert post["tags"] == ["a", "b", "c"]

    def test_preserve_order(self, base_dir: Path, state: AppState) -> None:
        """Preserve first occurrence order when removing duplicates."""
        content = "---\ntags: [z, a, z, m, a]\n---\n# Order"
        (base_dir / "order.md").write_text(content)

        result = tools.batch_array_unique(
            glob="order.md", property="tags", settings=get_settings()
        )
        assert result["updated_count"] == 1

        post = frontmatter.load(base_dir / "order.md")
        assert post["tags"] == ["z", "a", "m"]

    def test_skip_if_no_duplicates(self, base_dir: Path, state: AppState) -> None:
        """Skip files where array has no duplicates."""
        result = tools.batch_array_unique(
            glob="a.md", property="tags", settings=get_settings()
        )
        # a.md has [python, mcp] - no duplicates
        assert result["updated_count"] == 0

    def test_skip_empty_array(self, base_dir: Path, state: AppState) -> None:
        """Skip files with empty array."""
        (base_dir / "empty.md").write_text("---\ntags: []\n---\n# Empty")

        result = tools.batch_array_unique(
            glob="empty.md", property="tags", settings=get_settings()
        )
        assert result["updated_count"] == 0

    def test_skip_single_element(self, base_dir: Path, state: AppState) -> None:
        """Skip files with single element array."""
        result = tools.batch_array_unique(
            glob="b.md", property="tags", settings=get_settings()
        )
        # b.md has [duckdb] - single element
        assert result["updated_count"] == 0

    def test_skip_if_property_not_exists(self, base_dir: Path, state: AppState) -> None:
        """Skip files where property doesn't exist."""
        result = tools.batch_array_unique(
            glob="*.md", property="categories", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, base_dir: Path, state: AppState) -> None:
        """Skip and warn when property is not an array."""
        result = tools.batch_array_unique(
            glob="*.md", property="date", settings=get_settings()
        )
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestWriteBehavior:
    """Behavior shared by the write tools."""

    def test_batch_update_skips_files_already_up_to_date(
        self, base_dir: Path, state: AppState
    ) -> None:
        (base_dir / "a.md").write_text("---\nstatus: done\n---\n")
        (base_dir / "b.md").write_text("---\nstatus: todo\n---\n")
        before = (base_dir / "a.md").stat().st_mtime_ns
        result = tools.batch_update(
            glob="*.md", set={"status": "done"}, settings=state.settings
        )
        assert result["updated_files"] == ["b.md"]
        assert (base_dir / "a.md").stat().st_mtime_ns == before

    def test_remove_removes_every_occurrence(
        self, base_dir: Path, state: AppState
    ) -> None:
        (base_dir / "a.md").write_text("---\ntags: [x, y, x]\n---\n")
        tools.batch_array_remove(
            glob="a.md", property="tags", value="x", settings=state.settings
        )
        assert "tags: [y]" in (base_dir / "a.md").read_text()

    def test_warnings_have_path_and_error(
        self, base_dir: Path, state: AppState
    ) -> None:
        (base_dir / "a.md").write_text("---\ntags: notalist\n---\n")
        result = tools.batch_array_add(
            glob="a.md", property="tags", value="x", settings=state.settings
        )
        assert result["warnings"] == [
            {"path": "a.md", "error": "skipped: 'tags' is not an array"}
        ]

    def test_update_reports_whether_it_wrote(
        self, base_dir: Path, state: AppState
    ) -> None:
        first = tools.update(path="a.md", set={"s": "x"}, settings=state.settings)
        second = tools.update(path="a.md", set={"s": "x"}, settings=state.settings)
        assert (first["updated"], second["updated"]) == (True, False)
