"""MCP Server implementation using FastMCP."""

import glob as globmodule
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
from mcp.server.fastmcp import FastMCP

from frontmatter_mcp.frontmatter import parse_files, update_file
from frontmatter_mcp.query import SemanticContext, execute_query
from frontmatter_mcp.schema import infer_schema

if TYPE_CHECKING:
    from frontmatter_mcp.cache import EmbeddingCache
    from frontmatter_mcp.embedding import EmbeddingModel
    from frontmatter_mcp.indexer import Indexer

# Global base directory
_base_dir: Path | None = None

# Semantic search components (lazy-loaded)
_embedding_model: "EmbeddingModel | None" = None
_embedding_cache: "EmbeddingCache | None" = None
_indexer: "Indexer | None" = None

mcp = FastMCP("frontmatter-mcp")


def get_base_dir() -> Path:
    """Get the configured base directory."""
    if _base_dir is None:
        raise RuntimeError("Base directory not configured. Use --base-dir argument.")
    return _base_dir


def is_semantic_enabled() -> bool:
    """Check if semantic search is enabled via environment variable."""
    return os.getenv("FRONTMATTER_ENABLE_SEMANTIC", "").lower() in ("true", "1", "yes")


def get_embedding_model() -> "EmbeddingModel":
    """Get or create the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        from frontmatter_mcp.embedding import EmbeddingModel

        model_name = os.getenv("FRONTMATTER_EMBEDDING_MODEL")
        if model_name:
            _embedding_model = EmbeddingModel(model_name)
        else:
            _embedding_model = EmbeddingModel()
    return _embedding_model


def get_embedding_cache() -> "EmbeddingCache":
    """Get or create the embedding cache."""
    global _embedding_cache
    if _embedding_cache is None:
        from frontmatter_mcp.cache import EmbeddingCache

        base = get_base_dir()
        cache_dir_str = os.getenv("FRONTMATTER_CACHE_DIR")
        if cache_dir_str:
            cache_dir = Path(cache_dir_str)
        else:
            cache_dir = base / ".frontmatter-mcp"

        model = get_embedding_model()
        _embedding_cache = EmbeddingCache(
            cache_dir=cache_dir,
            model_name=model.model_name,
            dimension=model.get_dimension(),
        )
    return _embedding_cache


def get_indexer() -> "Indexer":
    """Get or create the indexer."""
    global _indexer
    if _indexer is None:
        from frontmatter_mcp.indexer import Indexer

        base = get_base_dir()
        cache = get_embedding_cache()
        model = get_embedding_model()

        def get_files() -> list[Path]:
            return list(base.rglob("*.md"))

        _indexer = Indexer(cache, model, get_files, base)
    return _indexer


def collect_files(glob_pattern: str) -> list[Path]:
    """Collect files matching the glob pattern."""
    base = get_base_dir()
    pattern = str(base / glob_pattern)
    matches = globmodule.glob(pattern, recursive=True)
    return [Path(p) for p in matches if Path(p).is_file()]


@mcp.tool()
def query_inspect(glob: str) -> dict[str, Any]:
    """Get frontmatter schema from files matching glob pattern.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").

    Returns:
        Dict with file_count, schema (type, count, nullable, sample_values).
    """
    base = get_base_dir()
    paths = collect_files(glob)
    records, warnings = parse_files(paths, base)
    schema = infer_schema(records)

    result: dict[str, Any] = {
        "file_count": len(records),
        "schema": schema,
    }
    if warnings:
        result["warnings"] = warnings

    return result


@mcp.tool()
def query(glob: str, sql: str) -> dict[str, Any]:
    """Query frontmatter with DuckDB SQL.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        sql: SQL query string. Reference 'files' table. Columns are frontmatter
            properties plus 'path'. If semantic search is enabled and indexing
            is complete, you can use embed() function and embedding column.

    Returns:
        Dict with results array, row_count, and columns.
    """
    base = get_base_dir()
    paths = collect_files(glob)
    records, warnings = parse_files(paths, base)

    # Prepare semantic search if enabled and indexing complete
    semantic = None
    if is_semantic_enabled() and _indexer is not None and not _indexer.is_indexing:
        cache = get_embedding_cache()
        model = get_embedding_model()
        semantic = SemanticContext(embeddings=cache.get_all(), model=model)

    query_result = execute_query(records, sql, semantic=semantic)

    result: dict[str, Any] = {
        "results": query_result["results"],
        "row_count": query_result["row_count"],
        "columns": query_result["columns"],
    }
    if warnings:
        result["warnings"] = warnings

    return result


@mcp.tool()
def index_status() -> dict[str, Any]:
    """Get the status of the semantic search index.

    Returns:
        Dict with enabled status. If enabled, also includes indexing state,
        indexed_count, model name, and cache_path.
    """
    if not is_semantic_enabled():
        return {"enabled": False}

    indexer = get_indexer()
    cache = get_embedding_cache()
    model = get_embedding_model()

    return {
        "enabled": True,
        "indexing": indexer.is_indexing,
        "indexed_count": indexer.indexed_count,
        "model": model.model_name,
        "cache_path": str(cache.cache_path),
    }


@mcp.tool()
def index_refresh() -> dict[str, Any]:
    """Refresh the semantic search index (differential update).

    Starts background indexing. On first run, indexes all files.
    Subsequent runs only update files changed since last index (by mtime).

    If indexing is already in progress, returns current status.

    Returns:
        Dict with message and target_count, or error if disabled.

    Notes:
        Call this after editing files during a session to update the index.
    """
    if not is_semantic_enabled():
        return {"error": "Semantic search is disabled"}

    indexer = get_indexer()
    return indexer.start()


@mcp.tool()
def update(
    path: str,
    set: dict[str, Any] | None = None,
    unset: list[str] | None = None,
) -> dict[str, Any]:
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
    base = get_base_dir().resolve()
    abs_path = (base / path).resolve()

    # Security: ensure path is within base_dir
    try:
        abs_path.relative_to(base)
    except ValueError as e:
        raise ValueError(f"Path must be within base directory: {path}") from e

    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return update_file(abs_path, base, set_values=set, unset=unset)


@mcp.tool()
def batch_update(
    glob: str,
    set: dict[str, Any] | None = None,
    unset: list[str] | None = None,
) -> dict[str, Any]:
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
    base = get_base_dir().resolve()
    paths = collect_files(glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        abs_path = file_path.resolve()
        try:
            abs_path.relative_to(base)
        except ValueError:
            warnings.append(f"Skipped (outside base directory): {abs_path}")
            continue

        try:
            update_result = update_file(abs_path, base, set_values=set, unset=unset)
            updated_files.append(update_result["path"])
        except Exception as e:
            rel_path = abs_path.relative_to(base)
            warnings.append(f"Failed to update {rel_path}: {e}")

    response: dict[str, Any] = {
        "updated_count": len(updated_files),
        "updated_files": updated_files,
    }
    if warnings:
        response["warnings"] = warnings

    return response


@mcp.tool()
def batch_array_add(
    glob: str,
    property: str,
    value: Any,
    allow_duplicates: bool = False,
) -> dict[str, Any]:
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

    base = get_base_dir().resolve()
    paths = collect_files(glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        abs_path = file_path.resolve()
        try:
            rel_path = str(abs_path.relative_to(base))
        except ValueError:
            warnings.append(f"Skipped (outside base directory): {abs_path}")
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

    response: dict[str, Any] = {
        "updated_count": len(updated_files),
        "updated_files": updated_files,
    }
    if warnings:
        response["warnings"] = warnings

    return response


@mcp.tool()
def batch_array_remove(
    glob: str,
    property: str,
    value: Any,
) -> dict[str, Any]:
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

    base = get_base_dir().resolve()
    paths = collect_files(glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        abs_path = file_path.resolve()
        try:
            rel_path = str(abs_path.relative_to(base))
        except ValueError:
            warnings.append(f"Skipped (outside base directory): {abs_path}")
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

    response: dict[str, Any] = {
        "updated_count": len(updated_files),
        "updated_files": updated_files,
    }
    if warnings:
        response["warnings"] = warnings

    return response


@mcp.tool()
def batch_array_replace(
    glob: str,
    property: str,
    old_value: Any,
    new_value: Any,
) -> dict[str, Any]:
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

    base = get_base_dir().resolve()
    paths = collect_files(glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        abs_path = file_path.resolve()
        try:
            rel_path = str(abs_path.relative_to(base))
        except ValueError:
            warnings.append(f"Skipped (outside base directory): {abs_path}")
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

    response: dict[str, Any] = {
        "updated_count": len(updated_files),
        "updated_files": updated_files,
    }
    if warnings:
        response["warnings"] = warnings

    return response


@mcp.tool()
def batch_array_sort(
    glob: str,
    property: str,
    reverse: bool = False,
) -> dict[str, Any]:
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

    base = get_base_dir().resolve()
    paths = collect_files(glob)

    updated_files: list[str] = []
    warnings: list[str] = []

    for file_path in paths:
        abs_path = file_path.resolve()
        try:
            rel_path = str(abs_path.relative_to(base))
        except ValueError:
            warnings.append(f"Skipped (outside base directory): {abs_path}")
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

    response: dict[str, Any] = {
        "updated_count": len(updated_files),
        "updated_files": updated_files,
    }
    if warnings:
        response["warnings"] = warnings

    return response


def main() -> None:
    """Entry point for the MCP server."""
    global _base_dir

    # Parse --base-dir argument
    args = sys.argv[1:]
    if "--base-dir" not in args:
        print("Error: --base-dir argument is required", file=sys.stderr)
        print("Usage: frontmatter-mcp --base-dir /path", file=sys.stderr)
        sys.exit(1)

    base_dir_idx = args.index("--base-dir")
    if base_dir_idx + 1 >= len(args):
        print("Error: --base-dir requires a value", file=sys.stderr)
        sys.exit(1)

    base_dir_str = args[base_dir_idx + 1]
    _base_dir = Path(base_dir_str).resolve()

    if not _base_dir.is_dir():
        print(f"Error: Base directory does not exist: {_base_dir}", file=sys.stderr)
        sys.exit(1)

    mcp.run()


if __name__ == "__main__":
    main()
