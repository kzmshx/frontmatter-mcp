# 11. Decouple semantic search as optional package

Date: 2025-12-05

## Status

Accepted

## Context

Semantic search requires heavy dependencies (sentence-transformers, torch) that significantly increase installation size and startup time. Users who only need frontmatter queries should not pay this cost.

Design goals:

- Core functionality works without semantic dependencies
- `query.py` should not import semantic modules
- Clear separation between core and semantic code
- Easy to enable semantic search when needed

## Decision

Organized semantic search code into a separate `semantic/` package with loose coupling to core modules.

Directory structure:

```text
src/frontmatter_mcp/
├── query.py              # Core query execution (no semantic imports)
├── server.py             # Tool definitions
├── context.py            # Singleton management for optional components
├── settings.py           # pydantic-settings configuration
└── semantic/
    ├── __init__.py
    ├── model.py          # EmbeddingModel class
    ├── cache.py          # EmbeddingCache class
    ├── indexer.py        # EmbeddingIndexer class
    └── query.py          # SemanticContext, setup_semantic_search
```

Key design patterns:

1. **Callback injection**: `execute_query()` accepts `conn_setup: Callable` instead of `SemanticContext`, removing the import dependency
2. **Conditional tool registration**: `@mcp.tool(enabled=False)` with `.enable()` at runtime
3. **Optional dependencies**: `sentence-transformers` in `[project.optional-dependencies]`, installed via `uvx --with`

## Consequences

Benefits:

- Core package installs quickly without ML dependencies
- `query.py` has no knowledge of semantic search implementation
- Future extensions (different vector DBs, embedding APIs) can use the same callback pattern
- Tests can run without loading the embedding model

Trade-offs:

- Slightly more complex wiring in `server.py` to connect components
- Users must manually specify `--with sentence-transformers` for uvx
- Two separate test directories (`tests/` and `tests/semantic/`)
