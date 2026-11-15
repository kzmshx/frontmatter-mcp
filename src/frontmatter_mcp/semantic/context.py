"""The semantic search context: the one object the tools talk to."""

import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from frontmatter_mcp.paths import list_markdown_files
from frontmatter_mcp.semantic.indexer import ChunkIndexer, IndexerState
from frontmatter_mcp.semantic.models import EmbeddingModel, Reranker, Scorer
from frontmatter_mcp.semantic.search import SearchHit, SearchIndex
from frontmatter_mcp.semantic.store import ChunkStore
from frontmatter_mcp.settings import Settings


@dataclass
class SemanticContext:
    """Model, store, indexer and reranker, behind a small facade."""

    model: EmbeddingModel
    store: ChunkStore
    indexer: ChunkIndexer
    reranker: Scorer | None = None
    _index: SearchIndex | None = field(default=None, repr=False)
    _index_key: tuple[int, float] | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def is_ready(self) -> bool:
        """Whether an index is being served, without loading one.

        True once an indexing run has finished in this process, or once a
        search has loaded the chunks already on disk (from an earlier session,
        or written so far by the first run). Stays true while a refresh runs.
        """
        return self.indexer.generation > 0 or self._index is not None

    def ensure_index(self, wait_seconds: float = 0.0) -> None:
        """Start indexing if it has never run, and wait up to wait_seconds."""
        if self.indexer.state == IndexerState.IDLE:
            self.indexer.start()
        if wait_seconds > 0:
            self.indexer.wait(timeout=wait_seconds)

    def refresh(self) -> dict[str, Any]:
        """Start a differential indexing run (or report the one in progress)."""
        return self.indexer.start()

    def wait(self, timeout: float) -> bool:
        """Wait for a run in progress; True when none is running."""
        return self.indexer.wait(timeout=timeout)

    def status(self) -> dict[str, Any]:
        """State, whether an index exists, and the last run's statistics."""
        indexer = self.indexer
        return {
            "state": indexer.state.value,
            "has_index": self.is_ready,
            "last_run": indexer.last_run.to_dict() if indexer.generation else None,
        }

    def search(
        self, query: str, limit: int, allowed_paths: set[str] | None = None
    ) -> list[SearchHit]:
        """Hybrid search (see semantic.search); empty if nothing is indexed."""
        index = self.search_index()
        if index is None:
            return []
        return index.search(
            self.model.encode_query(query),
            query,
            limit,
            allowed_paths=allowed_paths,
            reranker=self.reranker,
        )

    def document_vectors(self) -> dict[str, NDArray[np.float32]]:
        """One vector per indexed document (mean of its chunks)."""
        index = self.search_index()
        return index.document_vectors() if index is not None else {}

    def search_index(self) -> SearchIndex | None:
        """In-memory search index, reloaded after each indexing run.

        Returns None only if no index has been loaded yet and the store can't
        be read.
        """
        path = self.store.path
        mtime = path.stat().st_mtime if path.exists() else 0.0
        key = (self.indexer.generation, mtime)
        with self._lock:
            if self._index is None or self._index_key != key:
                rows = self.store.load_chunks()
                if rows is not None:
                    self._index = SearchIndex(rows)
                    self._index_key = key
                # If the store can't be read right now, keep serving the
                # previous index rather than returning nothing
            return self._index


def create_semantic_context(settings: Settings) -> SemanticContext:
    """Build the semantic context from settings. Models load on first use."""
    model = EmbeddingModel(
        settings.embedding_model,
        query_prefix=settings.embedding_query_prefix,
        document_prefix=settings.embedding_document_prefix,
    )
    store = ChunkStore(cache_dir=settings.cache_dir, model=model)
    base_dir = settings.base_dir
    indexer = ChunkIndexer(
        store, model, lambda: list_markdown_files(base_dir), base_dir
    )
    reranker = Reranker(settings.reranker_model) if settings.reranker_model else None
    return SemanticContext(model=model, store=store, indexer=indexer, reranker=reranker)
