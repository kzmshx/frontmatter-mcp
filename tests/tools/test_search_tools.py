"""Tests for the search tools."""

import os
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from frontmatter_mcp import server as tools
from frontmatter_mcp.dependencies import (
    AppState,
    get_semantic_ctx,
    get_state,
)
from frontmatter_mcp.semantic import SemanticContext
from tests.conftest import tool_deps


class TestSemanticDisabled:
    """Semantic tools fail with a clear message when semantic search is off."""

    def test_search_raises_tool_error(self, base_dir: Path, state: AppState) -> None:

        with pytest.raises(ToolError, match="FRONTMATTER_ENABLE_SEMANTIC"):
            tools.search(query="x", **tool_deps(get_state()))


class TestSemanticSearchTools:
    """Tests for semantic search tools."""

    def test_index_status_enabled(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """index_status returns state when enabled."""
        result = tools.index_status(semantic_ctx=get_semantic_ctx())
        assert "state" in result
        assert result["state"] in ["idle", "indexing", "ready"]

    def test_index_wait_success(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """index_wait returns success=true when indexing completes."""
        tools.index_refresh(semantic_ctx=get_semantic_ctx())
        result = tools.index_wait(timeout=5.0, semantic_ctx=get_semantic_ctx())

        assert result["success"] is True
        assert result["state"] == "ready"

    def test_index_wait_idle(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """index_wait returns success=true immediately when idle."""
        result = tools.index_wait(timeout=0.1, semantic_ctx=get_semantic_ctx())

        # When idle (never started), wait returns immediately with success=true
        assert result["success"] is True
        assert result["state"] == "idle"

    def test_index_refresh_enabled(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """index_refresh starts indexing when enabled."""
        result = tools.index_refresh(semantic_ctx=get_semantic_ctx())
        assert "message" in result
        assert result["message"] in ["Indexing started", "Indexing already in progress"]

        semantic_ctx.indexer.wait(timeout=5.0)

    def test_query_with_semantic_search(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """query can use embed() function after indexing."""
        tools.index_refresh(semantic_ctx=get_semantic_ctx())
        semantic_ctx.indexer.wait(timeout=5.0)

        result = tools.query(
            glob="**/*.md",
            sql="""SELECT path,
               array_cosine_similarity(embedding, embed('test')) as score
               FROM files
               ORDER BY score DESC
               LIMIT 2""",
            **tool_deps(get_state()),
        )

        assert result["row_count"] == 2
        assert "score" in result["columns"]

    def test_search_returns_best_passage(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """search finds documents by wording and returns the passage and line."""
        (base_dir / "darts.md").write_text(
            "---\ndate: 2025-11-20\n---\n# Evening\n\n"
            "ダーツが全然入らなくて苛立った夜だった。隣は上手かった。\n"
        )
        (base_dir / "tea.md").write_text(
            "---\ndate: 2025-11-28\n---\n# Morning\n\n"
            "煎り番茶を淹れて冷やしてみたら美味しかった。また作ろう。\n"
        )
        tools.index_refresh(semantic_ctx=get_semantic_ctx())
        semantic_ctx.indexer.wait(timeout=5.0)

        result = tools.search(query="ダーツ 苛立", **tool_deps(get_state()))
        top = result["results"][0]
        assert top["path"] == "darts.md"
        assert top["line"] == 6
        assert top["heading"] == "Evening"
        assert "ダーツ" in top["text"]
        assert result["index"]["state"] == "ready"

        filtered = tools.search(
            query="ダーツ 苛立", where="date > '2025-11-25'", **tool_deps(get_state())
        )
        assert [r["path"] for r in filtered["results"]] == ["tea.md"]

    def test_search_starts_indexing_on_first_use(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """The server does not index at startup; the first search does."""
        (base_dir / "note.md").write_text(
            "---\ndate: 2025-11-20\n---\n煎り番茶を淹れて冷やしてみたら美味しかった。\n"
        )
        assert semantic_ctx.indexer.state.value == "idle"
        result = tools.search(query="煎り番茶", **tool_deps(get_state()))
        assert result["index"]["state"] == "ready"
        assert result["results"][0]["path"] == "note.md"

    def test_server_import_does_not_load_torch(self, base_dir: Path) -> None:
        """Sessions that never search should not pay for torch."""
        import subprocess
        import sys

        code = (
            "import sys, frontmatter_mcp.server; "
            "print('torch' in sys.modules or 'sklearn' in sys.modules)"
        )
        out = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=dict(os.environ) | {"FRONTMATTER_BASE_DIR": str(base_dir)},
        )
        assert out.stdout.strip() == "False"

    def test_query_inspect_includes_embedding(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        """query_inspect includes embedding in schema when semantic search ready."""
        tools.index_refresh(semantic_ctx=get_semantic_ctx())
        semantic_ctx.indexer.wait(timeout=5.0)

        result = tools.query_inspect(glob="**/*.md", **tool_deps(get_state()))

        assert "embedding" in result["schema"]
        assert result["schema"]["embedding"]["type"] == "FLOAT[64]"
        assert result["schema"]["embedding"]["nullable"] is True


class TestSearchParameters:
    def test_glob_limit_and_where(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        for i in range(3):
            body = f"ダーツの練習をした日の記録。ブルがよく入った夜だった {i}"
            (base_dir / f"n{i}.md").write_text(
                f"---\ndate: 2025-12-0{i + 1}\n---\n{body}\n"
            )
        deps = tool_deps(get_state())
        by_glob = tools.search(query="ダーツ", glob="n0.md", **deps)
        assert [r["path"] for r in by_glob["results"]] == ["n0.md"]
        limited = tools.search(query="ダーツ", limit=2, **deps)
        assert len(limited["results"]) == 2
        clamped = tools.search(query="ダーツ", limit=0, **deps)
        assert len(clamped["results"]) == 1
        newest = tools.search(query="ダーツ", where="date >= '2025-12-03'", **deps)
        assert [r["path"] for r in newest["results"]] == ["n2.md"]

    def test_invalid_where_is_a_tool_error(
        self, base_dir: Path, semantic_ctx: SemanticContext
    ) -> None:
        with pytest.raises(ToolError, match="Columns of the files table"):
            tools.search(query="x", where="nope = 1", **tool_deps(get_state()))
