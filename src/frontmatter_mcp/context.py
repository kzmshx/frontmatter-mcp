"""Application context management for frontmatter-mcp."""

from functools import lru_cache
from pathlib import Path

from frontmatter_mcp.semantic import EmbeddingCache, EmbeddingIndexer, EmbeddingModel
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
    base_dir = get_base_dir()
    cache_dir = settings.get_cache_dir(base_dir)
    model = get_embedding_model()
    return EmbeddingCache(
        cache_dir=cache_dir,
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
        True if indexer exists and is not currently indexing.
    """
    return not get_indexer().is_indexing


def clear_context_cache() -> None:
    """Clear all cached context instances (for testing)."""
    # Check if cache_clear exists (may be replaced by monkeypatch in tests)
    if hasattr(get_embedding_model, "cache_clear"):
        get_embedding_model.cache_clear()
    if hasattr(get_embedding_cache, "cache_clear"):
        get_embedding_cache.cache_clear()
    if hasattr(get_indexer, "cache_clear"):
        get_indexer.cache_clear()
