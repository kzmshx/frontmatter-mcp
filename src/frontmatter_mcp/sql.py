"""DuckDB tables over frontmatter records, and sandboxed query execution."""

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


def create_files_connection(
    records: list[dict[str, Any]],
) -> duckdb.DuckDBPyConnection:
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

    # Columns in first-seen order with path first, so SELECT * is stable
    all_keys: list[str] = list(
        dict.fromkeys(["path", *(k for record in records for k in record)])
    )

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
    conn.unregister("_temp_source")

    return conn


def restrict_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Block file system, network, and extension access, then lock the config.

    The query tool runs SQL written by the model. Without this, DuckDB functions
    such as read_text() and COPY ... TO can read and write any file the server
    process can reach, and httpfs can send data over the network. Tables that
    are already loaded (files, embeddings) and Python UDFs (embed) keep working.

    Safe to call more than once.

    Args:
        conn: DuckDB connection whose tables are already set up.
    """
    locked = conn.execute("SELECT current_setting('lock_configuration')").fetchone()
    if locked and locked[0]:
        return
    conn.execute("SET enable_external_access = false")
    conn.execute("SET autoinstall_known_extensions = false")
    conn.execute("SET autoload_known_extensions = false")
    conn.execute("SET lock_configuration = true")


def execute_query(conn: duckdb.DuckDBPyConnection, sql: str) -> dict[str, Any]:
    """Execute SQL query on prepared connection.

    The connection is restricted with restrict_connection() before the query
    runs, so set up every table before calling this.

    Args:
        conn: DuckDB connection with tables already set up.
        sql: SQL query string.

    Returns:
        Dictionary with results, row_count, and columns.
    """
    restrict_connection(conn)
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


def files_columns(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Column names of the files table."""
    return [row[0] for row in conn.execute("DESCRIBE files").fetchall()]
