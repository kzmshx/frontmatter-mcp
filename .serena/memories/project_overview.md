# Project Overview

## Purpose

frontmatter-mcp is an MCP (Model Context Protocol) server for querying and manipulating Markdown frontmatter using DuckDB SQL.

## Tech Stack

- Python 3.11+
- sentence-transformers, scikit-learn, scipy (optional `semantic` extra)
- FastMCP (MCP server framework)
- DuckDB (SQL query engine)
- python-frontmatter (YAML frontmatter parsing)
- pyarrow (data interchange)
- Hatchling (build backend)
- Ruff (linting/formatting)
- pytest (testing)
- uv (package manager)

## Codebase Structure

See docs/adr/0013-organize-modules-by-responsibility.md for the module layout:
`app.py` (FastMCP instance), `server.py` (registration, main), `tools/` (query,
write, search tools), core modules (`paths`, `markdown`, `records`, `writer`,
`array_ops`, `sql`, `schema`, `settings`, `dependencies`) and `semantic/`
(chunking, models, store, indexer, search, context, sql).

Tests mirror the source layout: `tests/test_*.py`, `tests/tools/`,
`tests/semantic/`, `tests/benchmarks/` (run in CI with --benchmark-disable).
Shared fixtures and fakes are in `tests/conftest.py`.

## Available Tools

| Tool | Description |
|------|-------------|
| query_inspect | Get schema from frontmatter |
| query | SQL query with DuckDB |
| update | Update single file |
| batch_update | Update multiple files |
| batch_array_add | Add value to array property |
| batch_array_remove | Remove value from array property |
| batch_array_replace | Replace value in array property |
| batch_array_sort | Sort array property |
| batch_array_unique | Remove duplicate values from array property |
| search | Hybrid search over document text (semantic extra) |
| index_status / index_wait / index_refresh | Semantic index state and refresh (semantic extra) |
