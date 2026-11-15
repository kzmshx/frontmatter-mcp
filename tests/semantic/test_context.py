"""Tests for the SemanticContext facade."""

from pathlib import Path

from frontmatter_mcp.semantic import SemanticContext
from tests.conftest import FakeReranker


def _note(base: Path, name: str, body: str) -> None:
    (base / name).write_text(f"---\ntitle: {name}\n---\n{body}\n")


def test_index_reloads_after_each_run(
    base_dir: Path, semantic_ctx: SemanticContext
) -> None:
    _note(base_dir, "first.md", "最初に書いたメモ。煎り番茶を冷やして飲んだ。")
    semantic_ctx.ensure_index(wait_seconds=10)
    first = semantic_ctx.search_index()
    assert first is not None
    assert "first.md" in first.rows.paths

    _note(base_dir, "second.md", "次に書いたメモ。ダーツでブルがよく入った夜。")
    semantic_ctx.refresh()
    semantic_ctx.wait(10)
    second = semantic_ctx.search_index()
    assert second is not first
    assert second is not None and "second.md" in second.rows.paths


def test_status_before_and_after_a_run(
    base_dir: Path, semantic_ctx: SemanticContext
) -> None:
    assert semantic_ctx.status() == {
        "state": "idle",
        "has_index": False,
        "last_run": None,
    }
    semantic_ctx.ensure_index(wait_seconds=10)
    status = semantic_ctx.status()
    assert status["has_index"] is True
    assert status["last_run"]["error"] is None


def test_search_uses_reranker_when_set(
    base_dir: Path, semantic_ctx: SemanticContext
) -> None:
    _note(base_dir, "darts.md", "ダーツが全然入らなくて苛立った夜だった。")
    _note(base_dir, "tea.md", "煎り番茶を淹れて冷やしてみたら美味しかった。")
    semantic_ctx.reranker = FakeReranker()
    semantic_ctx.ensure_index(wait_seconds=10)
    hits = semantic_ctx.search("ダーツ苛立", 2)
    assert hits[0].path == "darts.md"
