"""DuckDB query execution module."""

import json
from typing import TYPE_CHECKING, Any

import duckdb
import pyarrow as pa

if TYPE_CHECKING:
    import numpy as np

    from frontmatter_mcp.embedding import EmbeddingModel


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
    embeddings: dict[str, "np.ndarray"] | None = None,
    embedding_model: "EmbeddingModel | None" = None,
) -> dict[str, Any]:
    """Execute DuckDB SQL query on frontmatter records.

    All values are passed as strings to DuckDB. Use TRY_CAST in SQL
    for type conversion. Arrays are JSON-encoded strings.

    Args:
        records: List of parsed frontmatter records.
        sql: SQL query string. Must reference 'files' table.
        embeddings: Optional dict mapping path to embedding vector.
        embedding_model: Optional embedding model for embed() function.

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

    # Add embedding column if embeddings are provided
    if embeddings and embedding_model:
        # Register as files_base, then create files view with embedding
        conn.register("files_base", table)
        _setup_semantic_search(conn, embeddings, embedding_model)
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
    embeddings: dict[str, "np.ndarray"],
    embedding_model: "EmbeddingModel",
) -> None:
    """Set up semantic search capabilities in DuckDB connection.

    Args:
        conn: DuckDB connection.
        embeddings: Dict mapping path to embedding vector.
        embedding_model: Embedding model for embed() function.
    """

    # Install and load VSS extension
    conn.execute("INSTALL vss")
    conn.execute("LOAD vss")

    # Get dimension from model
    dim = embedding_model.get_dimension()

    # Register embed() function
    def embed_func(text: str) -> list[float]:
        return embedding_model.encode(text).tolist()

    conn.create_function("embed", embed_func, [str], f"FLOAT[{dim}]")

    # Create embeddings table
    conn.execute(f"""
        CREATE TABLE embeddings (
            path TEXT PRIMARY KEY,
            vector FLOAT[{dim}]
        )
    """)

    # Insert embeddings
    for path, vector in embeddings.items():
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
