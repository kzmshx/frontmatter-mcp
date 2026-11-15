"""Read-only SQL tools over frontmatter: query_inspect and query."""

import re
from typing import Any

import duckdb
from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError

from frontmatter_mcp.app import READ_ONLY, mcp
from frontmatter_mcp.dependencies import (
    get_file_record_cache,
    get_semantic_ctx,
    get_settings,
)
from frontmatter_mcp.paths import collect_files
from frontmatter_mcp.records import FileRecordCache, parse_files
from frontmatter_mcp.schema import infer_schema
from frontmatter_mcp.semantic import (
    SemanticContext,
    add_semantic_columns,
    add_semantic_schema,
)
from frontmatter_mcp.settings import Settings
from frontmatter_mcp.sql import create_files_connection, execute_query, files_columns
from frontmatter_mcp.tools.results import QueryInspectResult, QueryResult

# How long a call that needs the index waits for an indexing run it started.
# The first full index of a large vault can take longer; the call then uses
# what was indexed so far.
INDEX_WAIT_SECONDS = 60.0

_USES_EMBEDDING = re.compile(r"\bembed(?:ding)?\b", re.IGNORECASE)


def run_sql(conn: duckdb.DuckDBPyConnection, sql: str) -> dict[str, Any]:
    """Execute SQL; report errors to the client with the available columns."""
    try:
        return execute_query(conn, sql)
    except duckdb.Error as e:
        columns = ", ".join(files_columns(conn))
        raise ToolError(f"{e}\nColumns of the files table: {columns}") from e


@mcp.tool(annotations=READ_ONLY)
def query_inspect(
    glob: str,
    settings: Settings = Depends(get_settings),
    cache: FileRecordCache = Depends(get_file_record_cache),
    semantic_ctx: SemanticContext | None = Depends(get_semantic_ctx),
) -> QueryInspectResult:
    """Get frontmatter schema from files matching glob pattern.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").

    Returns:
        Dict with file_count and schema (type, nullable, examples per column).
    """
    paths = collect_files(settings.base_dir, glob, settings.exclude)
    records, warnings = parse_files(paths, settings.base_dir, cache)
    schema = infer_schema(records)
    if semantic_ctx is not None and semantic_ctx.is_ready:
        add_semantic_schema(schema, semantic_ctx)
    result = QueryInspectResult(file_count=len(records), schema=dict(schema))
    if warnings:
        result["warnings"] = warnings
    return result


@mcp.tool(annotations=READ_ONLY)
def query(
    glob: str,
    sql: str,
    settings: Settings = Depends(get_settings),
    cache: FileRecordCache = Depends(get_file_record_cache),
    semantic_ctx: SemanticContext | None = Depends(get_semantic_ctx),
) -> QueryResult:
    """Query frontmatter with DuckDB SQL.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        sql: SQL query string. Reference 'files' table. Columns are frontmatter
            properties plus 'path'. Values are strings; arrays are JSON strings
            (use from_json(tags, '["VARCHAR"]')).

    To search document text, use the search tool when it is available: it
    matches passages, combines meaning and wording, and returns the text.

    Only when semantic search is enabled:
        - embedding: document vector, the mean of its chunk vectors (NULL if
          the file has no indexed text)
        - embed('text'): encodes text as a search query
        - array_cosine_similarity(a, b): cosine similarity (-1 to 1)

        Example - documents similar to a phrase:
            SELECT path,
                   array_cosine_similarity(embedding, embed('search term')) AS score
            FROM files WHERE embedding IS NOT NULL
            ORDER BY score DESC LIMIT 10

    Returns:
        Dict with results array, row_count, and columns.
    """
    paths = collect_files(settings.base_dir, glob, settings.exclude)
    records, warnings = parse_files(paths, settings.base_dir, cache)
    conn = create_files_connection(records)

    # Semantic columns cost a search-index load; add them only when used
    if semantic_ctx is not None and _USES_EMBEDDING.search(sql):
        semantic_ctx.ensure_index(wait_seconds=INDEX_WAIT_SECONDS)
        # Like search, use whatever is indexed if the run is still going
        if semantic_ctx.search_index() is not None:
            add_semantic_columns(conn, semantic_ctx)

    query_result = run_sql(conn, sql)
    result = QueryResult(
        results=query_result["results"],
        row_count=query_result["row_count"],
        columns=query_result["columns"],
    )
    if warnings:
        result["warnings"] = warnings
    return result
