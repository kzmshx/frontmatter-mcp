"""MCP Server implementation using FastMCP."""

import glob as globmodule
from pathlib import Path
from typing import Any

import frontmatter
from fastmcp import FastMCP

from frontmatter_mcp.files import (
    FileRecordCache,
    parse_files,
    update_file,
)
from frontmatter_mcp.query import create_base_connection, execute_query
from frontmatter_mcp.query_schema import create_base_schema
from frontmatter_mcp.semantic import (
    SemanticContext,
    add_semantic_columns,
    get_semantic_context,
)
from frontmatter_mcp.semantic.query_schema import add_semantic_schema
from frontmatter_mcp.settings import Settings, get_settings

Response = dict[str, Any]

mcp = FastMCP("frontmatter-mcp")

_settings: Settings | None = None
_semantic_ctx: SemanticContext | None = None
_file_record_cache: FileRecordCache = FileRecordCache()


def _collect_files(base_dir: Path, glob_pattern: str) -> list[Path]:
    """Collect files matching the glob pattern."""
    pattern = str(base_dir / glob_pattern)
    matches = globmodule.glob(pattern, recursive=True)
    return [Path(p) for p in matches if Path(p).is_file()]


def _build_response(
    results: dict[str, Any], warnings: list[Any] | None = None
) -> Response:
    """Build response dict for single operations."""
    response: dict[str, Any] = results
    if warnings:
        response["warnings"] = warnings
    return response


def _build_batch_response(updated_files: list[str], warnings: list[str]) -> Response:
    """Build response dict for batch operations."""
    return _build_response(
        {
            "updated_count": len(updated_files),
            "updated_files": updated_files,
        },
        warnings,
    )


def _resolve_path(base_dir: Path, rel_path: str) -> Path:
    """Resolve relative path and validate it's within base_dir and exists.

    Args:
        base_dir: Base directory (already resolved).
        rel_path: Relative path from base_dir.

    Returns:
        Resolved absolute path.

    Raises:
        ValueError: If path is outside base_dir.
        FileNotFoundError: If file doesn't exist.
    """
    abs_path = (base_dir / rel_path).resolve()

    try:
        abs_path.relative_to(base_dir)
    except ValueError as e:
        raise ValueError(f"Path must be within base directory: {rel_path}") from e

    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {rel_path}")

    return abs_path


@mcp.tool()
def query_inspect(glob: str) -> Response:
    """Get frontmatter schema from files matching glob pattern.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").

    Returns:
        Dict with file_count, schema (type, nullable, examples).
    """
    assert _settings is not None

    paths = _collect_files(_settings.base_dir, glob)
    records, warnings = parse_files(paths, _settings.base_dir, _file_record_cache)

    # Create base schema with path and frontmatter columns
    schema = create_base_schema(records)

    # Add semantic schema columns if semantic search is ready
    if _settings.enable_semantic:
        assert _semantic_ctx is not None
        if _semantic_ctx.is_ready:
            add_semantic_schema(schema, _semantic_ctx)

    return _build_response(
        {
            "file_count": len(records),
            "schema": schema,
        },
        warnings,
    )


@mcp.tool()
def query(glob: str, sql: str) -> Response:
    """Query frontmatter with DuckDB SQL.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        sql: SQL query string. Reference 'files' table. Columns are frontmatter
            properties plus 'path'.

    Semantic search (when enabled and indexing is complete):
        - embedding: document embedding vector (NULL if not indexed)
        - embed('text'): converts text to embedding vector
        - array_cosine_similarity(a, b): similarity score (0-1)

        Example - find similar documents:
            SELECT path,
                   array_cosine_similarity(embedding, embed('search term')) as score
            FROM files WHERE embedding IS NOT NULL
            ORDER BY score DESC LIMIT 10

    Returns:
        Dict with results array, row_count, and columns.
    """
    assert _settings is not None

    paths = _collect_files(_settings.base_dir, glob)
    records, warnings = parse_files(paths, _settings.base_dir, _file_record_cache)

    # Create base connection with files table (path and frontmatter columns)
    conn = create_base_connection(records)

    # Add semantic search columns if enabled and ready
    if _settings.enable_semantic:
        assert _semantic_ctx is not None
        if _semantic_ctx.is_ready:
            add_semantic_columns(conn, _semantic_ctx)

    query_result = execute_query(conn, sql)

    return _build_response(
        {
            "results": query_result["results"],
            "row_count": query_result["row_count"],
            "columns": query_result["columns"],
        },
        warnings,
    )


