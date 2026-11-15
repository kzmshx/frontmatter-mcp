"""Tests for locating files under the base directory."""

from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from frontmatter_mcp.paths import collect_files, list_markdown_files, resolve_file


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    return path


def test_collect_files_sorted_and_recursive(tmp_path: Path) -> None:
    _touch(tmp_path / "b.md")
    _touch(tmp_path / "a.md")
    _touch(tmp_path / "sub/c.md")
    names = [
        p.relative_to(tmp_path).as_posix() for p in collect_files(tmp_path, "**/*.md")
    ]
    assert names == ["a.md", "b.md", "sub/c.md"]


def test_collect_files_base_dir_with_glob_characters(tmp_path: Path) -> None:
    base = tmp_path / "vault [2025]"
    _touch(base / "a.md")
    assert [p.name for p in collect_files(base, "*.md")] == ["a.md"]


def test_collect_files_never_leaves_base_dir(tmp_path: Path) -> None:
    base = tmp_path / "vault"
    _touch(base / "in.md")
    _touch(tmp_path / "out.md")
    assert collect_files(base, "../*.md") == []
    assert collect_files(base, str(tmp_path / "*.md")) == []


def test_collect_files_drops_symlinks_out_of_base_dir(tmp_path: Path) -> None:
    base = tmp_path / "vault"
    outside = _touch(tmp_path / "secret.md")
    base.mkdir()
    (base / "link.md").symlink_to(outside)
    assert collect_files(base, "*.md") == []


def test_list_markdown_files_skips_dot_directories(tmp_path: Path) -> None:
    _touch(tmp_path / "a.md")
    _touch(tmp_path / ".obsidian/x.md")
    _touch(tmp_path / "sub/.hidden/y.md")
    assert [p.name for p in list_markdown_files(tmp_path)] == ["a.md"]


def test_resolve_file(tmp_path: Path) -> None:
    md = _touch(tmp_path / "a.md")
    assert resolve_file(tmp_path, "a.md") == md
    with pytest.raises(ToolError, match="not found"):
        resolve_file(tmp_path, "missing.md")
    with pytest.raises(ToolError, match="within the base directory"):
        resolve_file(tmp_path, "../a.md")
