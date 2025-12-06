"""DuckDB query execution module."""

import json
from typing import Any

import duckdb
import pyarrow as pa


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


def create_base_connection(records: list[dict[str, Any]]) -> duckdb.DuckDBPyConnection:
    """Create a new in-memory DuckDB connection with files table.

    Creates a files table with path and frontmatter columns.

    Args:
        records: List of parsed frontmatter records.

    Returns:
        DuckDB connection with files table.
    """
    conn = duckdb.connect(":memory:")

    if not records:
        conn.execute("CREATE TABLE files (path TEXT)")
        return conn

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

    # Register and create actual table (not view)
    conn.register("_temp_source", table)
    conn.execute("CREATE TABLE files AS SELECT * FROM _temp_source")

    return conn


def execute_query(conn: duckdb.DuckDBPyConnection, sql: str) -> dict[str, Any]:
    """Execute SQL query on prepared connection.

    Args:
        conn: DuckDB connection with tables already set up.
        sql: SQL query string.

    Returns:
        Dictionary with results, row_count, and columns.
    """
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
