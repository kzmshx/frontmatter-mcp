"""Embedding indexer module for background embedding generation."""

import threading
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import frontmatter

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.model import EmbeddingModel


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

        # Index stale files
        for rel_path in stale_paths:
            abs_path = self._base_dir / rel_path
            try:
                content = self._get_content(abs_path)
                if content:
                    vector = self._model.encode(content)
                    mtime = current_files[rel_path]
                    self._cache.set(rel_path, mtime, vector)
            except Exception:
                # Skip files that can't be processed
                continue

    def _get_content(self, file_path: Path) -> str | None:
        """Get content from a file for embedding.

        Args:
            file_path: Path to the file.

        Returns:
            File content (body text after frontmatter), or None if empty.
        """
        try:
            post = frontmatter.load(file_path)
            content = post.content.strip()
            return content if content else None
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
