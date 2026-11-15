"""Tests for the chunk store."""

from pathlib import Path
from typing import Any, Generator

import duckdb
import numpy as np
import pytest

from frontmatter_mcp.semantic.chunking import Chunk
from frontmatter_mcp.semantic.store import STORE_DB_NAME, ChunkStore
from tests.conftest import FakeEmbeddingModel

DIM = 8


def create_mock_model(
    name: str = "test-model", dimension: int = DIM, document_prefix: str = ""
) -> Any:
    """A model with the attributes the store reads."""
    model = FakeEmbeddingModel(dimension)
    model.name = name
    model.document_prefix = document_prefix
    return model


def file_count(store: ChunkStore) -> int:
    return len(store.indexed_mtimes())


def chunk_count(store: ChunkStore) -> int:
    rows = store.load_chunks()
    return len(rows) if rows is not None else 0


def chunks(*texts: str) -> list[Chunk]:
    return [Chunk(line=i + 1, heading="H", text=t) for i, t in enumerate(texts)]


def vectors(n: int) -> np.ndarray:
    v = np.random.rand(n, DIM).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class TestChunkStore:
    """Tests for ChunkStore class."""

    @pytest.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".frontmatter-mcp"

    @pytest.fixture
    def cache(self, cache_dir: Path) -> Generator[ChunkStore, None, None]:
        cache = ChunkStore(cache_dir, model=create_mock_model())
        yield cache
        cache.close()

    def test_cache_path(self, cache: ChunkStore, cache_dir: Path) -> None:
        assert cache.path == cache_dir / STORE_DB_NAME

    def test_creates_cache_dir(self, cache: ChunkStore, cache_dir: Path) -> None:
        _ = cache.conn
        assert cache_dir.exists()

    def test_set_file_and_load(self, cache: ChunkStore) -> None:
        v = vectors(2)
        cache.replace_files([("a.md", 1000.0, chunks("one", "two"), v)])
        cache.close()

        rows = cache.load_chunks()
        assert rows is not None
        assert rows.paths == ["a.md", "a.md"]
        assert rows.texts == ["one", "two"]
        assert rows.lines.tolist() == [1, 2]
        np.testing.assert_allclose(rows.vectors, v, rtol=1e-6)

    def test_sections_round_trip(self, cache: ChunkStore) -> None:
        from frontmatter_mcp.semantic.chunking import Chunk

        parts = [
            Chunk(line=3, heading="Sleep", text="t1", section=("Day", "Sleep")),
            Chunk(line=9, heading="", text="t2"),
        ]
        cache.replace_files([("a.md", 1000.0, parts, vectors(2))])
        rows = cache.load_chunks()
        assert rows is not None
        assert rows.sections == [["Day", "Sleep"], []]

    def test_set_file_replaces_chunks(self, cache: ChunkStore) -> None:
        cache.replace_files([("a.md", 1000.0, chunks("old1", "old2"), vectors(2))])
        cache.replace_files([("a.md", 2000.0, chunks("new"), vectors(1))])
        assert chunk_count(cache) == 1
        assert cache.indexed_mtimes() == {"a.md": 2000.0}

    def test_file_without_chunks_is_recorded(self, cache: ChunkStore) -> None:
        cache.replace_files([("empty.md", 1000.0, [], vectors(0))])
        assert file_count(cache) == 1
        assert chunk_count(cache) == 0
        assert cache.stale_paths({"empty.md": 1000.0}) == []

    def test_delete(self, cache: ChunkStore) -> None:
        cache.replace_files([("a.md", 1000.0, chunks("x"), vectors(1))])
        cache.delete_file("a.md")
        assert file_count(cache) == 0
        assert chunk_count(cache) == 0

    def test_stale_and_deleted_paths(self, cache: ChunkStore) -> None:
        cache.replace_files([("same.md", 1000.0, chunks("x"), vectors(1))])
        cache.replace_files([("changed.md", 1000.0, chunks("x"), vectors(1))])
        cache.replace_files([("gone.md", 1000.0, chunks("x"), vectors(1))])
        current = {"same.md": 1000.0, "changed.md": 2000.0, "new.md": 1.0}
        assert sorted(cache.stale_paths(current)) == ["changed.md", "new.md"]
        assert cache.deleted_paths(current) == ["gone.md"]

    def test_load_while_write_connection_is_open(self, cache: ChunkStore) -> None:
        """The indexing process can read its own cache mid-run."""
        cache.replace_files([("a.md", 1000.0, chunks("one"), vectors(1))])
        assert cache._conn is not None  # still open, as during indexing
        rows = cache.load_chunks()
        assert rows is not None and rows.texts == ["one"]

    def test_older_mtime_is_stale(self, cache: ChunkStore) -> None:
        """A file restored with an older mtime is re-indexed."""
        cache.replace_files([("a.md", 2000.0, chunks("x"), vectors(1))])
        assert cache.stale_paths({"a.md": 1000.0}) == ["a.md"]

    def test_readonly_when_db_missing(self, tmp_path: Path) -> None:
        cache = ChunkStore(tmp_path / "none", model=create_mock_model())
        assert cache.load_chunks() is None

    def test_readonly_ignores_a_store_for_another_model(self, cache_dir: Path) -> None:
        """Before the next run rebuilds it, a mismatched file serves nothing."""
        first = ChunkStore(cache_dir, model=create_mock_model(name="a"))
        first.replace_files([("a.md", 1000.0, chunks("x"), vectors(1))])
        first.close()

        assert ChunkStore(cache_dir, model=create_mock_model(name="a")).load_chunks()
        other = ChunkStore(cache_dir, model=create_mock_model(name="b", dimension=16))
        assert other.load_chunks() is None
        assert other.path.exists()  # reading doesn't delete it

    def test_rebuilt_when_model_changes(self, cache_dir: Path) -> None:
        first = ChunkStore(cache_dir, model=create_mock_model(name="a"))
        first.replace_files([("a.md", 1000.0, chunks("x"), vectors(1))])
        first.close()

        second = ChunkStore(cache_dir, model=create_mock_model(name="b"))
        assert file_count(second) == 0
        second.close()

    def test_rebuilt_when_prefix_changes(self, cache_dir: Path) -> None:
        first = ChunkStore(cache_dir, model=create_mock_model(document_prefix=""))
        first.replace_files([("a.md", 1000.0, chunks("x"), vectors(1))])
        first.close()

        model = create_mock_model(document_prefix="doc: ")
        second = ChunkStore(cache_dir, model=model)
        assert file_count(second) == 0
        second.close()

    def test_removes_stores_of_other_versions(self, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True)
        legacy = [cache_dir / "embeddings.duckdb", cache_dir / "chunks-v3.duckdb"]
        for path in legacy:
            with duckdb.connect(str(path)) as conn:
                conn.execute("CREATE TABLE metadata (key TEXT, value TEXT)")
        (cache_dir / "embeddings.duckdb.wal").write_bytes(b"")

        cache = ChunkStore(cache_dir, model=create_mock_model())
        tables = {r[0] for r in cache.conn.execute("SHOW TABLES").fetchall()}
        assert {"indexed_files", "chunks", "metadata"} <= tables
        cache.close()
        assert sorted(p.name for p in cache_dir.iterdir()) == [STORE_DB_NAME]

    def test_keeps_a_store_another_process_has_open(self, cache_dir: Path) -> None:
        """An older server still using its store is not disturbed."""
        import subprocess
        import sys

        cache_dir.mkdir(parents=True)
        legacy = cache_dir / "embeddings.duckdb"
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import duckdb, sys; c = duckdb.connect(sys.argv[1]); "
                "print('ready', flush=True); sys.stdin.read()",
                str(legacy),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert holder.stdout is not None
            assert holder.stdout.readline().strip() == "ready"
            cache = ChunkStore(cache_dir, model=create_mock_model())
            assert cache.indexed_mtimes() == {}
            cache.close()
            assert legacy.exists()
        finally:
            holder.communicate("")


