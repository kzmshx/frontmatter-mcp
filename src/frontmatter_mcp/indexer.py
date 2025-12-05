"""Indexer module for background embedding generation."""

import threading
from pathlib import Path
from typing import Callable

import frontmatter

from frontmatter_mcp.cache import EmbeddingCache
from frontmatter_mcp.embedding import EmbeddingModel


class Indexer:
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
        self._indexing = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def is_indexing(self) -> bool:
        """Check if indexing is in progress."""
        with self._lock:
            return self._indexing

    @property
    def indexed_count(self) -> int:
        """Get the number of indexed documents."""
        return self._cache.count()

    def start(self) -> dict:
        """Start background indexing.

        Returns:
            Status dict with message and target_count.
        """
        with self._lock:
            if self._indexing:
                return {
                    "message": "Indexing already in progress",
                    "indexing": True,
                }

            files = self._get_files()
            target_count = len(files)

            self._indexing = True
            self._thread = threading.Thread(
                target=self._run_indexing,
                args=(files,),
                daemon=True,
            )
            self._thread.start()

            return {
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
            with self._lock:
                self._indexing = False

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
