"""Embedding indexer module for background embedding generation."""

import threading
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.chunking import Chunk, chunk_markdown
from frontmatter_mcp.semantic.model import EmbeddingModel

# Encode this many chunks per model call during indexing
ENCODE_BATCH_CHUNKS = 256


class IndexerState(Enum):
    """State of the embedding indexer."""

    IDLE = "idle"  # Not started yet
    INDEXING = "indexing"  # Indexing in progress
    READY = "ready"  # Indexing completed at least once


class EmbeddingIndexer:
    """Background indexer for document embeddings."""

    def __init__(
        self,
        cache: EmbeddingCache,
        model: EmbeddingModel,
        get_files: Callable[[], list[Path]],
        base_dir: Path,
    ) -> None:
        """Initialize the indexer.

        Args:
            cache: Embedding cache instance.
            model: Embedding model instance.
            get_files: Callable that returns list of files to index.
            base_dir: Base directory for relative path calculation.
        """
        self._cache = cache
        self._model = model
        self._get_files = get_files
        self._base_dir = base_dir
        self._state = IndexerState.IDLE
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._generation = 0

    @property
    def generation(self) -> int:
        """Incremented each time an indexing run finishes."""
        with self._lock:
            return self._generation

    @property
    def state(self) -> IndexerState:
        """Get current indexer state."""
        with self._lock:
            return self._state

    def start(self) -> dict[str, Any]:
        """Start background indexing.

        Returns:
            Status dict with state, message, and target_count.
        """
        with self._lock:
            if self._state == IndexerState.INDEXING:
                return {
                    "state": self._state.value,
                    "message": "Indexing already in progress",
                }

            files = self._get_files()
            target_count = len(files)

            self._state = IndexerState.INDEXING
            self._thread = threading.Thread(
                target=self._run_indexing,
                args=(files,),
                daemon=True,
            )
            self._thread.start()

            return {
                "state": self._state.value,
                "message": "Indexing started",
                "target_count": target_count,
            }

    def _run_indexing(self, files: list[Path]) -> None:
        """Run the indexing process.

        Args:
            files: List of files to index.
        """
        try:
            self._index_files(files)
        finally:
            self._cache.close()
            with self._lock:
                self._state = IndexerState.READY
                self._generation += 1

    def _index_files(self, files: list[Path]) -> None:
        """Index the given files.

        Args:
            files: List of files to index.
        """
        # Build current file map with mtime
        current_files: dict[str, float] = {}
        for file_path in files:
            try:
                rel_path = str(file_path.relative_to(self._base_dir))
                mtime = file_path.stat().st_mtime
                current_files[rel_path] = mtime
            except (ValueError, OSError):
                continue

        # Find stale and deleted paths
        stale_paths = self._cache.get_stale_paths(current_files)
        deleted_paths = self._cache.get_deleted_paths(current_files)

        # Remove deleted entries
        for path in deleted_paths:
            self._cache.delete(path)

        # Encode chunks of several files at once (batching is much faster), then
        # write each file's chunks in its own transaction
        pending: list[tuple[str, list[Chunk]]] = []
        pending_chunks = 0
        for rel_path in stale_paths:
            chunks = self._get_chunks(self._base_dir / rel_path)
            if chunks is None:
                continue
            pending.append((rel_path, chunks))
            pending_chunks += len(chunks)
            if pending_chunks >= ENCODE_BATCH_CHUNKS:
                self._flush(pending, current_files)
                pending, pending_chunks = [], 0
        self._flush(pending, current_files)

    def _flush(
        self, pending: list[tuple[str, list[Chunk]]], current_files: dict[str, float]
    ) -> None:
        texts = [c.text for _, chunks in pending for c in chunks]
        if not pending:
            return
        try:
            vectors = self._model.encode_documents(texts)
        except Exception:
            return
        offset = 0
        for rel_path, chunks in pending:
            self._cache.set_file(
                rel_path,
                current_files[rel_path],
                chunks,
                vectors[offset : offset + len(chunks)],
            )
            offset += len(chunks)

    def _get_chunks(self, file_path: Path) -> list[Chunk] | None:
        """Split a file into chunks, or None if it can't be read."""
        try:
            return chunk_markdown(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for indexing to complete.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if indexing completed, False if timed out.
        """
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            return not self._thread.is_alive()
        return True
