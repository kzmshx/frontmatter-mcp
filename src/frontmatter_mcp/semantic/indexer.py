"""Background indexing: chunk changed files, embed the chunks, store them."""

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from frontmatter_mcp.semantic.chunking import Chunk, chunk_markdown
from frontmatter_mcp.semantic.models import EmbeddingModel
from frontmatter_mcp.semantic.store import ChunkStore

logger = logging.getLogger(__name__)

# Encode this many chunks per model call during indexing
ENCODE_BATCH_CHUNKS = 256


class IndexerState(Enum):
    """State of the embedding indexer."""

    IDLE = "idle"  # Not started yet
    INDEXING = "indexing"  # Indexing in progress
    READY = "ready"  # Indexing completed at least once


@dataclass
class IndexRunStats:
    """What the last indexing run did."""

    indexed: int = 0  # files whose chunks were (re)written
    removed: int = 0  # files dropped because they no longer exist or are excluded
    failed: int = 0  # files that could not be read or encoded
    error: str | None = None  # why the run stopped early, if it did

    def to_dict(self) -> dict[str, Any]:
        return {
            "indexed": self.indexed,
            "removed": self.removed,
            "failed": self.failed,
            "error": self.error,
        }


class ChunkIndexer:
    """Keeps the chunk store in step with the Markdown files, in a background thread."""

    def __init__(
        self,
        store: ChunkStore,
        model: EmbeddingModel,
        get_files: Callable[[], list[Path]],
        base_dir: Path,
    ) -> None:
        """Initialize the indexer.

        Args:
            store: Where chunks and vectors are kept.
            model: Embedding model instance.
            get_files: Callable that returns list of files to index.
            base_dir: Base directory for relative path calculation.
        """
        self._store = store
        self._model = model
        self._get_files = get_files
        self._base_dir = base_dir
        self._state = IndexerState.IDLE
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._generation = 0
        self._last_run = IndexRunStats()

    @property
    def generation(self) -> int:
        """Number of finished indexing runs; 0 until the first one finishes."""
        with self._lock:
            return self._generation

    @property
    def state(self) -> IndexerState:
        """Get current indexer state."""
        with self._lock:
            return self._state

    @property
    def last_run(self) -> IndexRunStats:
        """Statistics of the last finished run."""
        with self._lock:
            return self._last_run

    def start(self) -> dict[str, Any]:
        """Start background indexing.

        Returns:
            Status dict with state, message, and target_count (files found).
        """
        with self._lock:
            if self._state == IndexerState.INDEXING:
                return {
                    "state": self._state.value,
                    "message": "Indexing already in progress",
                }
            # Claim the run before scanning, so status calls don't wait on the scan
            self._state = IndexerState.INDEXING
        try:
            files = self._get_files()
        except Exception as e:
            with self._lock:
                self._state = IndexerState.READY
                self._last_run = IndexRunStats(error=f"listing files failed: {e}")
            logger.exception("listing files failed")
            return {"state": "ready", "message": "Indexing failed to start"}
        thread = threading.Thread(target=self._run_indexing, args=(files,), daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()
        return {
            "state": IndexerState.INDEXING.value,
            "message": "Indexing started",
            "target_count": len(files),
        }

    def _run_indexing(self, files: list[Path]) -> None:
        """Run the indexing process.

        Args:
            files: List of files to index.
        """
        stats = IndexRunStats()
        try:
            self._index_files(files, stats)
            self._store.compact_if_needed()
        except Exception as e:
            # The previous index stays usable; report why this run stopped
            stats.error = f"{type(e).__name__}: {e}"
            logger.exception("indexing failed")
        finally:
            try:
                self._store.close()
            finally:
                with self._lock:
                    self._state = IndexerState.READY
                    self._generation += 1
                    self._last_run = stats

    def _index_files(self, files: list[Path], stats: IndexRunStats) -> None:
        """Index the given files."""
        current_files: dict[str, float] = {}
        for file_path in files:
            try:
                rel_path = str(file_path.relative_to(self._base_dir))
                current_files[rel_path] = file_path.stat().st_mtime
            except (ValueError, OSError):
                continue

        stale_paths = self._store.stale_paths(current_files)
        deleted_paths = self._store.deleted_paths(current_files)
        for path in deleted_paths:
            self._store.delete_file(path)
        stats.removed = len(deleted_paths)

        # Encode chunks of several files per model call (batching is much
        # faster) and write each batch in one transaction
        pending: list[tuple[str, float, list[Chunk]]] = []
        pending_chunks = 0
        for rel_path in stale_paths:
            chunks = self._get_chunks(self._base_dir / rel_path)
            if chunks is None:
                stats.failed += 1
                continue
            pending.append((rel_path, current_files[rel_path], chunks))
            pending_chunks += len(chunks)
            if pending_chunks >= ENCODE_BATCH_CHUNKS:
                self._flush(pending, stats)
                pending, pending_chunks = [], 0
        self._flush(pending, stats)

    def _flush(
        self, pending: list[tuple[str, float, list[Chunk]]], stats: IndexRunStats
    ) -> None:
        if not pending:
            return
        texts = [c.text for _, _, chunks in pending for c in chunks]
        vectors = self._model.encode_documents(texts)
        entries = []
        offset = 0
        for rel_path, mtime, chunks in pending:
            end = offset + len(chunks)
            entries.append((rel_path, mtime, chunks, vectors[offset:end]))
            offset += len(chunks)
        self._store.replace_files(entries)
        stats.indexed += len(entries)

    def _get_chunks(self, file_path: Path) -> list[Chunk] | None:
        """Split a file into chunks, or None if it can't be read."""
        try:
            return chunk_markdown(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("skipping %s: %s", file_path, e)
            return None

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for indexing to complete.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if indexing completed, False if timed out.
        """
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
            return not thread.is_alive()
        return True
