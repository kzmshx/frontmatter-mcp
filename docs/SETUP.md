# SETUP

## Development Environment

### Install Dependencies

```bash
uv sync
```

### Serena MCP Setup

Serena is an MCP server for code analysis. Project settings are in `.serena/`.

Run in project root:

```bash
claude mcp add serena -s local -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context ide-assistant --project $(pwd)
```

## Commands

| Command     | Description              |
| ----------- | ------------------------ |
| `make lint` | Run linter               |
| `make fix`  | Auto-fix lint issues     |
| `make test` | Run tests                |
| `make help` | Show available commands  |

## Running the MCP Server

```bash
uv run frontmatter-mcp --base-dir /path/to/markdown
```
