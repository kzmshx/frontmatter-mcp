"""Tests for semantic cache module."""

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import duckdb
import numpy as np
import pytest

from frontmatter_mcp.semantic.cache import CACHE_DB_NAME, EmbeddingCache
from frontmatter_mcp.semantic.chunking import Chunk

DIM = 8


def create_mock_model(
    name: str = "test-model", dimension: int = DIM, document_prefix: str = ""
) -> MagicMock:
    """Create a mock EmbeddingModel."""
    mock = MagicMock()
    mock.name = name
    mock.document_prefix = document_prefix
    mock.get_dimension.return_value = dimension
    return mock


def chunks(*texts: str) -> list[Chunk]:
    return [Chunk(line=i + 1, heading="H", text=t) for i, t in enumerate(texts)]


def vectors(n: int) -> np.ndarray:
    v = np.random.rand(n, DIM).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class TestEmbeddingCache:
    """Tests for EmbeddingCache class."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".frontmatter-mcp"

    @pytest.fixture
    def cache(self, cache_dir: Path) -> Generator[EmbeddingCache, None, None]:
        cache = EmbeddingCache(cache_dir, model=create_mock_model())
        yield cache
        cache.close()

    def test_cache_path(self, cache: EmbeddingCache, cache_dir: Path) -> None:
        assert cache.cache_path == cache_dir / CACHE_DB_NAME

    def test_creates_cache_dir(self, cache: EmbeddingCache, cache_dir: Path) -> None:
        _ = cache.conn
        assert cache_dir.exists()

    def test_set_file_and_load(self, cache: EmbeddingCache) -> None:
        v = vectors(2)
        cache.set_file("a.md", 1000.0, chunks("one", "two"), v)
        cache.close()

        rows = cache.load_chunks_readonly()
        assert rows is not None
        assert rows.paths == ["a.md", "a.md"]
        assert rows.texts == ["one", "two"]
        assert rows.lines.tolist() == [1, 2]
        np.testing.assert_allclose(rows.vectors, v, rtol=1e-6)

    def test_set_file_replaces_chunks(self, cache: EmbeddingCache) -> None:
        cache.set_file("a.md", 1000.0, chunks("old1", "old2"), vectors(2))
        cache.set_file("a.md", 2000.0, chunks("new"), vectors(1))
        assert cache.chunk_count() == 1
        assert cache.get_all_paths_with_mtime() == {"a.md": 2000.0}

    def test_file_without_chunks_is_recorded(self, cache: EmbeddingCache) -> None:
        cache.set_file("empty.md", 1000.0, [], vectors(0))
        assert cache.count() == 1
        assert cache.chunk_count() == 0
        assert cache.get_stale_paths({"empty.md": 1000.0}) == []

    def test_delete(self, cache: EmbeddingCache) -> None:
        cache.set_file("a.md", 1000.0, chunks("x"), vectors(1))
        cache.delete("a.md")
        assert cache.count() == 0
        assert cache.chunk_count() == 0

    def test_clear(self, cache: EmbeddingCache) -> None:
        cache.set_file("a.md", 1000.0, chunks("x"), vectors(1))
        cache.set_file("b.md", 1000.0, chunks("y"), vectors(1))
        cache.clear()
        assert cache.count() == 0

    def test_stale_and_deleted_paths(self, cache: EmbeddingCache) -> None:
        cache.set_file("same.md", 1000.0, chunks("x"), vectors(1))
        cache.set_file("changed.md", 1000.0, chunks("x"), vectors(1))
        cache.set_file("gone.md", 1000.0, chunks("x"), vectors(1))
        current = {"same.md": 1000.0, "changed.md": 2000.0, "new.md": 1.0}
        assert sorted(cache.get_stale_paths(current)) == ["changed.md", "new.md"]
        assert cache.get_deleted_paths(current) == ["gone.md"]

    def test_get_all_readonly_is_normalized_mean(self, cache: EmbeddingCache) -> None:
        v = vectors(2)
        cache.set_file("a.md", 1000.0, chunks("one", "two"), v)
        cache.close()
        result = cache.get_all_readonly()
        mean = v.mean(axis=0)
        np.testing.assert_allclose(result["a.md"], mean / np.linalg.norm(mean), 1e-5)

    def test_readonly_when_db_missing(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(tmp_path / "none", model=create_mock_model())
        assert cache.load_chunks_readonly() is None
        assert cache.get_all_readonly() == {}

    def test_rebuilt_when_model_changes(self, cache_dir: Path) -> None:
        first = EmbeddingCache(cache_dir, model=create_mock_model(name="a"))
        first.set_file("a.md", 1000.0, chunks("x"), vectors(1))
        first.close()

        second = EmbeddingCache(cache_dir, model=create_mock_model(name="b"))
        assert second.count() == 0
        second.close()

    def test_rebuilt_when_prefix_changes(self, cache_dir: Path) -> None:
        first = EmbeddingCache(cache_dir, model=create_mock_model(document_prefix=""))
        first.set_file("a.md", 1000.0, chunks("x"), vectors(1))
        first.close()

        model = create_mock_model(document_prefix="doc: ")
        second = EmbeddingCache(cache_dir, model=model)
        assert second.count() == 0
        second.close()

    def test_drops_schema_v1_table(self, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True)
        with duckdb.connect(str(cache_dir / CACHE_DB_NAME)) as conn:
            conn.execute("CREATE TABLE embeddings (path TEXT, vector FLOAT[8])")
            conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO metadata VALUES ('model_name', 'test-model')")

        cache = EmbeddingCache(cache_dir, model=create_mock_model())
        tables = {r[0] for r in cache.conn.execute("SHOW TABLES").fetchall()}
        assert "embeddings" not in tables
        assert {"files", "chunks", "metadata"} <= tables
        cache.close()


class TestCacheDiskSpace:
    """The cache file does not keep growing with dead data."""

    def test_compact_after_many_replacements(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(tmp_path / "c", model=create_mock_model(dimension=256))
        many = [Chunk(line=i, heading="", text="x" * 300) for i in range(50)]
        big = np.random.rand(50, 256).astype(np.float32)
        for round_ in range(2):
            for f in range(40):
                cache.set_file(f"{f}.md", float(round_), many, big)
            cache.conn.execute("CHECKPOINT")
        before = cache.cache_path.stat().st_size

        assert cache.compact_if_needed(min_growth_bytes=0)
        after = cache.cache_path.stat().st_size
        assert after < before
        assert cache.count() == 40
        assert cache.chunk_count() == 40 * 50
        cache.close()

    def test_no_compaction_until_file_grows(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(tmp_path / "c", model=create_mock_model())
        cache.set_file("a.md", 1.0, chunks("x"), vectors(1))
        assert cache.compact_if_needed()  # first run records the compact size
        assert not cache.compact_if_needed()
        cache.close()

    def test_compact_size_does_not_trigger_rebuild(self, tmp_path: Path) -> None:
        cache = EmbeddingCache(tmp_path / "c", model=create_mock_model())
        cache.set_file("a.md", 1.0, chunks("x"), vectors(1))
        cache.compact_if_needed()
        cache.close()
        reopened = EmbeddingCache(tmp_path / "c", model=create_mock_model())
        assert reopened.count() == 1
        reopened.close()

    def test_mismatch_starts_a_new_file(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "c"
        model_a = create_mock_model(name="a", dimension=256)
        first = EmbeddingCache(cache_dir, model=model_a)
        many = [Chunk(line=i, heading="", text="x" * 300) for i in range(50)]
        big = np.random.rand(50, 256).astype(np.float32)
        for f in range(40):
            first.set_file(f"{f}.md", 1.0, many, big)
        first.conn.execute("CHECKPOINT")
        first.close()
        big = (cache_dir / CACHE_DB_NAME).stat().st_size

        model_b = create_mock_model(name="b", dimension=256)
        second = EmbeddingCache(cache_dir, model=model_b)
        one = np.random.rand(1, 256).astype(np.float32)
        second.set_file("a.md", 1.0, chunks("x"), one)
        second.conn.execute("CHECKPOINT")
        assert (cache_dir / CACHE_DB_NAME).stat().st_size < big
        second.close()
