"""Semantic search query support module."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import duckdb

if TYPE_CHECKING:
    from frontmatter_mcp.semantic.context import SemanticContext


def add_semantic_columns(
    conn: duckdb.DuckDBPyConnection,
    ctx: SemanticContext,
) -> None:
    """Add semantic search columns and functions to DuckDB connection.

    Adds embedding column to files table and registers embed() function.

    Args:
        conn: DuckDB connection with 'files' table already created.
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

    # Add embedding column to files table
    conn.execute(f"ALTER TABLE files ADD COLUMN embedding FLOAT[{dim}]")

    # Create temporary embeddings table for UPDATE
    conn.execute(f"""
        CREATE TEMP TABLE embeddings (
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

    # Update files table with embeddings
    conn.execute("""
        UPDATE files
        SET embedding = e.vector
        FROM embeddings e
        WHERE files.path = e.path
    """)
