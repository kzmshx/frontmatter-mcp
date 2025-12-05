"""Tests for cache module."""

from pathlib import Path

import numpy as np
import pytest

from frontmatter_mcp.cache import CACHE_DB_NAME, EmbeddingCache


class TestEmbeddingCache:
    """Tests for EmbeddingCache class."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory."""
        return tmp_path / ".frontmatter-mcp"

    @pytest.fixture
    def cache(self, cache_dir: Path) -> EmbeddingCache:
        """Create a cache instance."""
        cache = EmbeddingCache(cache_dir, model_name="test-model", dimension=256)
        yield cache
        cache.close()

    def test_db_path(self, cache: EmbeddingCache, cache_dir: Path) -> None:
        """Database path is correct."""
        assert cache.db_path == cache_dir / CACHE_DB_NAME

    def test_creates_cache_dir(self, cache: EmbeddingCache, cache_dir: Path) -> None:
        """Cache directory is created on connect."""
        _ = cache.conn  # Trigger connection
        assert cache_dir.exists()

    def test_creates_tables(self, cache: EmbeddingCache) -> None:
        """Database tables are created."""
        tables = cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "embeddings" in table_names
        assert "metadata" in table_names

    def test_stores_model_metadata(self, cache: EmbeddingCache) -> None:
        """Model metadata is stored."""
        result = cache.conn.execute(
            "SELECT value FROM metadata WHERE key = 'model_name'"
        ).fetchone()
        assert result[0] == "test-model"

        result = cache.conn.execute(
            "SELECT value FROM metadata WHERE key = 'dimension'"
        ).fetchone()
        assert result[0] == "256"

    def test_set_and_get(self, cache: EmbeddingCache) -> None:
        """Store and retrieve embedding."""
        vector = np.random.rand(256).astype(np.float32)
        cache.set("test.md", 1234567890.0, vector)

        result = cache.get("test.md")
        assert result is not None
        mtime, retrieved_vector = result
        assert mtime == 1234567890.0
        np.testing.assert_array_almost_equal(retrieved_vector, vector, decimal=5)

    def test_get_nonexistent(self, cache: EmbeddingCache) -> None:
        """Get returns None for nonexistent path."""
        result = cache.get("nonexistent.md")
        assert result is None

    def test_set_updates_existing(self, cache: EmbeddingCache) -> None:
        """Set updates existing entry."""
        vector1 = np.random.rand(256).astype(np.float32)
        vector2 = np.random.rand(256).astype(np.float32)

        cache.set("test.md", 1000.0, vector1)
        cache.set("test.md", 2000.0, vector2)

        result = cache.get("test.md")
        assert result is not None
        mtime, retrieved_vector = result
        assert mtime == 2000.0
        np.testing.assert_array_almost_equal(retrieved_vector, vector2, decimal=5)

    def test_delete(self, cache: EmbeddingCache) -> None:
        """Delete removes embedding."""
        vector = np.random.rand(256).astype(np.float32)
        cache.set("test.md", 1234567890.0, vector)
        cache.delete("test.md")

        result = cache.get("test.md")
        assert result is None

    def test_clear(self, cache: EmbeddingCache) -> None:
        """Clear removes all embeddings."""
        vector = np.random.rand(256).astype(np.float32)
        cache.set("a.md", 1000.0, vector)
        cache.set("b.md", 2000.0, vector)

        cache.clear()

        assert cache.get("a.md") is None
        assert cache.get("b.md") is None

    def test_count(self, cache: EmbeddingCache) -> None:
        """Count returns number of embeddings."""
        assert cache.count() == 0

        vector = np.random.rand(256).astype(np.float32)
        cache.set("a.md", 1000.0, vector)
        assert cache.count() == 1

        cache.set("b.md", 2000.0, vector)
        assert cache.count() == 2

    def test_get_all_paths_with_mtime(self, cache: EmbeddingCache) -> None:
        """Get all cached paths with mtime."""
        vector = np.random.rand(256).astype(np.float32)
        cache.set("a.md", 1000.0, vector)
        cache.set("b.md", 2000.0, vector)

        result = cache.get_all_paths_with_mtime()
        assert result == {"a.md": 1000.0, "b.md": 2000.0}

    def test_get_stale_paths_new_file(self, cache: EmbeddingCache) -> None:
        """Detect new files as stale."""
        current_files = {"new.md": 1000.0}
        stale = cache.get_stale_paths(current_files)
        assert stale == ["new.md"]

    def test_get_stale_paths_modified_file(self, cache: EmbeddingCache) -> None:
        """Detect modified files as stale."""
        vector = np.random.rand(256).astype(np.float32)
        cache.set("test.md", 1000.0, vector)

        current_files = {"test.md": 2000.0}  # Newer mtime
        stale = cache.get_stale_paths(current_files)
        assert stale == ["test.md"]

    def test_get_stale_paths_unchanged_file(self, cache: EmbeddingCache) -> None:
        """Unchanged files are not stale."""
        vector = np.random.rand(256).astype(np.float32)
        cache.set("test.md", 1000.0, vector)

        current_files = {"test.md": 1000.0}  # Same mtime
        stale = cache.get_stale_paths(current_files)
        assert stale == []

    def test_get_deleted_paths(self, cache: EmbeddingCache) -> None:
        """Detect cached paths that no longer exist."""
        vector = np.random.rand(256).astype(np.float32)
        cache.set("exists.md", 1000.0, vector)
        cache.set("deleted.md", 1000.0, vector)

        current_files = {"exists.md": 1000.0}
        deleted = cache.get_deleted_paths(current_files)
        assert deleted == ["deleted.md"]

    def test_get_all_embeddings(self, cache: EmbeddingCache) -> None:
        """Get all embeddings."""
        vector_a = np.random.rand(256).astype(np.float32)
        vector_b = np.random.rand(256).astype(np.float32)
        cache.set("a.md", 1000.0, vector_a)
        cache.set("b.md", 2000.0, vector_b)

        result = cache.get_all_embeddings()
        assert len(result) == 2

        result_dict = {path: vec for path, vec in result}
        np.testing.assert_array_almost_equal(result_dict["a.md"], vector_a, decimal=5)
        np.testing.assert_array_almost_equal(result_dict["b.md"], vector_b, decimal=5)


