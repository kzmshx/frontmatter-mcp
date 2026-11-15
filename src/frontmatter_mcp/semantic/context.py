"""Semantic search context management."""

import threading
from dataclasses import dataclass, field
from pathlib import Path

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.indexer import EmbeddingIndexer, IndexerState
from frontmatter_mcp.semantic.model import EmbeddingModel
from frontmatter_mcp.semantic.search import Reranker, SearchIndex
from frontmatter_mcp.settings import Settings


@dataclass
class SemanticContext:
    """Context for semantic search operations."""

    model: EmbeddingModel
    cache: EmbeddingCache
    indexer: EmbeddingIndexer
    reranker: Reranker | None = None
    _index: SearchIndex | None = field(default=None, repr=False)
    _index_key: tuple[int, float] | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def is_ready(self) -> bool:
        """Check if indexing is complete and ready for semantic search."""
        return self.indexer.state == IndexerState.READY

    def search_index(self) -> SearchIndex | None:
        """In-memory search index, reloaded after each indexing run.

        Returns None if the cache can't be read yet.
        """
        path = self.cache.cache_path
        mtime = path.stat().st_mtime if path.exists() else 0.0
        key = (self.indexer.generation, mtime)
        with self._lock:
            if self._index is None or self._index_key != key:
                rows = self.cache.load_chunks_readonly()
                if rows is None:
                    return None
                self._index = SearchIndex(rows)
                self._index_key = key
            return self._index


def get_semantic_context(settings: Settings) -> SemanticContext:
    """Create a semantic context instance.

    The model is lazy-loaded when first needed (e.g., when cache connects
    or when encoding text). This allows the MCP server to start quickly.

    Args:
        settings: Application settings.

    Returns:
        SemanticContext with model, cache, indexer, and reranker.
    """
    model = EmbeddingModel(
        settings.embedding_model,
        query_prefix=settings.frontmatter_embedding_query_prefix,
        document_prefix=settings.frontmatter_embedding_document_prefix,
    )
    cache = EmbeddingCache(cache_dir=settings.cache_dir, model=model)

    def get_files() -> list[Path]:
        # Skip dot directories (.obsidian, .claude, the cache itself), as Obsidian does
        base = settings.base_dir
        return [
            p
            for p in base.rglob("*.md")
            if not any(part.startswith(".") for part in p.relative_to(base).parts)
        ]

    indexer = EmbeddingIndexer(cache, model, get_files, settings.base_dir)
    reranker = Reranker(settings.reranker_model) if settings.reranker_model else None

    return SemanticContext(model=model, cache=cache, indexer=indexer, reranker=reranker)
