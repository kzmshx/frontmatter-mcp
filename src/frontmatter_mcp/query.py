"""DuckDB query execution module."""

import json
from dataclasses import dataclass
from typing import Any

import duckdb
import numpy as np
import pyarrow as pa

from frontmatter_mcp.embedding import EmbeddingModel


@dataclass
class SemanticContext:
    """Context for semantic search in query execution.

    Bundles embeddings and model together to ensure they are always
    provided as a pair.
    """

    embeddings: dict[str, np.ndarray]
    """Dict mapping file path to embedding vector."""

    model: EmbeddingModel
    """Embedding model for encode() and embed() function."""


def _serialize_value(value: Any) -> str | None:
    """Serialize a value to string for DuckDB.

    Arrays are JSON-encoded, other values are converted to string.
    None remains None.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def execute_query(
    records: list[dict[str, Any]],
    sql: str,
    semantic: SemanticContext | None = None,
) -> dict[str, Any]:
    """Execute DuckDB SQL query on frontmatter records.

    All values are passed as strings to DuckDB. Use TRY_CAST in SQL
    for type conversion. Arrays are JSON-encoded strings.

    Args:
        records: List of parsed frontmatter records.
        sql: SQL query string. Must reference 'files' table.
        semantic: Optional semantic search context with embeddings and model.

    Returns:
        Dictionary with results, row_count, and columns.
    """
    if not records:
        return {
            "results": [],
            "row_count": 0,
            "columns": [],
        }

    # Collect all unique keys across all records
    all_keys: set[str] = set()
    for record in records:
        all_keys.update(record.keys())

    # Build columns dict with serialized string values
    columns_data: dict[str, list[str | None]] = {key: [] for key in all_keys}
    for record in records:
        for key in all_keys:
            columns_data[key].append(_serialize_value(record.get(key)))

    # Create pyarrow table with explicit string type for all columns
    schema = pa.schema([(key, pa.string()) for key in all_keys])
    table = pa.table(columns_data, schema=schema)

    # Create connection and register table
    conn = duckdb.connect(":memory:")

    # Add embedding column if semantic context is provided
    if semantic:
        # Register as files_base, then create files view with embedding
        conn.register("files_base", table)
        _setup_semantic_search(conn, semantic)
    else:
        conn.register("files", table)

    # Execute query
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()

    # Convert to list of dicts
    results = [dict(zip(columns, row, strict=True)) for row in rows]

    return {
        "results": results,
        "row_count": len(results),
        "columns": columns,
    }


def _setup_semantic_search(
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
