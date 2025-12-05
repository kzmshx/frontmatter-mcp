"""Application context management for frontmatter-mcp."""

from pathlib import Path

from frontmatter_mcp.semantic import EmbeddingCache, EmbeddingIndexer, EmbeddingModel
from frontmatter_mcp.settings import settings

# Global base directory
_base_dir: Path | None = None

# Semantic search components (lazy-loaded)
_embedding_model: EmbeddingModel | None = None
_embedding_cache: EmbeddingCache | None = None
_indexer: EmbeddingIndexer | None = None


def set_base_dir(path: Path) -> None:
    """Set the base directory."""
    global _base_dir
    _base_dir = path


def get_base_dir() -> Path:
    """Get the configured base directory."""
    if _base_dir is None:
        raise RuntimeError("Base directory not configured. Use --base-dir argument.")
    return _base_dir


def get_embedding_model() -> EmbeddingModel:
    """Get or create the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        if settings.embedding_model:
            _embedding_model = EmbeddingModel(settings.embedding_model)
        else:
            _embedding_model = EmbeddingModel()
    return _embedding_model


def get_embedding_cache(base_dir: Path) -> EmbeddingCache:
    """Get or create the embedding cache.

    Args:
        base_dir: Base directory for default cache location.

    Returns:
        EmbeddingCache instance.
    """
    global _embedding_cache
    if _embedding_cache is None:
        cache_dir = settings.get_cache_dir(base_dir)
        model = get_embedding_model()
        _embedding_cache = EmbeddingCache(
            cache_dir=cache_dir,
            model_name=model.model_name,
            dimension=model.get_dimension(),
        )
    return _embedding_cache


def get_indexer(base_dir: Path) -> EmbeddingIndexer:
    """Get or create the indexer.

    Args:
        base_dir: Base directory for file discovery and cache.

    Returns:
        EmbeddingIndexer instance.
    """
    global _indexer
    if _indexer is None:
        cache = get_embedding_cache(base_dir)
        model = get_embedding_model()

        def get_files() -> list[Path]:
            return list(base_dir.rglob("*.md"))

        _indexer = EmbeddingIndexer(cache, model, get_files, base_dir)
    return _indexer


def is_indexing_ready() -> bool:
    """Check if indexing is complete and ready for semantic search.

    Returns:
        True if indexer exists and is not currently indexing.
    """
    return _indexer is not None and not _indexer.is_indexing
