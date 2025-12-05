"""DuckDB query execution module."""

import json
from typing import Any, Callable

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


def execute_query(
    records: list[dict[str, Any]],
    sql: str,
    conn_setup: Callable[[duckdb.DuckDBPyConnection], None] | None = None,
) -> dict[str, Any]:
    """Execute DuckDB SQL query on frontmatter records.

    All values are passed as strings to DuckDB. Use TRY_CAST in SQL
    for type conversion. Arrays are JSON-encoded strings.

    Args:
        records: List of parsed frontmatter records.
        sql: SQL query string. Must reference 'files' table.
        conn_setup: Optional callback to set up the connection before query.
            When provided, 'files_base' table is registered instead of 'files',
            allowing the callback to create a 'files' view with additional columns.

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

    if conn_setup:
        # Register as files_base, then let callback create files view
        conn.register("files_base", table)
        conn_setup(conn)
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
