"""Semantic search context management."""

from dataclasses import dataclass
from pathlib import Path

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.indexer import EmbeddingIndexer, IndexerState
from frontmatter_mcp.semantic.model import EmbeddingModel
from frontmatter_mcp.settings import Settings


@dataclass
class SemanticContext:
    """Context for semantic search operations."""

    model: EmbeddingModel
    """Embedding model for encoding text."""

    cache: EmbeddingCache
    """Cache for storing embeddings."""

    indexer: EmbeddingIndexer
    """Indexer for building and updating embeddings."""

    @property
    def is_ready(self) -> bool:
        """Check if indexing is complete and ready for semantic search."""
        return self.indexer.state == IndexerState.READY


def get_semantic_context(settings: Settings) -> SemanticContext:
    """Create a semantic context instance.

    Args:
        settings: Application settings.
        ctx: Core application context.

    Returns:
        SemanticContext with model, cache, and indexer.
    """
    model = EmbeddingModel(settings.embedding_model)
    cache = EmbeddingCache(
        cache_dir=settings.cache_dir,
        model_name=model.model_name,
        dimension=model.get_dimension(),
    )

    def get_files() -> list[Path]:
        return list(settings.base_dir.rglob("*.md"))

    indexer = EmbeddingIndexer(cache, model, get_files, settings.base_dir)

    return SemanticContext(model=model, cache=cache, indexer=indexer)