class TestCacheDiskSpace:
    """The cache file does not keep growing with dead data."""

    def test_compact_after_many_replacements(self, tmp_path: Path) -> None:
        cache = ChunkStore(tmp_path / "c", model=create_mock_model(dimension=256))
        many = [Chunk(line=i, heading="", text="x" * 300) for i in range(50)]
        big = np.random.rand(50, 256).astype(np.float32)
        for round_ in range(2):
            for f in range(40):
                cache.replace_files([(f"{f}.md", float(round_), many, big)])
            cache.conn.execute("CHECKPOINT")
        before = cache.path.stat().st_size

        assert cache.compact_if_needed(min_growth_bytes=0)
        after = cache.path.stat().st_size
        assert after < before
        assert file_count(cache) == 40
        assert chunk_count(cache) == 40 * 50
        cache.close()

    def test_no_compaction_until_file_grows(self, tmp_path: Path) -> None:
        cache = ChunkStore(tmp_path / "c", model=create_mock_model())
        cache.replace_files([("a.md", 1.0, chunks("x"), vectors(1))])
        assert cache.compact_if_needed()  # first run records the compact size
        assert not cache.compact_if_needed()
        cache.close()

    def test_compact_size_does_not_trigger_rebuild(self, tmp_path: Path) -> None:
        cache = ChunkStore(tmp_path / "c", model=create_mock_model())
        cache.replace_files([("a.md", 1.0, chunks("x"), vectors(1))])
        cache.compact_if_needed()
        cache.close()
        reopened = ChunkStore(tmp_path / "c", model=create_mock_model())
        assert file_count(reopened) == 1
        reopened.close()

    def test_mismatch_starts_a_new_file(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "c"
        model_a = create_mock_model(name="a", dimension=256)
        first = ChunkStore(cache_dir, model=model_a)
        many = [Chunk(line=i, heading="", text="x" * 300) for i in range(50)]
        big = np.random.rand(50, 256).astype(np.float32)
        for f in range(40):
            first.replace_files([(f"{f}.md", 1.0, many, big)])
        first.conn.execute("CHECKPOINT")
        first.close()
        big = (cache_dir / STORE_DB_NAME).stat().st_size

        model_b = create_mock_model(name="b", dimension=256)
        second = ChunkStore(cache_dir, model=model_b)
        one = np.random.rand(1, 256).astype(np.float32)
        second.replace_files([("a.md", 1.0, chunks("x"), one)])
        second.conn.execute("CHECKPOINT")
        assert (cache_dir / STORE_DB_NAME).stat().st_size < big
        second.close()
