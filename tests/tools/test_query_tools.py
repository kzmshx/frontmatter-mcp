"""Tests for the query tools."""

from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from frontmatter_mcp import server as tools
from frontmatter_mcp.dependencies import (
    AppState,
    get_state,
)
from frontmatter_mcp.semantic import SemanticContext
from tests.conftest import tool_deps


class TestQueryInspect:
    """Tests for query_inspect tool."""

    def test_basic_schema(self, base_dir: Path, state: AppState) -> None:
        """Get schema from files."""
        result = tools.query_inspect(glob="*.md", **tool_deps(get_state()))
        assert result["file_count"] == 2
        assert "date" in result["schema"]
        assert "tags" in result["schema"]

    def test_recursive_glob(self, base_dir: Path, state: AppState) -> None:
        """Get schema with recursive glob."""
        result = tools.query_inspect(glob="**/*.md", **tool_deps(get_state()))
        assert result["file_count"] == 3
        assert "summary" in result["schema"]


class TestQuery:
    """Tests for query tool."""

    def test_excluded_files_are_invisible(
        self, base_dir: Path, state: AppState
    ) -> None:
        state.settings.exclude = ["subdir"]
        result = tools.query(
            glob="**/*.md",
            sql="SELECT path FROM files ORDER BY path",
            **tool_deps(get_state()),
        )
        assert [r["path"] for r in result["results"]] == ["a.md", "b.md"]

    def test_select_all(self, base_dir: Path, state: AppState) -> None:
        """Select all files."""
        result = tools.query(
            glob="**/*.md",
            sql="SELECT path FROM files ORDER BY path",
            **tool_deps(get_state()),
        )
        assert result["row_count"] == 3
        assert "path" in result["columns"]

    def test_where_clause(self, base_dir: Path, state: AppState) -> None:
        """Filter by date."""
        result = tools.query(
            glob="**/*.md",
            sql="SELECT path FROM files WHERE date >= '2025-11-26'",
            **tool_deps(get_state()),
        )
        assert result["row_count"] == 2
        paths = [r["path"] for r in result["results"]]
        assert "a.md" in paths
        assert "b.md" in paths

    def test_tag_contains(self, base_dir: Path, state: AppState) -> None:
        """Filter by tag using from_json."""
        result = tools.query(
            glob="**/*.md",
            sql="""SELECT path FROM files
               WHERE list_contains(from_json(tags, '["VARCHAR"]'), 'python')""",
            **tool_deps(get_state()),
        )
        assert result["row_count"] == 2

    def test_tag_aggregation(self, base_dir: Path, state: AppState) -> None:
        """Aggregate tags using from_json."""
        result = tools.query(
            glob="**/*.md",
            sql="""
            SELECT tag, COUNT(*) AS count
            FROM files, UNNEST(from_json(tags, '["VARCHAR"]')) AS t(tag)
            GROUP BY tag
            ORDER BY count DESC
            """,
            **tool_deps(get_state()),
        )
        assert result["row_count"] == 3
        assert result["results"][0]["tag"] == "python"
        assert result["results"][0]["count"] == 2

    def test_cannot_read_files_outside_base_dir(
        self, base_dir: Path, state: AppState, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """SQL cannot read arbitrary files."""
        secret = tmp_path_factory.mktemp("outside") / "secret.txt"
        secret.write_text("secret")
        with pytest.raises(Exception, match="Permission Error"):
            tools.query(
                glob="**/*.md",
                sql=f"SELECT * FROM read_text('{secret}')",
                **tool_deps(get_state()),
            )

    def test_cannot_write_files(
        self, base_dir: Path, state: AppState, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """SQL cannot write files with COPY ... TO."""
        target = tmp_path_factory.mktemp("outside") / "out.csv"
        with pytest.raises(Exception, match="Permission Error"):
            tools.query(
                glob="**/*.md",
                sql=f"COPY (SELECT path FROM files) TO '{target}'",
                **tool_deps(get_state()),
            )
        assert not target.exists()

    def test_cannot_reenable_external_access(
        self, base_dir: Path, state: AppState
    ) -> None:
        """SQL cannot lift the restriction."""
        with pytest.raises(Exception, match="Cannot change configuration"):
            tools.query(
                glob="**/*.md",
                sql="SET enable_external_access = true",
                **tool_deps(get_state()),
            )

    def test_glob_cannot_escape_base_dir(self, base_dir: Path, state: AppState) -> None:
        """A glob with .. does not match files outside base_dir."""
        outside = base_dir.parent / f"{base_dir.name}-outside.md"
        outside.write_text("---\ntitle: outside\n---\n")
        try:
            result = tools.query(
                glob=f"../{outside.name}",
                sql="SELECT path FROM files",
                **tool_deps(get_state()),
            )
            assert result["row_count"] == 0
        finally:
            outside.unlink()


class TestQueryBehavior:
    def test_columns_start_with_path(self, base_dir: Path, state: AppState) -> None:
        result = tools.query(
            glob="**/*.md", sql="SELECT * FROM files", **tool_deps(state)
        )
        assert result["columns"][0] == "path"

    def test_sql_errors_name_the_columns(self, base_dir: Path, state: AppState) -> None:
        with pytest.raises(ToolError, match="Columns of the files table: path"):
            tools.query(glob="*.md", sql="SELECT nope FROM files", **tool_deps(state))

    def test_word_containing_embed_does_not_start_indexing(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        tools.query(
            glob="*.md",
            sql="SELECT path FROM files WHERE path LIKE '%embedded%'",
            **tool_deps(get_state()),
        )
        assert semantic_ctx.indexer.state.value == "idle"

    def test_frontmatter_path_key_is_ignored(
        self, base_dir: Path, state: AppState
    ) -> None:
        (base_dir / "a.md").write_text("---\npath: fake.md\n---\n")
        result = tools.query(
            glob="a.md", sql="SELECT path FROM files", **tool_deps(state)
        )
        assert result["results"] == [{"path": "a.md"}]
        assert result["warnings"][0]["path"] == "a.md"
