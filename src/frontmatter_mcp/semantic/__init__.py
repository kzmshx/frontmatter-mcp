"""Semantic search module for frontmatter-mcp."""

from frontmatter_mcp.semantic.cache import EmbeddingCache
from frontmatter_mcp.semantic.indexer import EmbeddingIndexer
from frontmatter_mcp.semantic.model import EmbeddingModel
from frontmatter_mcp.semantic.query import SemanticContext, setup_semantic_search

__all__ = [
    "EmbeddingCache",
    "EmbeddingIndexer",
    "EmbeddingModel",
    "SemanticContext",
    "setup_semantic_search",
]
