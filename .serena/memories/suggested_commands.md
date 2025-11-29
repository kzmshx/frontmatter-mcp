# Suggested Commands

## Development

```bash
# Install dependencies
uv sync

# Run the MCP server
uv run frontmatter-mcp --base-dir /path/to/markdown

# Run tests
make test
# or
uv run pytest tests -v

# Lint
make lint
# or
uv run ruff check src tests
uv run ruff format --check src tests

# Auto-fix lint issues
make fix
# or
uv run ruff check --fix src tests
uv run ruff format src tests
```

## Build & Publish

```bash
# Build package
uv build

# Publish to PyPI
uv publish
```

## Git

```bash
# Branch naming: {type}/{description}
# Types: feat, fix, docs, style, refactor, test, chore

# Example
git checkout -b feat/new-feature
```

## ADR (Architecture Decision Records)

```bash
adr new <title>
adr list
adr new -s <number> <title>  # Supersede existing ADR
```