@mcp.tool(enabled=False)
def index_status() -> Response:
    """Get the status of the semantic search index.

    Returns:
        Dict with state ("idle", "indexing", "ready").
        - idle: Indexing has never been started
        - indexing: Indexing is in progress
        - ready: Indexing completed, embed() and embedding column available
    """
    assert _semantic_ctx is not None
    return _build_response({"state": _semantic_ctx.indexer.state.value})


@mcp.tool(enabled=False)
def index_wait(timeout: float = 60.0) -> Response:
    """Wait for semantic search indexing to complete.

    Blocks until indexing finishes or timeout is reached.
    Use this instead of polling index_status when you need embeddings.

    Args:
        timeout: Maximum seconds to wait. Default 60.

    Returns:
        Dict with success (bool) and state.
        - success=true: Indexing completed or idle (not started)
        - success=false: Timeout reached while indexing in progress
    """
    assert _semantic_ctx is not None
    completed = _semantic_ctx.indexer.wait(timeout=timeout)
    return _build_response(
        {
            "success": completed,
            "state": _semantic_ctx.indexer.state.value,
        }
    )


@mcp.tool(enabled=False)
def index_refresh() -> Response:
    """Refresh the semantic search index (differential update).

    Starts background indexing. On first run, indexes all files.
    Subsequent runs only update files changed since last index (by mtime).

    If indexing is already in progress, returns current status.

    Returns:
        Dict with message and target_count.

    Notes:
        Call this after editing files during a session to update the index.
    """
    assert _semantic_ctx is not None
    return _build_response(_semantic_ctx.indexer.start())


@mcp.tool()
def update(
    path: str,
    set: dict[str, Any] | None = None,
    unset: list[str] | None = None,
) -> Response:
    """Update frontmatter properties in a single file.

    Args:
        path: File path relative to base directory.
        set: Properties to add or overwrite. Values are applied as-is (null becomes
            YAML null, empty string becomes empty value).
        unset: Property names to remove completely.

    Returns:
        Dict with path and updated frontmatter.

    Notes:
        - If same key appears in both set and unset, unset takes priority.
        - If file has no frontmatter, it will be created.
    """
    assert _settings is not None

    base_dir = _settings.base_dir
    abs_path = _resolve_path(base_dir, path)
    result = update_file(abs_path, base_dir, set, unset)

    return _build_response(result)


