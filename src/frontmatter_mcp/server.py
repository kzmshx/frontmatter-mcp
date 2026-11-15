"""MCP server entry point: registers the tools and runs the server."""

import argparse
import importlib.metadata
import importlib.util
import sys

from frontmatter_mcp.app import SEMANTIC_TAG, mcp
from frontmatter_mcp.dependencies import get_settings

# Importing the tool modules registers their tools
from frontmatter_mcp.tools.query import query, query_inspect
from frontmatter_mcp.tools.search import (
    index_refresh,
    index_status,
    index_wait,
    search,
)
from frontmatter_mcp.tools.write import (
    batch_array_add,
    batch_array_remove,
    batch_array_replace,
    batch_array_sort,
    batch_array_unique,
    batch_update,
    update,
)

__all__ = [
    "batch_array_add",
    "batch_array_remove",
    "batch_array_replace",
    "batch_array_sort",
    "batch_array_unique",
    "batch_update",
    "index_refresh",
    "index_status",
    "index_wait",
    "main",
    "mcp",
    "query",
    "query_inspect",
    "search",
    "update",
]

# Semantic search tools stay hidden unless semantic search is enabled in main()
mcp.disable(tags={SEMANTIC_TAG})

SEMANTIC_PACKAGES = ("sentence_transformers", "sklearn", "scipy")


def _missing_semantic_packages() -> list[str]:
    return [p for p in SEMANTIC_PACKAGES if importlib.util.find_spec(p) is None]


def _parse_args(argv: list[str] | None) -> None:
    """Handle --version and --help; the server itself takes no arguments.

    Runs before settings are read, so both work without FRONTMATTER_BASE_DIR.
    """
    parser = argparse.ArgumentParser(
        prog="frontmatter-mcp",
        description=(
            "MCP server for querying and updating Markdown frontmatter. "
            "Configured through FRONTMATTER_* environment variables; "
            "FRONTMATTER_BASE_DIR is required."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {importlib.metadata.version('frontmatter-mcp')}",
    )
    parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the MCP server."""
    _parse_args(argv)
    settings = get_settings()

    if settings.enable_semantic:
        if missing := _missing_semantic_packages():
            # Keep serving the other tools; say why search is not available
            print(
                "frontmatter-mcp: FRONTMATTER_ENABLE_SEMANTIC is set but "
                f"{', '.join(missing)} is not installed; semantic tools are "
                "disabled. Install frontmatter-mcp[semantic].",
                file=sys.stderr,
            )
        else:
            # Indexing starts on the first semantic call, not here, so sessions
            # that never search don't load the model
            mcp.enable(tags={SEMANTIC_TAG})

    mcp.run()


if __name__ == "__main__":
    main()
