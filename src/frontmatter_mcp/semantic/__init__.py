"""Semantic search module for frontmatter-mcp."""

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.context import SemanticContext, get_semantic_context
from frontmatter_mcp.semantic.indexer import EmbeddingIndexer, IndexerState
from frontmatter_mcp.semantic.model import EmbeddingModel
from frontmatter_mcp.semantic.query import setup_semantic_search

__all__ = [
    "EmbeddingCache",
    "EmbeddingIndexer",
    "IndexerState",
    "EmbeddingModel",
    "SemanticContext",
    "get_semantic_context",
    "setup_semantic_search",
]
