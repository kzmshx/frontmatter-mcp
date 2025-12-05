# 10. Store embedding cache under base directory

Date: 2025-12-05

## Status

Accepted

## Context

Semantic search requires persistent storage for embedding vectors to avoid regenerating them on every startup.

Options considered for cache location:

| Option | Example Path | Pros | Cons |
|--------|--------------|------|------|
| XDG cache | `~/.cache/frontmatter-mcp/` | Standard on Linux | Platform-specific paths needed |
| platformdirs | Varies by OS | Cross-platform | Additional dependency |
| Base directory | `{base_dir}/.frontmatter-mcp/` | Simple, portable | Stored with user data |

Platform-specific cache paths:

- Linux: `~/.cache/`
- macOS: `~/Library/Caches/`
- Windows: `AppData/Local/`

## Decision

Store embedding cache under the base directory: `{FRONTMATTER_BASE_DIR}/.frontmatter-mcp/embeddings.duckdb`

Override is available via `FRONTMATTER_CACHE_DIR` environment variable.

## Consequences

Benefits:

- Cache is isolated per vault/project (each base directory gets its own cache)
- No platform-specific logic needed
- Cache travels with the data when moving directories
- No additional dependencies (no platformdirs)

Trade-offs:

- Hidden directory (`.frontmatter-mcp/`) is stored alongside user content
- Backup tools may include cache files unless excluded
- Cache is not shared between different base directories (intentional)
