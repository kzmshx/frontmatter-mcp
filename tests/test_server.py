"""Tests for MCP server module."""

import datetime
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter
import numpy as np
import pytest

import frontmatter_mcp.server as server_module
from frontmatter_mcp.settings import get_settings


# Helper to call FastMCP tool functions (they're FunctionTool objects, not callables)
def _call(tool_or_fn, *args, **kwargs):
    """Call a tool function, handling both FastMCP FunctionTool and plain functions."""
    fn = getattr(tool_or_fn, "fn", tool_or_fn)
    return fn(*args, **kwargs)


def _setup_server_context() -> None:
    """Set up server module globals for testing."""
    server_module._settings = get_settings()
    server_module._semantic_ctx = None


def _teardown_server_context() -> None:
    """Clear server module globals after testing."""
    server_module._settings = None
    server_module._semantic_ctx = None


@pytest.fixture
def temp_base_dir(monkeypatch: pytest.MonkeyPatch):
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

        # Set base_dir via environment variable and set up server context
        monkeypatch.setenv("FRONTMATTER_BASE_DIR", str(base))
        get_settings.cache_clear()
        _setup_server_context()
        yield base
        _teardown_server_context()
        get_settings.cache_clear()


class TestQueryInspect:
    """Tests for query_inspect tool."""

    def test_basic_schema(self, temp_base_dir: Path) -> None:
        """Get schema from files."""
        result = _call(server_module.query_inspect, "*.md")
        assert result["file_count"] == 2
        assert "date" in result["schema"]
        assert "tags" in result["schema"]

    def test_recursive_glob(self, temp_base_dir: Path) -> None:
        """Get schema with recursive glob."""
        result = _call(server_module.query_inspect, "**/*.md")
        assert result["file_count"] == 3
        assert "summary" in result["schema"]


