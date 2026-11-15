# 13. Organize modules by responsibility

Date: 2026-11-16

## Status

Accepted

Amends [11. Decouple semantic search as optional package](0011-decouple-semantic-search-as-optional-package.md)

## Context

By 0.5.x, `server.py` held every tool, path helpers, response building and `main()` (about 770 lines); the six batch tools repeated the same per-file loop; `files.py` mixed reading frontmatter with round-trip writing; three places listed files with different rules; and the semantic package kept names from the whole-document design (`EmbeddingCache` storing chunks, `EmbeddingIndexer`). Dependency wiring had two singleton layers that tests had to reset separately.

## Decision

```text
src/frontmatter_mcp/
├── app.py            # FastMCP instance, tool annotations, semantic tag
├── server.py         # imports the tools (registration), main()
├── dependencies.py   # AppState (settings, record cache, semantic context) for Depends
├── settings.py       # FRONTMATTER_* environment variables (env_prefix)
├── paths.py          # collect_files, list_markdown_files, resolve_file
├── markdown.py       # split_frontmatter (shared by writer and chunking)
├── records.py        # FileRecordCache, parse_file(s); "path" is reserved
├── writer.py         # read_metadata, apply_update, render, write_metadata
├── array_ops.py      # pure list operations for batch_array_*
├── sql.py            # files table, sandboxed execute_query
├── schema.py         # infer_schema for query_inspect
├── tools/
│   ├── results.py    # TypedDict results (published as output schemas)
│   ├── query.py      # query_inspect, query
│   ├── write.py      # update, batch_update, batch_array_*
│   └── search.py     # search, index_status, index_wait, index_refresh
└── semantic/
    ├── chunking.py   # Markdown → chunks
    ├── models.py     # EmbeddingModel, Reranker (lazy, locked loading)
    ├── store.py      # ChunkStore: DuckDB tables indexed_files, chunks, metadata
    ├── indexer.py    # ChunkIndexer, IndexRunStats
    ├── search.py     # SearchIndex, Bm25Index
    ├── context.py    # SemanticContext facade, create_semantic_context
    └── sql.py        # add_semantic_columns, add_semantic_schema
```

- Tool modules register on `app.mcp`; `server.py` re-exports the tool functions, so `frontmatter_mcp.server.query` and the entry point keep working
- The write tools share one loop (`_update_files`) and differ only in a metadata transform; files are written only when their text changes
- Tools raise `ToolError` for client mistakes (path outside the base directory, SQL errors with the available columns, semantic search disabled)
- Tool names, parameters and environment variables are unchanged. Result shapes change in three places: warnings are always `{path, error}`, `update` adds `updated`, `search` reports `index` instead of `index_state`

## Consequences

- Each module has one reason to change, and the array operations and frontmatter rendering are tested without files or MCP
- The store schema version is 3 (tables renamed); caches from 0.6 pre-releases are rebuilt
- Code importing `frontmatter_mcp.files`, `frontmatter_mcp.query`, `frontmatter_mcp.query_schema` or the old semantic class names must update its imports
