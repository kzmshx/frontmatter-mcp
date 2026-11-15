"""Tests for reading frontmatter into records."""

import os
from datetime import date
from pathlib import Path

from frontmatter_mcp.records import FileRecordCache, parse_file, parse_files


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestParseFile:
    def test_with_frontmatter(self, tmp_path: Path) -> None:
        md = _write(
            tmp_path / "test.md",
            "---\ndate: 2025-11-27\ntags: [mcp, python]\nsummary: S\n---\n# C\n",
        )
        record, warning = parse_file(md, tmp_path)
        assert record == {
            "path": "test.md",
            "date": date(2025, 11, 27),
            "tags": ["mcp", "python"],
            "summary": "S",
        }
        assert warning is None

    def test_without_frontmatter(self, tmp_path: Path) -> None:
        md = _write(tmp_path / "plain.md", "# Just content\n")
        record, _ = parse_file(md, tmp_path)
        assert record == {"path": "plain.md"}

    def test_nested_path_is_relative(self, tmp_path: Path) -> None:
        md = _write(tmp_path / "atoms/sub/nested.md", "---\ntitle: N\n---\n")
        record, _ = parse_file(md, tmp_path)
        assert record["path"] == "atoms/sub/nested.md"

    def test_path_key_is_reserved(self, tmp_path: Path) -> None:
        """A frontmatter key named path must not replace the file path."""
        md = _write(tmp_path / "real.md", "---\npath: elsewhere.md\ntitle: T\n---\n")
        record, warning = parse_file(md, tmp_path)
        assert record == {"path": "real.md", "title": "T"}
        assert warning is not None and "reserved" in warning["error"]


class TestParseFiles:
    def test_parses_and_caches(self, tmp_path: Path) -> None:
        a = _write(tmp_path / "a.md", "---\ntitle: A\n---\n")
        b = _write(tmp_path / "b.md", "---\ntitle: B\n---\n")
        cache = FileRecordCache()
        records, warnings = parse_files([a, b], tmp_path, cache)
        assert [r["title"] for r in records] == ["A", "B"]
        assert warnings == []
        assert cache.get(a, a.stat().st_mtime) is not None

    def test_uses_cache_until_mtime_changes(self, tmp_path: Path) -> None:
        md = _write(tmp_path / "a.md", "---\ntitle: A\n---\n")
        cache = FileRecordCache()
        parse_files([md], tmp_path, cache)
        mtime = md.stat().st_mtime

        md.write_text("---\ntitle: changed\n---\n")
        os.utime(md, (mtime, mtime))  # same mtime: cached record is used
        records, _ = parse_files([md], tmp_path, cache)
        assert records[0]["title"] == "A"

        os.utime(md, (mtime + 10, mtime + 10))
        records, _ = parse_files([md], tmp_path, cache)
        assert records[0]["title"] == "changed"

    def test_errors_become_warnings(self, tmp_path: Path) -> None:
        good = _write(tmp_path / "good.md", "---\ntitle: ok\n---\n")
        bad = _write(tmp_path / "bad.md", "---\ninvalid: [unclosed\n---\n")
        records, warnings = parse_files([good, bad], tmp_path, FileRecordCache())
        assert [r["path"] for r in records] == ["good.md"]
        assert [w["path"] for w in warnings] == ["bad.md"]

    def test_reserved_key_warning_is_repeated_from_cache(self, tmp_path: Path) -> None:
        md = _write(tmp_path / "a.md", "---\npath: x\n---\n")
        cache = FileRecordCache()
        parse_files([md], tmp_path, cache)
        _, warnings = parse_files([md], tmp_path, cache)
        assert len(warnings) == 1
