# SETUP

## Development Environment

### Install Dependencies

```bash
uv sync
```

The dev group includes the project with its `semantic` extra, so every test can run. CI also tests a plain `uv sync --no-dev` install (no extras).

### Serena MCP Setup

Serena is an MCP server for code analysis. Project settings are in `.serena/`.

Run in project root:

```bash
claude mcp add serena -s local -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context ide-assistant --project $(pwd)
```

## Commands

| Command          | Description                                   |
| ---------------- | --------------------------------------------- |
| `make lint`      | Run linter                                    |
| `make fix`       | Auto-fix lint issues                          |
| `make test`      | Run tests (benchmarks excluded)               |
| `make test-fast` | Run tests except the slow (real model) ones   |
| `make test-bench`| Run benchmarks                                |
| `make typecheck` | Run type checker                              |
| `make help`      | Show available commands                       |

## Running the MCP Server

Configuration comes from environment variables (see README):

```bash
FRONTMATTER_BASE_DIR=/path/to/markdown uv run frontmatter-mcp
```
