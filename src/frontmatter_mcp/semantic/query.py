"""Semantic search query support module."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import duckdb

if TYPE_CHECKING:
    from frontmatter_mcp.semantic.context import SemanticContext


def setup_semantic_search(
    conn: duckdb.DuckDBPyConnection,
    ctx: SemanticContext,
) -> None:
    """Set up semantic search capabilities in DuckDB connection.

    Args:
        conn: DuckDB connection.
        ctx: Semantic context with model and cache.
    """
    # Install and load VSS extension
    conn.execute("INSTALL vss")
    conn.execute("LOAD vss")

    # Get dimension from model
    dim = ctx.model.get_dimension()

    # Register embed() function
    def embed_func(text: str) -> list[float]:
        return cast(list[float], ctx.model.encode(text).tolist())

    conn.create_function(
        "embed",
        embed_func,
        [str],  # type: ignore[list-item]
        f"FLOAT[{dim}]",  # type: ignore[arg-type]
    )

    # Create embeddings table
    conn.execute(f"""
        CREATE TABLE embeddings (
            path TEXT PRIMARY KEY,
            vector FLOAT[{dim}]
        )
    """)

    # Insert embeddings from cache
    for path, vector in ctx.cache.get_all().items():
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