class TestEmbeddingCacheModelChange:
    """Tests for model change detection."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory."""
        return tmp_path / ".frontmatter-mcp"

    def test_model_change_clears_cache(self, cache_dir: Path) -> None:
        """Changing model clears existing cache."""
        # Create cache with first model
        cache1 = EmbeddingCache(cache_dir, model_name="model-v1", dimension=256)
        vector = np.random.rand(256).astype(np.float32)
        cache1.set("test.md", 1000.0, vector)
        assert cache1.count() == 1
        cache1.close()

        # Create cache with different model
        cache2 = EmbeddingCache(cache_dir, model_name="model-v2", dimension=256)
        assert cache2.count() == 0  # Cache should be cleared

        # Metadata should be updated
        result = cache2.conn.execute(
            "SELECT value FROM metadata WHERE key = 'model_name'"
        ).fetchone()
        assert result[0] == "model-v2"
        cache2.close()

    def test_same_model_preserves_cache(self, cache_dir: Path) -> None:
        """Same model preserves existing cache."""
        # Create cache with model
        cache1 = EmbeddingCache(cache_dir, model_name="test-model", dimension=256)
        vector = np.random.rand(256).astype(np.float32)
        cache1.set("test.md", 1000.0, vector)
        cache1.close()

        # Reopen with same model
        cache2 = EmbeddingCache(cache_dir, model_name="test-model", dimension=256)
        assert cache2.count() == 1  # Cache should be preserved
        cache2.close()
