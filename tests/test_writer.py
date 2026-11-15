"""Tests for writing frontmatter back to files."""

from pathlib import Path
from typing import Any

import pytest

import frontmatter_mcp.writer as writer_module
from frontmatter_mcp.writer import apply_update, read_metadata, write_metadata


def update_file(
    path: Path,
    base_dir: Path,
    set_values: dict[str, Any] | None = None,
    unset: list[str] | None = None,
) -> dict[str, Any]:
    """Read, update and write one file, as the update tool does."""
    metadata = apply_update(read_metadata(path), set_values, unset)
    if set_values or unset:
        write_metadata(path, metadata)
    return {"path": str(path.relative_to(base_dir)), "frontmatter": metadata}


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
        result = update_file(md_file, tmp_path, {"status": "published"})

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
        result = update_file(md_file, tmp_path, {"status": "published"})

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
        result = update_file(md_file, tmp_path, {"status": "published"}, ["status"])

        assert "status" not in result["frontmatter"]

    def test_set_null_value(self, tmp_path: Path) -> None:
        """Setting null value keeps key with null."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
---
""")
        result = update_file(md_file, tmp_path, {"category": None})

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
        result = update_file(md_file, tmp_path, {"summary": ""})

        assert result["frontmatter"]["summary"] == ""

    def test_set_array_value(self, tmp_path: Path) -> None:
        """Set array value."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
title: Test
---
""")
        result = update_file(md_file, tmp_path, {"tags": ["python", "mcp"]})

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

        result = update_file(md_file, tmp_path, {"title": "New Title"})

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
        update_file(md_file, tmp_path, {"status": "done"})

        content = md_file.read_text()
        assert "# Heading" in content
        assert "Some paragraph." in content
        assert "- List item" in content


