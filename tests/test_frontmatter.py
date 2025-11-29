"""Tests for frontmatter module."""

from datetime import date
from pathlib import Path

from frontmatter_mcp.frontmatter import (
    parse_file,
    parse_files,
    update_file,
)


class TestParseFile:
    """Tests for parse_file function."""

    def test_parse_file_with_frontmatter(self, tmp_path: Path) -> None:
        """Parse a file with valid frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
date: 2025-11-27
tags: [mcp, python]
summary: Test summary
---
# Content
""")
        result = parse_file(md_file, tmp_path)

        assert result["path"] == "test.md"
        assert result["date"] == date(2025, 11, 27)
        assert result["tags"] == ["mcp", "python"]
        assert result["summary"] == "Test summary"

    def test_parse_file_without_frontmatter(self, tmp_path: Path) -> None:
        """Parse a file without frontmatter returns only path."""
        md_file = tmp_path / "no_frontmatter.md"
        md_file.write_text("# Just content\n\nNo frontmatter here.")

        result = parse_file(md_file, tmp_path)

        assert result["path"] == "no_frontmatter.md"
        assert len(result) == 1

    def test_parse_file_nested_path(self, tmp_path: Path) -> None:
        """Parse a file in a nested directory returns relative path."""
        nested_dir = tmp_path / "atoms" / "sub"
        nested_dir.mkdir(parents=True)
        md_file = nested_dir / "nested.md"
        md_file.write_text("""---
title: Nested
---
""")
        result = parse_file(md_file, tmp_path)

        assert result["path"] == "atoms/sub/nested.md"


class TestParseFiles:
    """Tests for parse_files function."""

    def test_parse_multiple_files(self, tmp_path: Path) -> None:
        """Parse multiple files successfully."""
        file1 = tmp_path / "a.md"
        file1.write_text("""---
date: 2025-11-27
---
""")
        file2 = tmp_path / "b.md"
        file2.write_text("""---
date: 2025-11-26
---
""")
        records, warnings = parse_files([file1, file2], tmp_path)

        assert len(records) == 2
        assert len(warnings) == 0
        assert records[0]["path"] == "a.md"
        assert records[1]["path"] == "b.md"

    def test_parse_files_with_invalid_yaml(self, tmp_path: Path) -> None:
        """Skip files with invalid YAML and report warnings."""
        valid_file = tmp_path / "valid.md"
        valid_file.write_text("""---
title: Valid
---
""")
        invalid_file = tmp_path / "invalid.md"
        invalid_file.write_text("""---
invalid: yaml: content: [
---
""")
        records, warnings = parse_files([valid_file, invalid_file], tmp_path)

        assert len(records) == 1
        assert records[0]["path"] == "valid.md"
        assert len(warnings) == 1
        assert warnings[0]["path"] == "invalid.md"
        assert "error" in warnings[0]


class TestUpdateFile:
    """Tests for update_file function."""

    def test_set_new_property(self, tmp_path: Path) -> None:
        """Add a new property to frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Original
---
# Content
""")
        result = update_file(md_file, tmp_path, set_values={"status": "published"})

        assert result["path"] == "test.md"
        assert result["frontmatter"]["title"] == "Original"
        assert result["frontmatter"]["status"] == "published"

        # Verify file was updated
        content = md_file.read_text()
        assert "status: published" in content
        assert "# Content" in content

    def test_overwrite_existing_property(self, tmp_path: Path) -> None:
        """Overwrite an existing property."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Original
status: draft
---
""")
        result = update_file(md_file, tmp_path, set_values={"status": "published"})

        assert result["frontmatter"]["title"] == "Original"
        assert result["frontmatter"]["status"] == "published"

    def test_unset_property(self, tmp_path: Path) -> None:
        """Remove a property from frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
draft: true
---
""")
        result = update_file(md_file, tmp_path, unset=["draft"])

        assert result["frontmatter"]["title"] == "Test"
        assert "draft" not in result["frontmatter"]

        content = md_file.read_text()
        assert "draft" not in content

    def test_set_and_unset_same_key_unset_wins(self, tmp_path: Path) -> None:
        """When same key in set and unset, unset takes priority."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
status: draft
---
""")
        result = update_file(
            md_file, tmp_path, set_values={"status": "published"}, unset=["status"]
        )

        assert "status" not in result["frontmatter"]

    def test_set_null_value(self, tmp_path: Path) -> None:
        """Setting null value keeps key with null."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
---
""")
        result = update_file(md_file, tmp_path, set_values={"category": None})

        assert result["frontmatter"]["category"] is None

        content = md_file.read_text()
        assert "category:" in content

    def test_set_empty_string(self, tmp_path: Path) -> None:
        """Setting empty string keeps key with empty value."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
---
""")
        result = update_file(md_file, tmp_path, set_values={"summary": ""})

        assert result["frontmatter"]["summary"] == ""

    def test_set_array_value(self, tmp_path: Path) -> None:
        """Set array value."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
---
""")
        result = update_file(md_file, tmp_path, set_values={"tags": ["python", "mcp"]})

        assert result["frontmatter"]["tags"] == ["python", "mcp"]

    def test_no_changes_returns_current(self, tmp_path: Path) -> None:
        """When no set or unset, return current frontmatter unchanged."""
        md_file = tmp_path / "test.md"
        original = """---
title: Test
---
# Content
"""
        md_file.write_text(original)
        result = update_file(md_file, tmp_path)

        assert result["frontmatter"]["title"] == "Test"
        assert md_file.read_text() == original

    def test_file_without_frontmatter_creates_it(self, tmp_path: Path) -> None:
        """File without frontmatter gets frontmatter added."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Just content\n\nNo frontmatter.")

        result = update_file(md_file, tmp_path, set_values={"title": "New Title"})

        assert result["frontmatter"]["title"] == "New Title"

        content = md_file.read_text()
        assert content.startswith("---\n")
        assert "title: New Title" in content
        assert "# Just content" in content

    def test_preserves_content(self, tmp_path: Path) -> None:
        """Content after frontmatter is preserved."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
---
# Heading

Some paragraph.

- List item
""")
        update_file(md_file, tmp_path, set_values={"status": "done"})

        content = md_file.read_text()
        assert "# Heading" in content
        assert "Some paragraph." in content
        assert "- List item" in content
