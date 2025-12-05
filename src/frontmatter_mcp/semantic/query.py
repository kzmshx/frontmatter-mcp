"""Semantic search query support module."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import duckdb
import numpy as np

if TYPE_CHECKING:
    from frontmatter_mcp.semantic.model import EmbeddingModel


@dataclass
class SemanticContext:
    """Context for semantic search in query execution.

    Bundles embeddings and model together to ensure they are always
    provided as a pair.
    """

    embeddings: dict[str, np.ndarray]
    """Dict mapping file path to embedding vector."""

    model: "EmbeddingModel"
    """Embedding model for encode() and embed() function."""


def setup_semantic_search(
    conn: duckdb.DuckDBPyConnection,
    semantic: SemanticContext,
) -> None:
    """Set up semantic search capabilities in DuckDB connection.

    Args:
        conn: DuckDB connection.
        semantic: Semantic search context with embeddings and model.
    """
    # Install and load VSS extension
    conn.execute("INSTALL vss")
    conn.execute("LOAD vss")

    # Get dimension from model
    dim = semantic.model.get_dimension()

    # Register embed() function
    def embed_func(text: str) -> list[float]:
        return semantic.model.encode(text).tolist()

    conn.create_function("embed", embed_func, [str], f"FLOAT[{dim}]")

    # Create embeddings table
    conn.execute(f"""
        CREATE TABLE embeddings (
            path TEXT PRIMARY KEY,
            vector FLOAT[{dim}]
        )
    """)

    # Insert embeddings
    for path, vector in semantic.embeddings.items():
        conn.execute(
            "INSERT INTO embeddings (path, vector) VALUES (?, ?)",
            [path, vector.tolist()],
        )

    # Create files view with embedding column via JOIN
    conn.execute("""
        CREATE VIEW files AS
        SELECT f.*, e.vector as embedding
        FROM files_base f
        LEFT JOIN embeddings e ON f.path = e.path
    """)
