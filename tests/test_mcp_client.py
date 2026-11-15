"""Smoke tests through an in-memory MCP client.

Dependency update PRs are merged when CI passes, so these check that the
server still works over the MCP protocol with the installed FastMCP.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastmcp import Client

import frontmatter_mcp.dependencies as deps
import frontmatter_mcp.server as server_module
from frontmatter_mcp.settings import get_settings

READ_ONLY = {"query_inspect", "query"}
WRITE = {
    "update",
    "batch_update",
    "batch_array_add",
    "batch_array_remove",
    "batch_array_replace",
    "batch_array_sort",
    "batch_array_unique",
}

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def base_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    (tmp_path / "a.md").write_text("---\ndate: 2025-11-27\ntags: [x]\n---\nBody\n")
    monkeypatch.setenv("FRONTMATTER_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("FRONTMATTER_ENABLE_SEMANTIC", raising=False)
    deps.reset_caches()
    get_settings.cache_clear()
    yield tmp_path
    deps.reset_caches()
    get_settings.cache_clear()


async def test_semantic_tools_hidden_by_default(base_dir: Path) -> None:
    async with Client(server_module.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert names == READ_ONLY | WRITE


async def test_read_only_annotations(base_dir: Path) -> None:
    async with Client(server_module.mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}

    def read_only(name: str) -> bool | None:
        annotations = tools[name].annotations
        if annotations is None:
            return None
        # mcp 2.x renamed readOnlyHint to read_only_hint
        return getattr(annotations, "read_only_hint", None) or getattr(
            annotations, "readOnlyHint", None
        )

    for name in READ_ONLY:
        assert read_only(name) is True
    for name in WRITE:
        assert read_only(name) is not True


async def test_query_over_mcp(base_dir: Path) -> None:
    async with Client(server_module.mcp) as client:
        result = await client.call_tool(
            "query", {"glob": "*.md", "sql": "SELECT path, date FROM files"}
        )
    assert result.data["results"] == [{"path": "a.md", "date": "2025-11-27"}]


async def test_update_over_mcp(base_dir: Path) -> None:
    async with Client(server_module.mcp) as client:
        await client.call_tool("update", {"path": "a.md", "set": {"status": "done"}})
    text = (base_dir / "a.md").read_text()
    assert "status: done" in text
    assert text.endswith("Body\n")
