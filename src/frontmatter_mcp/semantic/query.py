"""Semantic search query support module."""

from typing import cast

import duckdb
import numpy as np
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
    # Get dimension from model
    dim = ctx.model.get_dimension()

    # Register embed(): encodes a search query (query prefix, normalized), so
    # array_cosine_similarity(embedding, embed('...')) ranks documents
    def embed_func(text: str) -> list[float]:
        return cast(list[float], ctx.model.encode_query(text).tolist())

    conn.create_function(
        "embed",
        embed_func,
        [str],
        f"FLOAT[{dim}]",
    )

    # Document vectors come from the in-memory search index (built once per
    # indexing run), so a query does not re-read the cache file
    index = ctx.search_index()
    vectors = index.document_vectors() if index is not None else {}
    if vectors:
        matrix = np.stack(list(vectors.values())).astype(np.float32)
        arrow_table = pa.table(
            {
                "path": list(vectors.keys()),
                "vector": pa.FixedSizeListArray.from_arrays(
                    pa.array(matrix.ravel()), dim
                ),
            }
        )
        conn.register("arrow_embeddings", arrow_table)
        conn.execute(f"""
            CREATE TEMP TABLE embeddings AS
            SELECT path, vector::FLOAT[{dim}] AS vector FROM arrow_embeddings
        """)
        conn.unregister("arrow_embeddings")
    # Add the column, then fill it (rebuilding files with a LEFT JOIN failed on
    # real vault data with "cannot cast list with length 0 to array")
    conn.execute(f"ALTER TABLE files ADD COLUMN embedding FLOAT[{dim}]")
    if vectors:
        conn.execute("""
            UPDATE files SET embedding = e.vector
            FROM embeddings e WHERE files.path = e.path
        """)