class TestQuery:
    """Tests for query tool."""

    def test_select_all(self, temp_base_dir: Path) -> None:
        """Select all files."""
        result = _call(
            server_module.query, "**/*.md", "SELECT path FROM files ORDER BY path"
        )
        assert result["row_count"] == 3
        assert "path" in result["columns"]

    def test_where_clause(self, temp_base_dir: Path) -> None:
        """Filter by date."""
        result = _call(
            server_module.query,
            "**/*.md",
            "SELECT path FROM files WHERE date >= '2025-11-26'",
        )
        assert result["row_count"] == 2
        paths = [r["path"] for r in result["results"]]
        assert "a.md" in paths
        assert "b.md" in paths

    def test_tag_contains(self, temp_base_dir: Path) -> None:
        """Filter by tag using from_json."""
        result = _call(
            server_module.query,
            "**/*.md",
            """SELECT path FROM files
               WHERE list_contains(from_json(tags, '["VARCHAR"]'), 'python')""",
        )
        assert result["row_count"] == 2

    def test_tag_aggregation(self, temp_base_dir: Path) -> None:
        """Aggregate tags using from_json."""
        result = _call(
            server_module.query,
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
        result = _call(server_module.update, "a.md", set={"status": "published"})
        assert result["path"] == "a.md"
        assert result["frontmatter"]["status"] == "published"
        assert result["frontmatter"]["date"] == datetime.date(2025, 11, 27)

    def test_unset_property(self, temp_base_dir: Path) -> None:
        """Unset a property from a file."""
        result = _call(server_module.update, "b.md", unset=["tags"])
        assert "tags" not in result["frontmatter"]

    def test_set_and_unset(self, temp_base_dir: Path) -> None:
        """Set and unset properties."""
        result = _call(
            server_module.update,
            "subdir/c.md",
            set={"status": "done"},
            unset=["summary"],
        )
        assert result["path"] == "subdir/c.md"
        assert result["frontmatter"]["status"] == "done"
        assert "summary" not in result["frontmatter"]

    def test_file_not_found(self, temp_base_dir: Path) -> None:
        """Error when file does not exist."""
        with pytest.raises(FileNotFoundError):
            _call(server_module.update, "nonexistent.md", set={"x": 1})

    def test_path_outside_base_dir(self, temp_base_dir: Path) -> None:
        """Error when path is outside base_dir."""
        with pytest.raises(ValueError):
            _call(server_module.update, "../outside.md", set={"x": 1})


class TestBatchUpdate:
    """Tests for batch_update tool."""

    def test_set_property_all_files(self, temp_base_dir: Path) -> None:
        """Set a property on all matching files."""
        result = _call(server_module.batch_update, "*.md", set={"status": "reviewed"})
        assert result["updated_count"] == 2
        assert "a.md" in result["updated_files"]
        assert "b.md" in result["updated_files"]

        post = frontmatter.load(temp_base_dir / "a.md")
        assert post["status"] == "reviewed"

    def test_recursive_glob(self, temp_base_dir: Path) -> None:
        """Update all files including subdirectories."""
        result = _call(server_module.batch_update, "**/*.md", set={"batch": True})
        assert result["updated_count"] == 3
        assert "subdir/c.md" in result["updated_files"]

    def test_unset_property(self, temp_base_dir: Path) -> None:
        """Unset a property from all matching files."""
        result = _call(server_module.batch_update, "**/*.md", unset=["tags"])
        assert result["updated_count"] == 3

        post = frontmatter.load(temp_base_dir / "a.md")
        assert "tags" not in post.keys()

    def test_set_and_unset(self, temp_base_dir: Path) -> None:
        """Set and unset properties in batch."""
        result = _call(
            server_module.batch_update,
            "**/*.md",
            set={"new_prop": "value"},
            unset=["date"],
        )
        assert result["updated_count"] == 3

        post = frontmatter.load(temp_base_dir / "b.md")
        assert post["new_prop"] == "value"
        assert "date" not in post.keys()

    def test_no_matching_files(self, temp_base_dir: Path) -> None:
        """Handle no matching files gracefully."""
        result = _call(server_module.batch_update, "*.txt", set={"x": 1})
        assert result["updated_count"] == 0
        assert result["updated_files"] == []

    def test_no_warnings_key_when_success(self, temp_base_dir: Path) -> None:
        """Warnings key is absent when all updates succeed."""
        result = _call(server_module.batch_update, "*.md", set={"status": "ok"})
        assert result["updated_count"] == 2
        assert "warnings" not in result

    def test_warnings_on_malformed_frontmatter(self, temp_base_dir: Path) -> None:
        """Warnings are populated when file has malformed frontmatter."""
        # Create a file with malformed YAML frontmatter
        (temp_base_dir / "malformed.md").write_text(
            "---\ninvalid: [unclosed\n---\n# Content"
        )

        result = _call(server_module.batch_update, "*.md", set={"status": "ok"})
        # a.md and b.md should succeed, malformed.md should fail
        assert result["updated_count"] == 2
        assert "warnings" in result
        assert len(result["warnings"]) == 1
        assert "malformed.md" in result["warnings"][0]


class TestBatchArrayAdd:
    """Tests for batch_array_add tool."""

    def test_add_value_to_existing_array(self, temp_base_dir: Path) -> None:
        """Add a value to an existing array property."""
        result = _call(server_module.batch_array_add, "*.md", "tags", "new-tag")
        assert result["updated_count"] == 2
        assert "a.md" in result["updated_files"]

        post = frontmatter.load(temp_base_dir / "a.md")
        assert "new-tag" in post["tags"]

    def test_skip_duplicate_value(self, temp_base_dir: Path) -> None:
        """Skip files where value already exists (allow_duplicates=False)."""
        result = _call(server_module.batch_array_add, "*.md", "tags", "python")
        # a.md has [python, mcp], b.md has [duckdb]
        # a.md is skipped (python already exists), b.md is updated
        assert result["updated_count"] == 1
        assert "b.md" in result["updated_files"]

    def test_allow_duplicates(self, temp_base_dir: Path) -> None:
        """Allow duplicate values when allow_duplicates=True."""
        result = _call(
            server_module.batch_array_add,
            "*.md",
            "tags",
            "python",
            allow_duplicates=True,
        )
        assert result["updated_count"] == 2

        post = frontmatter.load(temp_base_dir / "a.md")
        assert post["tags"].count("python") == 2

    def test_create_property_if_not_exists(self, temp_base_dir: Path) -> None:
        """Create array property if it doesn't exist."""
        result = _call(server_module.batch_array_add, "*.md", "categories", "blog")
        assert result["updated_count"] == 2

        post = frontmatter.load(temp_base_dir / "a.md")
        assert post["categories"] == ["blog"]

    def test_skip_non_array_property(self, temp_base_dir: Path) -> None:
        """Skip and warn when property is not an array."""
        result = _call(server_module.batch_array_add, "*.md", "date", "value")
        assert result["updated_count"] == 0
        assert "warnings" in result
        assert len(result["warnings"]) == 2

    def test_value_as_array_not_flattened(self, temp_base_dir: Path) -> None:
        """Array value should be added as single element, not flattened."""
        result = _call(
            server_module.batch_array_add, "*.md", "tags", ["nested", "array"]
        )
        assert result["updated_count"] == 2

        post = frontmatter.load(temp_base_dir / "a.md")
        assert ["nested", "array"] in post["tags"]


class TestBatchArrayRemove:
    """Tests for batch_array_remove tool."""

    def test_remove_value_from_array(self, temp_base_dir: Path) -> None:
        """Remove a value from array property."""
        result = _call(server_module.batch_array_remove, "**/*.md", "tags", "python")
        # a.md and c.md have python tag
        assert result["updated_count"] == 2

        post = frontmatter.load(temp_base_dir / "a.md")
        assert "python" not in post["tags"]

    def test_skip_if_value_not_exists(self, temp_base_dir: Path) -> None:
        """Skip files where value doesn't exist."""
        result = _call(server_module.batch_array_remove, "*.md", "tags", "nonexistent")
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_if_property_not_exists(self, temp_base_dir: Path) -> None:
        """Skip files where property doesn't exist."""
        result = _call(server_module.batch_array_remove, "*.md", "categories", "value")
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, temp_base_dir: Path) -> None:
        """Skip and warn when property is not an array."""
        result = _call(server_module.batch_array_remove, "*.md", "date", "value")
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestBatchArrayReplace:
    """Tests for batch_array_replace tool."""

    def test_replace_value_in_array(self, temp_base_dir: Path) -> None:
        """Replace a value in array property."""
        result = _call(
            server_module.batch_array_replace, "**/*.md", "tags", "python", "py"
        )
        assert result["updated_count"] == 2

        post = frontmatter.load(temp_base_dir / "a.md")
        assert "py" in post["tags"]
        assert "python" not in post["tags"]

    def test_skip_if_old_value_not_exists(self, temp_base_dir: Path) -> None:
        """Skip files where old_value doesn't exist."""
        result = _call(
            server_module.batch_array_replace, "*.md", "tags", "nonexistent", "new"
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_if_property_not_exists(self, temp_base_dir: Path) -> None:
        """Skip files where property doesn't exist."""
        result = _call(
            server_module.batch_array_replace, "*.md", "categories", "old", "new"
        )
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, temp_base_dir: Path) -> None:
        """Skip and warn when property is not an array."""
        result = _call(server_module.batch_array_replace, "*.md", "date", "old", "new")
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestBatchArraySort:
    """Tests for batch_array_sort tool."""

    def test_sort_array_ascending(self, temp_base_dir: Path) -> None:
        """Sort array in ascending order."""
        result = _call(server_module.batch_array_sort, "*.md", "tags")
        # a.md has [python, mcp] -> [mcp, python] (updated)
        # b.md has [duckdb] (single element, already sorted, skipped)
        assert result["updated_count"] == 1
        assert "a.md" in result["updated_files"]

        post = frontmatter.load(temp_base_dir / "a.md")
        assert post["tags"] == ["mcp", "python"]

    def test_sort_array_descending(self, temp_base_dir: Path) -> None:
        """Sort array in descending order."""
        result = _call(server_module.batch_array_sort, "*.md", "tags", reverse=True)
        # a.md has [python, mcp] - already descending order (skipped)
        # b.md has [duckdb] (single element, already sorted, skipped)
        assert result["updated_count"] == 0

    def test_sort_array_descending_updated(self, temp_base_dir: Path) -> None:
        """Sort array in descending order when not already sorted."""
        # First sort ascending
        _call(server_module.batch_array_sort, "*.md", "tags")
        # Now a.md has [mcp, python], reverse should update it
        result = _call(server_module.batch_array_sort, "*.md", "tags", reverse=True)
        assert result["updated_count"] == 1

        post = frontmatter.load(temp_base_dir / "a.md")
        assert post["tags"] == ["python", "mcp"]

    def test_skip_if_already_sorted(self, temp_base_dir: Path) -> None:
        """Skip files where array is already sorted."""
        # First sort
        _call(server_module.batch_array_sort, "*.md", "tags")
        # Second sort should skip
        result = _call(server_module.batch_array_sort, "*.md", "tags")
        assert result["updated_count"] == 0

    def test_skip_empty_array(self, temp_base_dir: Path) -> None:
        """Skip files with empty array."""
        (temp_base_dir / "empty.md").write_text("---\ntags: []\n---\n# Empty")

        result = _call(server_module.batch_array_sort, "empty.md", "tags")
        assert result["updated_count"] == 0

    def test_skip_if_property_not_exists(self, temp_base_dir: Path) -> None:
        """Skip files where property doesn't exist."""
        result = _call(server_module.batch_array_sort, "*.md", "categories")
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, temp_base_dir: Path) -> None:
        """Skip and warn when property is not an array."""
        result = _call(server_module.batch_array_sort, "*.md", "date")
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestBatchArrayUnique:
    """Tests for batch_array_unique tool."""

    def test_remove_duplicates(self, temp_base_dir: Path) -> None:
        """Remove duplicate values from array."""
        (temp_base_dir / "dup.md").write_text("---\ntags: [a, b, a, c, b]\n---\n# Dup")

        result = _call(server_module.batch_array_unique, "dup.md", "tags")
        assert result["updated_count"] == 1
        assert "dup.md" in result["updated_files"]

        post = frontmatter.load(temp_base_dir / "dup.md")
        assert post["tags"] == ["a", "b", "c"]

    def test_preserve_order(self, temp_base_dir: Path) -> None:
        """Preserve first occurrence order when removing duplicates."""
        content = "---\ntags: [z, a, z, m, a]\n---\n# Order"
        (temp_base_dir / "order.md").write_text(content)

        result = _call(server_module.batch_array_unique, "order.md", "tags")
        assert result["updated_count"] == 1

        post = frontmatter.load(temp_base_dir / "order.md")
        assert post["tags"] == ["z", "a", "m"]

    def test_skip_if_no_duplicates(self, temp_base_dir: Path) -> None:
        """Skip files where array has no duplicates."""
        result = _call(server_module.batch_array_unique, "a.md", "tags")
        # a.md has [python, mcp] - no duplicates
        assert result["updated_count"] == 0

    def test_skip_empty_array(self, temp_base_dir: Path) -> None:
        """Skip files with empty array."""
        (temp_base_dir / "empty.md").write_text("---\ntags: []\n---\n# Empty")

        result = _call(server_module.batch_array_unique, "empty.md", "tags")
        assert result["updated_count"] == 0

    def test_skip_single_element(self, temp_base_dir: Path) -> None:
        """Skip files with single element array."""
        result = _call(server_module.batch_array_unique, "b.md", "tags")
        # b.md has [duckdb] - single element
        assert result["updated_count"] == 0

    def test_skip_if_property_not_exists(self, temp_base_dir: Path) -> None:
        """Skip files where property doesn't exist."""
        result = _call(server_module.batch_array_unique, "*.md", "categories")
        assert result["updated_count"] == 0
        assert "warnings" not in result

    def test_skip_non_array_property(self, temp_base_dir: Path) -> None:
        """Skip and warn when property is not an array."""
        result = _call(server_module.batch_array_unique, "*.md", "date")
        assert result["updated_count"] == 0
        assert "warnings" in result


