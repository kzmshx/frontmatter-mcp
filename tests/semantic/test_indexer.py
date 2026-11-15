"""Tests for the background chunk indexer."""

import os
import time
from pathlib import Path
from typing import Generator

import numpy as np
import pytest

from frontmatter_mcp.semantic import ChunkIndexer, ChunkStore, IndexerState
from tests.conftest import FakeEmbeddingModel

LONG = "This paragraph is long enough to become a chunk."


class SlowModel(FakeEmbeddingModel):
    def encode_documents(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        time.sleep(0.5)
        return super().encode_documents(texts, batch_size)


def _chunk_count(store: ChunkStore) -> int:
    rows = store.load_chunks()
    return len(rows) if rows is not None else 0


class TestChunkIndexer:
    """Tests for ChunkIndexer class."""

    @pytest.fixture
    def base_dir(self, tmp_path: Path) -> Path:
        base = tmp_path / "vault"
        base.mkdir()
        return base

    @pytest.fixture
    def mock_model(self) -> FakeEmbeddingModel:
        return FakeEmbeddingModel()

    @pytest.fixture
    def cache(
        self, tmp_path: Path, mock_model: FakeEmbeddingModel
    ) -> Generator[ChunkStore, None, None]:
        cache = ChunkStore(tmp_path / ".frontmatter-mcp", model=mock_model)
        yield cache
        cache.close()

    def _create_md_file(self, base_dir: Path, name: str, content: str) -> Path:
        file_path = base_dir / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"---\ntitle: {name}\n---\n{content}")
        return file_path

    def _run(self, indexer: ChunkIndexer) -> None:
        indexer.start()
        assert indexer.wait(timeout=5.0)

    def test_initial_state(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        indexer = ChunkIndexer(cache, mock_model, lambda: [], base_dir)
        assert indexer.state == IndexerState.IDLE
        assert indexer.generation == 0

    def test_start_indexing(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "a.md", f"# A\n\n{LONG}")
        self._create_md_file(base_dir, "b.md", f"{LONG}\n\n# B2\n\n{LONG}")
        files = list(base_dir.glob("*.md"))
        indexer = ChunkIndexer(cache, mock_model, lambda: files, base_dir)

        result = indexer.start()
        assert result["state"] == "indexing"
        assert result["target_count"] == 2
        assert indexer.wait(timeout=5.0)

        assert indexer.state == IndexerState.READY
        assert indexer.generation == 1
        assert len(cache.indexed_mtimes()) == 2
        assert _chunk_count(cache) == 3

    def test_chunks_record_heading_and_line(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "a.md", f"# Title\n\n{LONG}\n")
        indexer = ChunkIndexer(
            cache, mock_model, lambda: list(base_dir.glob("*.md")), base_dir
        )
        self._run(indexer)
        rows = cache.load_chunks()
        assert rows is not None
        assert rows.headings == ["Title"]
        assert rows.lines.tolist() == [6]  # 3 frontmatter lines + heading + blank
        assert mock_model.encoded_documents

    def test_duplicate_start(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "a.md", LONG)

        mock_model = SlowModel()
        files = list(base_dir.glob("*.md"))
        indexer = ChunkIndexer(cache, mock_model, lambda: files, base_dir)

        assert indexer.start()["message"] == "Indexing started"
        assert indexer.start()["message"] == "Indexing already in progress"
        indexer.wait(timeout=5.0)

    def test_differential_update(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        file_a = self._create_md_file(base_dir, "a.md", LONG)
        file_b = self._create_md_file(base_dir, "b.md", LONG)
        indexer = ChunkIndexer(cache, mock_model, lambda: [file_a, file_b], base_dir)
        self._run(indexer)
        assert len(mock_model.encoded_documents) == 2

        mock_model.encoded_documents.clear()
        file_a.write_text(f"---\ntitle: a\n---\nUpdated. {LONG}")
        st = file_a.stat()
        os.utime(file_a, (st.st_atime, st.st_mtime + 10))
        self._run(indexer)

        assert mock_model.encoded_documents == [f"Updated. {LONG}"]

    def test_deleted_file_removed_from_cache(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        file_a = self._create_md_file(base_dir, "a.md", LONG)
        file_b = self._create_md_file(base_dir, "b.md", LONG)
        both = [file_a, file_b]
        self._run(ChunkIndexer(cache, mock_model, lambda: both, base_dir))
        assert len(cache.indexed_mtimes()) == 2

        file_b.unlink()
        self._run(ChunkIndexer(cache, mock_model, lambda: [file_a], base_dir))
        assert cache.indexed_mtimes().keys() == {"a.md"}

    def test_newly_excluded_file_removed_from_cache(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        from frontmatter_mcp.paths import list_markdown_files

        self._create_md_file(base_dir, "a.md", LONG)
        self._create_md_file(base_dir, "IDENTITY.md", LONG)
        exclude: list[str] = []
        indexer = ChunkIndexer(
            cache, mock_model, lambda: list_markdown_files(base_dir, exclude), base_dir
        )
        self._run(indexer)
        assert cache.indexed_mtimes().keys() == {"a.md", "IDENTITY.md"}

        exclude.append("IDENTITY.md")
        self._run(indexer)
        assert cache.indexed_mtimes().keys() == {"a.md"}
        assert indexer.last_run.removed == 1

    def test_file_without_chunks_is_recorded_once(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        """Short files are recorded so they are not re-read on every run."""
        self._create_md_file(base_dir, "short.md", "tiny")
        files = list(base_dir.glob("*.md"))
        indexer = ChunkIndexer(cache, mock_model, lambda: files, base_dir)
        self._run(indexer)
        assert len(cache.indexed_mtimes()) == 1
        assert _chunk_count(cache) == 0
        assert cache.stale_paths({"short.md": files[0].stat().st_mtime}) == []

    def test_wait_returns_true_when_not_started(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        indexer = ChunkIndexer(cache, mock_model, lambda: [], base_dir)
        assert indexer.wait(timeout=1.0) is True

    def test_subdirectory_files(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "root.md", LONG)
        self._create_md_file(base_dir, "sub/nested.md", LONG)
        files = list(base_dir.rglob("*.md"))
        self._run(ChunkIndexer(cache, mock_model, lambda: files, base_dir))
        assert cache.indexed_mtimes().keys() == {"root.md", "sub/nested.md"}

    def test_cache_connection_closed_after_indexing(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        """Closing the connection avoids DuckDB lock conflicts with readers."""
        self._create_md_file(base_dir, "a.md", LONG)
        files = list(base_dir.glob("*.md"))
        self._run(ChunkIndexer(cache, mock_model, lambda: files, base_dir))
        assert cache._conn is None

    def test_failed_run_reports_error_and_keeps_index(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        f = self._create_md_file(base_dir, "a.md", LONG)
        indexer = ChunkIndexer(cache, mock_model, lambda: [f], base_dir)
        self._run(indexer)
        assert indexer.last_run.indexed == 1

        mock_model.fail_with = RuntimeError("model download failed")
        f.write_text(f"---\ntitle: a\n---\nChanged. {LONG}")
        os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 10))
        self._run(indexer)

        assert indexer.state == IndexerState.READY
        assert "model download failed" in (indexer.last_run.error or "")
        rows = cache.load_chunks()
        assert rows is not None and rows.texts == [LONG]  # previous chunks kept

    def test_unreadable_file_counted_as_failed(
        self, cache: ChunkStore, mock_model: FakeEmbeddingModel, base_dir: Path
    ) -> None:
        bad = base_dir / "bad.md"
        bad.write_bytes(b"\xff\xfe invalid utf-8 " * 5)
        good = self._create_md_file(base_dir, "good.md", LONG)
        indexer = ChunkIndexer(cache, mock_model, lambda: [bad, good], base_dir)
        self._run(indexer)
        assert indexer.last_run.failed == 1
        assert indexer.last_run.indexed == 1
