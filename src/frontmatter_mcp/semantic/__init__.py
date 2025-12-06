"""Semantic search module for frontmatter-mcp."""

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.context import SemanticContext, get_semantic_context
from frontmatter_mcp.semantic.indexer import EmbeddingIndexer, IndexerState
from frontmatter_mcp.semantic.model import EmbeddingModel
from frontmatter_mcp.semantic.query import add_semantic_columns

__all__ = [
    "EmbeddingCache",
    "EmbeddingIndexer",
    "EmbeddingModel",
    "IndexerState",
    "SemanticContext",
    "add_semantic_columns",
    "get_semantic_context",
]