class TestSemanticSearchTools:
    """Tests for semantic search tools."""

    @pytest.fixture
    def semantic_base_dir(self, temp_base_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """Enable semantic search for tests."""
        monkeypatch.setenv("FRONTMATTER_ENABLE_SEMANTIC", "true")
        get_settings.cache_clear()
        _setup_server_context()
        yield temp_base_dir

    @pytest.fixture
    def mock_semantic_context(
        self, semantic_base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Create and set up a mock semantic context."""
        from frontmatter_mcp.semantic import EmbeddingCache, EmbeddingIndexer
        from frontmatter_mcp.semantic.context import SemanticContext

        mock_model = MagicMock()
        mock_model.name = "test-model"
        mock_model.get_dimension.return_value = 256
        mock_model.encode.return_value = np.random.rand(256).astype(np.float32)

        # Create real cache and indexer with mock model
        cache = EmbeddingCache(
            cache_dir=semantic_base_dir / ".cache",
            model=mock_model,
        )

        def get_files() -> list:
            return list(semantic_base_dir.rglob("*.md"))

        indexer = EmbeddingIndexer(cache, mock_model, get_files, semantic_base_dir)

        sem_ctx = SemanticContext(model=mock_model, cache=cache, indexer=indexer)

        # Set the global semantic context
        server_module._semantic_ctx = sem_ctx

        return sem_ctx

    def test_index_status_enabled(
        self, semantic_base_dir: Path, mock_semantic_context
    ) -> None:
        """index_status returns state when enabled."""
        result = _call(server_module.index_status)
        assert "state" in result
        assert result["state"] in ["idle", "indexing", "ready"]

    def test_index_wait_success(
        self, semantic_base_dir: Path, mock_semantic_context
    ) -> None:
        """index_wait returns success=true when indexing completes."""
        _call(server_module.index_refresh)
        result = _call(server_module.index_wait, 5.0)

        assert result["success"] is True
        assert result["state"] == "ready"

    def test_index_wait_idle(
        self, semantic_base_dir: Path, mock_semantic_context
    ) -> None:
        """index_wait returns success=true immediately when idle."""
        result = _call(server_module.index_wait, 0.1)

        # When idle (never started), wait returns immediately with success=true
        assert result["success"] is True
        assert result["state"] == "idle"

    def test_index_refresh_enabled(
        self, semantic_base_dir: Path, mock_semantic_context
    ) -> None:
        """index_refresh starts indexing when enabled."""
        result = _call(server_module.index_refresh)
        assert "message" in result
        assert result["message"] in ["Indexing started", "Indexing already in progress"]

        mock_semantic_context.indexer.wait(timeout=5.0)

    def test_query_with_semantic_search(
        self, semantic_base_dir: Path, mock_semantic_context
    ) -> None:
        """query can use embed() function after indexing."""
        _call(server_module.index_refresh)
        mock_semantic_context.indexer.wait(timeout=5.0)

        result = _call(
            server_module.query,
            "**/*.md",
            """SELECT path,
               array_cosine_similarity(embedding, embed('test')) as score
               FROM files
               ORDER BY score DESC
               LIMIT 2""",
        )

        assert result["row_count"] == 2
        assert "score" in result["columns"]

    def test_query_inspect_includes_embedding(
        self, semantic_base_dir: Path, mock_semantic_context
    ) -> None:
        """query_inspect includes embedding in schema when semantic search ready."""
        _call(server_module.index_refresh)
        mock_semantic_context.indexer.wait(timeout=5.0)

        result = _call(server_module.query_inspect, "**/*.md")

        assert "embedding" in result["schema"]
        assert result["schema"]["embedding"]["type"] == "FLOAT[256]"
        assert result["schema"]["embedding"]["nullable"] is False