@mcp.tool()
def batch_update(
    glob: str,
    set: dict[str, Any] | None = None,
    unset: list[str] | None = None,
) -> Response:
    """Update frontmatter properties in multiple files matching glob pattern.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        set: Properties to add or overwrite in all matched files.
        unset: Property names to remove from all matched files.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If same key appears in both set and unset, unset takes priority.
        - If a file has no frontmatter, it will be created.
        - Errors in individual files are recorded in warnings, not raised.
    """
    assert _settings is not None

    base_dir = _settings.base_dir
    paths = _collect_files(base_dir, glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        rel_path = str(file_path.relative_to(base_dir))
        try:
            abs_path = _resolve_path(base_dir, rel_path)
        except (ValueError, FileNotFoundError) as e:
            warnings.append(str(e))
            continue

        try:
            result = update_file(abs_path, base_dir, set, unset)
            updated_files.append(result["path"])
        except Exception as e:
            warnings.append(f"Failed to update {rel_path}: {e}")

    return _build_batch_response(updated_files, warnings)


@mcp.tool()
def batch_array_add(
    glob: str,
    property: str,
    value: Any,
    allow_duplicates: bool = False,
) -> Response:
    """Add a value to an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        value: Value to add. If value is an array, it's added as a single element.
        allow_duplicates: If False (default), skip files where value already exists.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, it will be created with [value].
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    assert _settings is not None

    base_dir = _settings.base_dir
    paths = _collect_files(base_dir, glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        rel_path = str(file_path.relative_to(base_dir))
        try:
            abs_path = _resolve_path(base_dir, rel_path)
        except (ValueError, FileNotFoundError) as e:
            warnings.append(str(e))
            continue

        try:
            post = frontmatter.load(abs_path)
            current = post.get(property)

            # Property doesn't exist: create new array
            if current is None:
                post[property] = [value]
                frontmatter.dump(post, abs_path)
                updated_files.append(rel_path)
                continue

            # Property is not an array: skip with warning
            if not isinstance(current, list):
                warnings.append(f"Skipped {rel_path}: '{property}' is not an array")
                continue

            # Check for duplicates
            if not allow_duplicates and value in current:
                continue

            # Add value
            current.append(value)
            frontmatter.dump(post, abs_path)
            updated_files.append(rel_path)

        except Exception as e:
            warnings.append(f"Failed to update {rel_path}: {e}")

    return _build_batch_response(updated_files, warnings)


@mcp.tool()
def batch_array_remove(
    glob: str,
    property: str,
    value: Any,
) -> Response:
    """Remove a value from an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        value: Value to remove.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, file is skipped.
        - If value doesn't exist in array, file is skipped.
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    assert _settings is not None

    base_dir = _settings.base_dir
    paths = _collect_files(base_dir, glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        rel_path = str(file_path.relative_to(base_dir))
        try:
            abs_path = _resolve_path(base_dir, rel_path)
        except (ValueError, FileNotFoundError) as e:
            warnings.append(str(e))
            continue

        try:
            post = frontmatter.load(abs_path)
            current = post.get(property)

            # Property doesn't exist: skip
            if current is None:
                continue

            # Property is not an array: skip with warning
            if not isinstance(current, list):
                warnings.append(f"Skipped {rel_path}: '{property}' is not an array")
                continue

            # Value doesn't exist: skip
            if value not in current:
                continue

            # Remove value
            current.remove(value)
            frontmatter.dump(post, abs_path)
            updated_files.append(rel_path)

        except Exception as e:
            warnings.append(f"Failed to update {rel_path}: {e}")

    return _build_batch_response(updated_files, warnings)


@mcp.tool()
def batch_array_replace(
    glob: str,
    property: str,
    old_value: Any,
    new_value: Any,
) -> Response:
    """Replace a value in an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        old_value: Value to replace.
        new_value: New value.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, file is skipped.
        - If old_value doesn't exist in array, file is skipped.
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    assert _settings is not None

    base_dir = _settings.base_dir
    paths = _collect_files(base_dir, glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        rel_path = str(file_path.relative_to(base_dir))
        try:
            abs_path = _resolve_path(base_dir, rel_path)
        except (ValueError, FileNotFoundError) as e:
            warnings.append(str(e))
            continue

        try:
            post = frontmatter.load(abs_path)
            current = post.get(property)

            # Property doesn't exist: skip
            if current is None:
                continue

            # Property is not an array: skip with warning
            if not isinstance(current, list):
                warnings.append(f"Skipped {rel_path}: '{property}' is not an array")
                continue

            # Old value doesn't exist: skip
            if old_value not in current:
                continue

            # Replace value
            idx = current.index(old_value)
            current[idx] = new_value
            frontmatter.dump(post, abs_path)
            updated_files.append(rel_path)

        except Exception as e:
            warnings.append(f"Failed to update {rel_path}: {e}")

    return _build_batch_response(updated_files, warnings)


@mcp.tool()
def batch_array_sort(
    glob: str,
    property: str,
    reverse: bool = False,
) -> Response:
    """Sort an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.
        reverse: If True, sort in descending order. Default is ascending.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - If property doesn't exist, file is skipped.
        - If array is empty, file is skipped.
        - If array is already sorted, file is skipped.
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    assert _settings is not None

    base_dir = _settings.base_dir
    paths = _collect_files(base_dir, glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        rel_path = str(file_path.relative_to(base_dir))
        try:
            abs_path = _resolve_path(base_dir, rel_path)
        except (ValueError, FileNotFoundError) as e:
            warnings.append(str(e))
            continue

        try:
            post = frontmatter.load(abs_path)
            current = post.get(property)

            # Property doesn't exist: skip
            if current is None:
                continue

            # Property is not an array: skip with warning
            if not isinstance(current, list):
                warnings.append(f"Skipped {rel_path}: '{property}' is not an array")
                continue

            # Empty array or single element: skip (already sorted)
            if len(current) <= 1:
                continue

            # Check if already sorted using pairwise comparison
            if not reverse:
                is_sorted = all(
                    current[i] <= current[i + 1] for i in range(len(current) - 1)
                )
            else:
                is_sorted = all(
                    current[i] >= current[i + 1] for i in range(len(current) - 1)
                )
            if is_sorted:
                continue

            # Sort
            post[property] = sorted(current, reverse=reverse)
            frontmatter.dump(post, abs_path)
            updated_files.append(rel_path)

        except Exception as e:
            warnings.append(f"Failed to update {rel_path}: {e}")

    return _build_batch_response(updated_files, warnings)


@mcp.tool()
def batch_array_unique(
    glob: str,
    property: str,
) -> Response:
    """Remove duplicate values from an array property in multiple files.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        property: Name of the array property.

    Returns:
        Dict with updated_count, updated_files, and warnings.

    Notes:
        - Preserves the order of first occurrence.
        - If property doesn't exist, file is skipped.
        - If array is empty or has single element, file is skipped.
        - If array has no duplicates, file is skipped.
        - If property is not an array, file is skipped with a warning.
        - Files are only included in updated_files if actually modified.
    """
    assert _settings is not None

    base_dir = _settings.base_dir
    paths = _collect_files(base_dir, glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        rel_path = str(file_path.relative_to(base_dir))
        try:
            abs_path = _resolve_path(base_dir, rel_path)
        except (ValueError, FileNotFoundError) as e:
            warnings.append(str(e))
            continue

        try:
            post = frontmatter.load(abs_path)
            current = post.get(property)

            # Property doesn't exist: skip
            if current is None:
                continue

            # Property is not an array: skip with warning
            if not isinstance(current, list):
                warnings.append(f"Skipped {rel_path}: '{property}' is not an array")
                continue

            # Empty array or single element: skip (no duplicates possible)
            if len(current) <= 1:
                continue

            # Remove duplicates while preserving order
            unique = list(dict.fromkeys(current))

            # No duplicates: skip
            if len(unique) == len(current):
                continue

            # Update
            post[property] = unique
            frontmatter.dump(post, abs_path)
            updated_files.append(rel_path)

        except Exception as e:
            warnings.append(f"Failed to update {rel_path}: {e}")

    return _build_batch_response(updated_files, warnings)


def main() -> None:
    """Entry point for the MCP server."""
    global _settings, _semantic_ctx

    _settings = get_settings()

    if _settings.enable_semantic:
        _semantic_ctx = get_semantic_context(_settings)
        _semantic_ctx.indexer.start()
        index_status.enable()
        index_wait.enable()
        index_refresh.enable()

    mcp.run()


if __name__ == "__main__":
    main()
