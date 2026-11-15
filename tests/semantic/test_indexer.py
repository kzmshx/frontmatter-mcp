"""Tests for semantic indexer module."""

import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import numpy as np
import pytest

from frontmatter_mcp.semantic import EmbeddingCache, EmbeddingIndexer, IndexerState

DIM = 8
LONG = "This paragraph is long enough to become a chunk."


def _fake_encode(texts: list[str], batch_size: int = 64) -> np.ndarray:
    v = np.random.rand(len(texts), DIM).astype(np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


class TestEmbeddingIndexer:
    """Tests for EmbeddingIndexer class."""

    @pytest.fixture
    def base_dir(self, tmp_path: Path) -> Path:
        base = tmp_path / "vault"
        base.mkdir()
        return base

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        model = MagicMock()
        model.name = "test-model"
        model.document_prefix = ""
        model.get_dimension.return_value = DIM
        model.encode_documents.side_effect = _fake_encode
        return model

    @pytest.fixture
    def cache(
        self, tmp_path: Path, mock_model: MagicMock
    ) -> Generator[EmbeddingCache, None, None]:
        cache = EmbeddingCache(tmp_path / ".frontmatter-mcp", model=mock_model)
        yield cache
        cache.close()

    def _create_md_file(self, base_dir: Path, name: str, content: str) -> Path:
        file_path = base_dir / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"---\ntitle: {name}\n---\n{content}")
        return file_path

    def _run(self, indexer: EmbeddingIndexer) -> None:
        indexer.start()
        assert indexer.wait(timeout=5.0)

    def test_initial_state(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        indexer = EmbeddingIndexer(cache, mock_model, lambda: [], base_dir)
        assert indexer.state == IndexerState.IDLE
        assert indexer.generation == 0

    def test_start_indexing(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "a.md", f"# A\n\n{LONG}")
        self._create_md_file(base_dir, "b.md", f"{LONG}\n\n# B2\n\n{LONG}")
        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        result = indexer.start()
        assert result["state"] == "indexing"
        assert result["target_count"] == 2
        assert indexer.wait(timeout=5.0)

        assert indexer.state == IndexerState.READY
        assert indexer.generation == 1
        assert cache.count() == 2
        assert cache.chunk_count() == 3

    def test_chunks_record_heading_and_line(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "a.md", f"# Title\n\n{LONG}\n")
        indexer = EmbeddingIndexer(
            cache, mock_model, lambda: list(base_dir.glob("*.md")), base_dir
        )
        self._run(indexer)
        rows = cache.load_chunks_readonly()
        assert rows is not None
        assert rows.headings == ["Title"]
        assert rows.lines.tolist() == [6]  # 3 frontmatter lines + heading + blank
        mock_model.encode_documents.assert_called()

    def test_duplicate_start(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "a.md", LONG)

        def slow(texts: list[str], batch_size: int = 64) -> np.ndarray:
            time.sleep(0.5)
            return _fake_encode(texts)

        mock_model.encode_documents.side_effect = slow
        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)

        assert indexer.start()["message"] == "Indexing started"
        assert indexer.start()["message"] == "Indexing already in progress"
        indexer.wait(timeout=5.0)

    def test_differential_update(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        file_a = self._create_md_file(base_dir, "a.md", LONG)
        file_b = self._create_md_file(base_dir, "b.md", LONG)
        indexer = EmbeddingIndexer(
            cache, mock_model, lambda: [file_a, file_b], base_dir
        )
        self._run(indexer)
        first_texts = mock_model.encode_documents.call_args.args[0]
        assert len(first_texts) == 2

        mock_model.encode_documents.reset_mock()
        time.sleep(0.01)
        file_a.write_text(f"---\ntitle: a\n---\nUpdated. {LONG}")
        self._run(indexer)

        texts = mock_model.encode_documents.call_args.args[0]
        assert texts == [f"Updated. {LONG}"]

    def test_deleted_file_removed_from_cache(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        file_a = self._create_md_file(base_dir, "a.md", LONG)
        file_b = self._create_md_file(base_dir, "b.md", LONG)
        both = [file_a, file_b]
        self._run(EmbeddingIndexer(cache, mock_model, lambda: both, base_dir))
        assert cache.count() == 2

        file_b.unlink()
        self._run(EmbeddingIndexer(cache, mock_model, lambda: [file_a], base_dir))
        assert cache.get_all_paths_with_mtime().keys() == {"a.md"}

    def test_file_without_chunks_is_recorded_once(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Short files are recorded so they are not re-read on every run."""
        self._create_md_file(base_dir, "short.md", "tiny")
        files = list(base_dir.glob("*.md"))
        indexer = EmbeddingIndexer(cache, mock_model, lambda: files, base_dir)
        self._run(indexer)
        assert cache.count() == 1
        assert cache.chunk_count() == 0
        assert cache.get_stale_paths({"short.md": files[0].stat().st_mtime}) == []

    def test_wait_returns_true_when_not_started(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        indexer = EmbeddingIndexer(cache, mock_model, lambda: [], base_dir)
        assert indexer.wait(timeout=1.0) is True

    def test_subdirectory_files(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        self._create_md_file(base_dir, "root.md", LONG)
        self._create_md_file(base_dir, "sub/nested.md", LONG)
        files = list(base_dir.rglob("*.md"))
        self._run(EmbeddingIndexer(cache, mock_model, lambda: files, base_dir))
        assert cache.get_all_paths_with_mtime().keys() == {"root.md", "sub/nested.md"}

    def test_cache_connection_closed_after_indexing(
        self, cache: EmbeddingCache, mock_model: MagicMock, base_dir: Path
    ) -> None:
        """Closing the connection avoids DuckDB lock conflicts with readers."""
        self._create_md_file(base_dir, "a.md", LONG)
        files = list(base_dir.glob("*.md"))
        self._run(EmbeddingIndexer(cache, mock_model, lambda: files, base_dir))
        assert cache._conn is None
