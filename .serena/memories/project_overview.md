# Project Overview

## Purpose

frontmatter-mcp is an MCP (Model Context Protocol) server for querying and manipulating Markdown frontmatter using DuckDB SQL.

## Tech Stack

- Python 3.11+
- FastMCP (MCP server framework)
- DuckDB (SQL query engine)
- python-frontmatter (YAML frontmatter parsing)
- pyarrow (data interchange)
- Hatchling (build backend)
- Ruff (linting/formatting)
- pytest (testing)
- uv (package manager)

## Codebase Structure

```
src/frontmatter_mcp/
  __init__.py
  server.py       # Main MCP server and tool definitions
  frontmatter.py  # Frontmatter parsing utilities
  query.py        # DuckDB query execution
  schema.py       # Schema inspection

tests/
  test_server.py  # Integration tests

docs/
  workspace/      # Branch-specific work documents (gitignored)
  adr/            # Architecture Decision Records
```

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