class TestWritePost:
    """Tests for write_post function."""

    def test_failure_leaves_original_intact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failure while replacing the file does not touch the original."""
        md_file = tmp_path / "test.md"
        original = "---\ntitle: Test\n---\n# Body\n"
        md_file.write_text(original)

        def broken_replace(*args: object, **kwargs: object) -> None:
            raise OSError("boom")

        monkeypatch.setattr(writer_module.os, "replace", broken_replace)
        with pytest.raises(OSError):
            update_file(md_file, tmp_path, {"status": "done"})

        assert md_file.read_text() == original
        assert list(tmp_path.iterdir()) == [md_file]

    def test_preserves_key_order(self, tmp_path: Path) -> None:
        """Existing keys keep their order and new keys are appended."""
        md_file = tmp_path / "test.md"
        md_file.write_text("---\ndate: 2025-11-01\nweek: w\nday: Sat\n---\nBody\n")

        update_file(md_file, tmp_path, {"tags": ["a"]})

        lines = md_file.read_text().splitlines()
        keys = [line.split(":")[0] for line in lines[1 : lines.index("---", 1)]]
        top_level = [k for k in keys if not k.startswith("-")]
        assert top_level == ["date", "week", "day", "tags"]

    def test_ends_with_newline(self, tmp_path: Path) -> None:
        """The written file ends with a single newline."""
        md_file = tmp_path / "test.md"
        md_file.write_text("---\ntitle: Test\n---\nBody\n")

        update_file(md_file, tmp_path, {"status": "done"})

        assert md_file.read_text().endswith("Body\n")

    def test_preserves_file_mode(self, tmp_path: Path) -> None:
        """The permission bits of the original file are kept."""
        md_file = tmp_path / "test.md"
        md_file.write_text("---\ntitle: Test\n---\nBody\n")
        md_file.chmod(0o644)

        write_metadata(md_file, {"title": "Other"})

        assert md_file.stat().st_mode & 0o777 == 0o644


class TestPreserveStyle:
    """Only changed keys are rewritten; the rest of the file keeps its form."""

    def _write(self, tmp_path: Path, text: str) -> Path:
        md_file = tmp_path / "note.md"
        md_file.write_text(text)
        return md_file

    def test_flow_list_kept_when_other_key_changes(self, tmp_path: Path) -> None:
        md_file = self._write(
            tmp_path, "---\ndate: 2025-11-01\ntags: [a, b]\n---\nBody\n"
        )
        update_file(md_file, tmp_path, {"status": "done"})
        assert md_file.read_text() == (
            "---\ndate: 2025-11-01\ntags: [a, b]\nstatus: done\n---\nBody\n"
        )

    def test_replaced_flow_list_stays_flow(self, tmp_path: Path) -> None:
        md_file = self._write(tmp_path, "---\ntags: [a, b]\n---\nBody\n")
        update_file(md_file, tmp_path, {"tags": ["a", "b", "c"]})
        assert md_file.read_text() == "---\ntags: [a, b, c]\n---\nBody\n"

    def test_replaced_block_list_stays_block(self, tmp_path: Path) -> None:
        md_file = self._write(tmp_path, "---\ntags:\n- a\n---\nBody\n")
        update_file(md_file, tmp_path, {"tags": ["a", "b"]})
        assert md_file.read_text() == "---\ntags:\n- a\n- b\n---\nBody\n"

    def test_new_list_follows_file_style(self, tmp_path: Path) -> None:
        flow = self._write(tmp_path, "---\naliases: [x]\n---\n")
        update_file(flow, tmp_path, {"tags": ["a"]})
        assert flow.read_text() == "---\naliases: [x]\ntags: [a]\n---\n"

        block = tmp_path / "block.md"
        block.write_text("---\ntitle: t\n---\n")
        update_file(block, tmp_path, {"tags": ["a"]})
        assert block.read_text() == "---\ntitle: t\ntags:\n- a\n---\n"

    def test_empty_flow_list_filled_as_flow(self, tmp_path: Path) -> None:
        md_file = self._write(tmp_path, "---\ndate: 2025-11-01\ntags: []\n---\n")
        update_file(md_file, tmp_path, {"tags": ["record/daily"]})
        expected = "---\ndate: 2025-11-01\ntags: [record/daily]\n---\n"
        assert md_file.read_text() == expected

    def test_indented_block_list_keeps_indent(self, tmp_path: Path) -> None:
        md_file = self._write(tmp_path, "---\ntags:\n  - a\n---\n")
        update_file(md_file, tmp_path, {"tags": ["a", "b"]})
        assert md_file.read_text() == "---\ntags:\n  - a\n  - b\n---\n"

    def test_yaml_11_scalars_not_rewritten(self, tmp_path: Path) -> None:
        """`On` reads as True in YAML 1.1; setting another key must not touch it."""
        md_file = self._write(tmp_path, "---\nbrand: On\ntitle: x\n---\n")
        update_file(md_file, tmp_path, {"title": "y"})
        assert md_file.read_text() == "---\nbrand: On\ntitle: y\n---\n"

    def test_file_ending_at_closing_delimiter(self, tmp_path: Path) -> None:
        md_file = self._write(tmp_path, "---\ntitle: x\n---")
        update_file(md_file, tmp_path, {"title": "y"})
        assert md_file.read_text() == "---\ntitle: y\n---"

    def test_quotes_and_comments_kept(self, tmp_path: Path) -> None:
        text = '---\nimage: "[[a.jpg]]"  # cover\ntitle: x\n---\nBody\n'
        md_file = self._write(tmp_path, text)
        update_file(md_file, tmp_path, {"title": "y"})
        assert md_file.read_text() == (
            '---\nimage: "[[a.jpg]]"  # cover\ntitle: y\n---\nBody\n'
        )

    def test_body_kept_byte_for_byte(self, tmp_path: Path) -> None:
        body = "\n\n# H\n\ntext without trailing newline"
        md_file = self._write(tmp_path, "---\ntitle: x\n---\n" + body)
        update_file(md_file, tmp_path, {"title": "y"})
        assert md_file.read_text() == "---\ntitle: y\n---\n" + body

    def test_unset_last_key_removes_block(self, tmp_path: Path) -> None:
        md_file = self._write(tmp_path, "---\ntitle: x\n---\nBody\n")
        update_file(md_file, tmp_path, unset=["title"])
        assert md_file.read_text() == "Body\n"

    def test_long_value_not_wrapped(self, tmp_path: Path) -> None:
        md_file = self._write(tmp_path, "---\ntitle: x\n---\n")
        long = "word " * 40
        update_file(md_file, tmp_path, {"summary": long.strip()})
        assert f"summary: {long.strip()}\n" in md_file.read_text()


class TestWriteMetadata:
    def test_unchanged_values_do_not_touch_the_file(self, tmp_path: Path) -> None:
        md = tmp_path / "a.md"
        md.write_text("---\ntitle: x\n---\nBody\n")
        before = md.stat().st_mtime_ns
        assert write_metadata(md, {"title": "x"}) is False
        assert md.stat().st_mtime_ns == before

    def test_changed_values_are_written(self, tmp_path: Path) -> None:
        md = tmp_path / "a.md"
        md.write_text("---\ntitle: x\n---\nBody\n")
        assert write_metadata(md, {"title": "y"}) is True
        assert md.read_text() == "---\ntitle: y\n---\nBody\n"


def test_apply_update_unset_wins() -> None:
    assert apply_update({"a": 1, "b": 2}, {"a": 3, "c": 4}, ["a"]) == {"b": 2, "c": 4}
