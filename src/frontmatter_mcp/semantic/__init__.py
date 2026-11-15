"""Semantic search: chunked embeddings, BM25, and reranking (the [semantic] extra).

Importing this package does not import torch or sentence-transformers; the
models load on first use.
"""

from frontmatter_mcp.semantic.context import SemanticContext, create_semantic_context
from frontmatter_mcp.semantic.indexer import ChunkIndexer, IndexerState
from frontmatter_mcp.semantic.models import EmbeddingModel, Reranker
from frontmatter_mcp.semantic.sql import add_semantic_columns, add_semantic_schema
from frontmatter_mcp.semantic.store import ChunkStore

__all__ = [
    "ChunkIndexer",
    "ChunkStore",
    "EmbeddingModel",
    "IndexerState",
    "Reranker",
    "SemanticContext",
    "add_semantic_columns",
    "add_semantic_schema",
    "create_semantic_context",
]
