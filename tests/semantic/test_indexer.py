"""Tests for semantic indexer module."""

import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import numpy as np
import pytest

from frontmatter_mcp.semantic import EmbeddingCache, EmbeddingIndexer, IndexerState


class TestEmbeddingIndexer:
    """Tests for EmbeddingIndexer class."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory."""
        return tmp_path / ".frontmatter-mcp"

    @pytest.fixture
    def base_dir(self, tmp_path: Path) -> Path:
        """Create a temporary base directory with test files."""
        base = tmp_path / "vault"
        base.mkdir()
        return base

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create a mock embedding model."""
        model = MagicMock()
        model.name = "test-model"
        model.encode.return_value = np.random.rand(256).astype(np.float32)
        model.get_dimension.return_value = 256
        return model

    @pytest.fixture
    def cache(
        self, cache_dir: Path, mock_model: MagicMock
    ) -> Generator[EmbeddingCache, None, None]:
        """Create a cache instance."""
        cache = EmbeddingCache(cache_dir, model=mock_model)
        yield cache
        cache.close()

    def _create_md_file(self, base_dir: Path, name: str, content: str) -> Path:
        """Create a markdown file with frontmatter."""
        file_path = base_dir / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"---\ntitle: {name}\n---\n{content}")
        return file_path

    def test_initial_state(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """EmbeddingIndexer starts in IDLE state."""
        indexer = EmbeddingIndexer(cache, mock_model, lambda: [], base_dir)
        assert indexer.state == IndexerState.IDLE

    def test_start_indexing(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Start begins background indexing and transitions to READY on completion."""
        self._create_md_file(base_dir, "a.md", "Content A")
        self._create_md_file(base_dir, "b.md", "Content B")

        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        # Before start
        assert indexer.state == IndexerState.IDLE

        result = indexer.start()
        assert result["state"] == "indexing"
        assert result["message"] == "Indexing started"
        assert result["target_count"] == 2

        # Wait for completion
        indexer.wait(timeout=5.0)
        assert indexer.state == IndexerState.READY
        assert cache.count() == 2

    def test_duplicate_start(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Starting while already indexing returns appropriate message."""
        self._create_md_file(base_dir, "a.md", "Content A")

        # Make encode slow to keep indexing state
        def slow_encode(text):
            time.sleep(0.5)
            return np.random.rand(256).astype(np.float32)

        mock_model.encode.side_effect = slow_encode

        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        result1 = indexer.start()
        assert result1["state"] == "indexing"
        assert result1["message"] == "Indexing started"

        # Try to start again while indexing
        result2 = indexer.start()
        assert result2["state"] == "indexing"
        assert result2["message"] == "Indexing already in progress"

        indexer.wait(timeout=5.0)

    def test_differential_update(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Only stale files are re-indexed."""
        file_a = self._create_md_file(base_dir, "a.md", "Content A")
        file_b = self._create_md_file(base_dir, "b.md", "Content B")

        files = [file_a, file_b]
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        # First indexing
        indexer.start()
        indexer.wait(timeout=5.0)
        assert mock_model.encode.call_count == 2

        mock_model.encode.reset_mock()

        # Modify one file
        time.sleep(0.01)  # Ensure mtime changes
        file_a.write_text("---\ntitle: a.md\n---\nUpdated Content A")

        # Second indexing
        indexer.start()
        indexer.wait(timeout=5.0)

        # Only modified file should be re-indexed
        assert mock_model.encode.call_count == 1

    def test_deleted_file_removed_from_cache(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Deleted files are removed from cache."""
        file_a = self._create_md_file(base_dir, "a.md", "Content A")
        file_b = self._create_md_file(base_dir, "b.md", "Content B")

        files = [file_a, file_b]
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        # First indexing
        indexer.start()
        indexer.wait(timeout=5.0)
        assert cache.count() == 2

        # Delete one file
        file_b.unlink()

        # Re-index with only file_a
        indexer2 = EmbeddingIndexer(cache, mock_model, lambda: [file_a], base_dir)
        indexer2.start()
        indexer2.wait(timeout=5.0)

        assert cache.count() == 1
        assert cache.get("b.md") is None

    def test_empty_content_skipped(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Files with empty content are skipped."""
        self._create_md_file(base_dir, "empty.md", "")
        self._create_md_file(base_dir, "has_content.md", "Some content")

        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        indexer.start()
        indexer.wait(timeout=5.0)

        # Only file with content should be indexed
        assert cache.count() == 1

    def test_wait_returns_true_on_completion(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Wait returns True when indexing completes."""
        self._create_md_file(base_dir, "a.md", "Content")

        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        indexer.start()
        result = indexer.wait(timeout=5.0)

        assert result is True
        assert indexer.state == IndexerState.READY

    def test_wait_returns_true_when_not_started(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Wait returns True when indexing was never started."""
        indexer = EmbeddingIndexer(cache, mock_model, lambda: [], base_dir)
        result = indexer.wait(timeout=1.0)
        assert result is True

    def test_subdirectory_files(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Files in subdirectories are indexed with relative paths."""
        self._create_md_file(base_dir, "root.md", "Root content")
        self._create_md_file(base_dir, "sub/nested.md", "Nested content")

        files = list(base_dir.rglob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        indexer.start()
        indexer.wait(timeout=5.0)

        assert cache.count() == 2
        assert cache.get("root.md") is not None
        assert cache.get("sub/nested.md") is not None

    def test_cache_connection_closed_after_indexing(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Cache connection is closed after indexing completes.

        This prevents DuckDB file lock conflicts when query tries to access
        the cache after indexing is done.
        """
        self._create_md_file(base_dir, "a.md", "Content A")

        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        indexer.start()
        indexer.wait(timeout=5.0)

        assert indexer.state == IndexerState.READY
        # Connection should be closed after indexing
        assert cache._conn is None
