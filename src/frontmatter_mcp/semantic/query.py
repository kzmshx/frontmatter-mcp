"""Semantic search query support module."""

from typing import cast

import duckdb
import pyarrow as pa

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

    # Get embeddings from cache using read-only connection
    # This avoids lock conflicts when another process holds the write lock
    embeddings = ctx.cache.get_all_readonly()
    if embeddings:
        paths = list(embeddings.keys())
        vectors = [v.tolist() for v in embeddings.values()]

        arrow_table = pa.table({"path": paths, "vector": vectors})
        conn.register("arrow_embeddings", arrow_table)
        conn.execute(f"""
            CREATE TEMP TABLE embeddings AS
            SELECT path, vector::FLOAT[{dim}] as vector FROM arrow_embeddings
        """)
        conn.unregister("arrow_embeddings")

        # Update files table with embeddings
        conn.execute("""
            UPDATE files
            SET embedding = e.vector
            FROM embeddings e
            WHERE files.path = e.path
        """)
