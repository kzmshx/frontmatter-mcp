"""MCP Server implementation using FastMCP."""

import glob as globmodule
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from filesystem_frontmatter_mcp.parser import infer_schema, parse_files
from filesystem_frontmatter_mcp.query import execute_query

# Global base directory
_base_dir: Path | None = None

mcp = FastMCP("filesystem-frontmatter-mcp")


def get_base_dir() -> Path:
    """Get the configured base directory."""
    if _base_dir is None:
        raise RuntimeError("Base directory not configured. Use --base-dir argument.")
    return _base_dir


def collect_files(glob_pattern: str) -> list[Path]:
    """Collect files matching the glob pattern."""
    base = get_base_dir()
    pattern = str(base / glob_pattern)
    matches = globmodule.glob(pattern, recursive=True)
    return [Path(p) for p in matches if Path(p).is_file()]


@mcp.tool()
def inspect_frontmatter(glob: str) -> str:
    """Get frontmatter schema from files matching glob pattern.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").

    Returns:
        JSON with file_count, schema (type, count, nullable, sample_values).
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

    return json.dumps(result, default=str)


@mcp.tool()
def query_frontmatter(glob: str, sql: str) -> str:
    """Query frontmatter with DuckDB SQL.

    Args:
        glob: Glob pattern relative to base directory (e.g. "atoms/**/*.md").
        sql: SQL query string. Reference 'files' table. Columns are frontmatter
            properties plus 'path'.

    Returns:
        JSON with results array, row_count, and columns.
    """
    base = get_base_dir()
    paths = collect_files(glob)
    records, warnings = parse_files(paths, base)
    query_result = execute_query(records, sql)

    result: dict[str, Any] = {
        "results": query_result["results"],
        "row_count": query_result["row_count"],
        "columns": query_result["columns"],
    }
    if warnings:
        result["warnings"] = warnings

    return json.dumps(result, default=str)


def main() -> None:
    """Entry point for the MCP server."""
    global _base_dir

    # Parse --base-dir argument
    args = sys.argv[1:]
    if "--base-dir" not in args:
        print("Error: --base-dir argument is required", file=sys.stderr)
        print("Usage: filesystem-frontmatter-mcp --base-dir /path", file=sys.stderr)
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
