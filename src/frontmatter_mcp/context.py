"""Application context management for frontmatter-mcp."""

from functools import lru_cache
from pathlib import Path

from frontmatter_mcp.semantic import (
    EmbeddingCache,
    EmbeddingIndexer,
    EmbeddingModel,
    IndexerState,
)
from frontmatter_mcp.settings import get_settings


def get_base_dir() -> Path:
    """Get the configured base directory from settings.

    Returns:
        Resolved base directory path.
    """
    return get_settings().base_dir.resolve()


@lru_cache
def get_embedding_model() -> EmbeddingModel:
    """Get the cached embedding model instance."""
    return EmbeddingModel(get_settings().embedding_model)


@lru_cache
def get_embedding_cache() -> EmbeddingCache:
    """Get the cached embedding cache instance."""
    settings = get_settings()
    model = get_embedding_model()
    return EmbeddingCache(
        cache_dir=settings.cache_dir,
        model_name=model.model_name,
        dimension=model.get_dimension(),
    )


@lru_cache
def get_indexer() -> EmbeddingIndexer:
    """Get the cached indexer instance."""
    base_dir = get_base_dir()
    cache = get_embedding_cache()
    model = get_embedding_model()

    def get_files() -> list[Path]:
        return list(base_dir.rglob("*.md"))

    return EmbeddingIndexer(cache, model, get_files, base_dir)


def is_indexing_ready() -> bool:
    """Check if indexing is complete and ready for semantic search.

    Returns:
        True if indexer state is READY (indexing completed at least once).
    """
    return get_indexer().state == IndexerState.READY
