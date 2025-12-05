"""Semantic search module for frontmatter-mcp."""

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.indexer import EmbeddingIndexer, IndexerState
from frontmatter_mcp.semantic.model import EmbeddingModel
from frontmatter_mcp.semantic.query import (
    SemanticContext,
    extend_schema_semantic,
    setup_semantic_search,
)

__all__ = [
    "EmbeddingCache",
    "EmbeddingIndexer",
    "IndexerState",
    "EmbeddingModel",
    "SemanticContext",
    "extend_schema_semantic",
    "setup_semantic_search",
]
