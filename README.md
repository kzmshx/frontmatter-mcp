# frontmatter-mcp

An MCP server for querying Markdown frontmatter with DuckDB SQL.

## Configuration

### Basic Usage

```json
{
  "mcpServers": {
    "frontmatter": {
      "command": "uvx",
      "args": ["frontmatter-mcp"],
      "env": {
        "FRONTMATTER_BASE_DIR": "/path/to/markdown/directory"
      }
    }
  }
}
```

### With Semantic Search

Semantic search requires large dependencies (~1GB). Set `MCP_TIMEOUT` to extend installation timeout:

```json
{
  "mcpServers": {
    "frontmatter": {
      "command": "uvx",
      "args": ["--from", "frontmatter-mcp[semantic]", "frontmatter-mcp"],
      "env": {
        "FRONTMATTER_BASE_DIR": "/path/to/markdown/directory",
        "FRONTMATTER_ENABLE_SEMANTIC": "true",
        "MCP_TIMEOUT": "300000"
      }
    }
  }
}
```

Note: `MCP_TIMEOUT` is in milliseconds (300000 = 5 minutes).

## Installation (Optional)

If you prefer to install globally:

```bash
pip install frontmatter-mcp
# or
uv tool install frontmatter-mcp
```

## Tools

### query_inspect

Get schema information from frontmatter across files.

| Parameter | Type   | Description                             |
| --------- | ------ | --------------------------------------- |
| `glob`    | string | Glob pattern relative to base directory |

**Example:**

```json
// Input
{ "glob": "**/*.md" }

// Output
{
  "file_count": 186,
  "schema": {
    "path": { "type": "string", "nullable": false, "examples": ["notes/a.md"] },
    "date": { "type": "string", "nullable": true, "examples": ["2025-11-28"] },
    "tags": { "type": "array", "nullable": true, "examples": [["python", "mcp"]] }
  }
}

// With semantic search ready, the schema also has
//   "embedding": { "type": "FLOAT[256]", "nullable": true }
// (NULL for files without indexed text)
```

### query

Query frontmatter data with DuckDB SQL.

| Parameter | Type   | Description                                |
| --------- | ------ | ------------------------------------------ |
| `glob`    | string | Glob pattern relative to base directory    |
| `sql`     | string | DuckDB SQL query referencing `files` table |

**Example:**

```json
// Input
{
  "glob": "**/*.md",
  "sql": "SELECT path, date FROM files WHERE date >= '2025-11-01' ORDER BY date DESC"
}

// Output
{
  "columns": ["path", "date"],
  "row_count": 24,
  "results": [
    {"path": "daily/2025-11-28.md", "date": "2025-11-28"},
    {"path": "daily/2025-11-27.md", "date": "2025-11-27"}
  ]
}
```

### update

Update frontmatter properties in a single file.

| Parameter | Type     | Description                          |
| --------- | -------- | ------------------------------------ |
| `path`    | string   | File path relative to base directory |
| `set`     | object   | Properties to add or overwrite       |
| `unset`   | string[] | Property names to remove             |

**Example:**

```json
// Input
{ "path": "notes/idea.md", "set": {"status": "published"} }

// Output
{
  "path": "notes/idea.md",
  "frontmatter": {"title": "Idea", "status": "published"},
  "updated": true
}
```

`updated` is false when the values were already as requested; the file is then not written.

### batch_update

Update frontmatter properties in multiple files.

| Parameter | Type     | Description                             |
| --------- | -------- | --------------------------------------- |
| `glob`    | string   | Glob pattern relative to base directory |
| `set`     | object   | Properties to add or overwrite          |
| `unset`   | string[] | Property names to remove                |

**Example:**

```json
// Input
{ "glob": "drafts/*.md", "set": {"status": "review"} }

// Output
{ "updated_count": 5, "updated_files": ["drafts/a.md", "drafts/b.md", ...] }
```

Files whose values are already as requested are not written and not listed.

### batch_array_add

Add a value to an array property in multiple files.

| Parameter          | Type   | Description                             |
| ------------------ | ------ | --------------------------------------- |
| `glob`             | string | Glob pattern relative to base directory |
| `property`         | string | Name of the array property              |
| `value`            | any    | Value to add                            |
| `allow_duplicates` | bool   | Allow duplicate values (default: false) |

**Example:**

```json
// Input
{ "glob": "**/*.md", "property": "tags", "value": "reviewed" }

// Output
{ "updated_count": 42, "updated_files": ["a.md", "b.md", ...] }
```

### batch_array_remove

Remove a value from an array property in multiple files.

| Parameter  | Type   | Description                             |
| ---------- | ------ | --------------------------------------- |
| `glob`     | string | Glob pattern relative to base directory |
| `property` | string | Name of the array property              |
| `value`    | any    | Value to remove                         |

**Example:**

```json
// Input
{ "glob": "**/*.md", "property": "tags", "value": "draft" }

// Output
{ "updated_count": 15, "updated_files": ["a.md", "b.md", ...] }
```

### batch_array_replace

Replace a value in an array property in multiple files.

| Parameter   | Type   | Description                             |
| ----------- | ------ | --------------------------------------- |
| `glob`      | string | Glob pattern relative to base directory |
| `property`  | string | Name of the array property              |
| `old_value` | any    | Value to replace                        |
| `new_value` | any    | New value                               |

**Example:**

```json
// Input
{ "glob": "**/*.md", "property": "tags", "old_value": "draft", "new_value": "review" }

// Output
{ "updated_count": 10, "updated_files": ["a.md", "b.md", ...] }
```

### batch_array_sort

Sort an array property in multiple files.

| Parameter  | Type   | Description                               |
| ---------- | ------ | ----------------------------------------- |
| `glob`     | string | Glob pattern relative to base directory   |
| `property` | string | Name of the array property                |
| `reverse`  | bool   | Sort in descending order (default: false) |

**Example:**

```json
// Input
{ "glob": "**/*.md", "property": "tags" }

// Output
{ "updated_count": 20, "updated_files": ["a.md", "b.md", ...] }
```

### batch_array_unique

Remove duplicate values from an array property in multiple files.

| Parameter  | Type   | Description                             |
| ---------- | ------ | --------------------------------------- |
| `glob`     | string | Glob pattern relative to base directory |
| `property` | string | Name of the array property              |

**Example:**

```json
// Input
{ "glob": "**/*.md", "property": "tags" }

// Output
{ "updated_count": 5, "updated_files": ["a.md", "b.md", ...] }
```

### search

Search document text and return the best-matching passage of each document. Finds paraphrases as well as exact names.

This tool is only available when `FRONTMATTER_ENABLE_SEMANTIC=true`.

| Parameter | Type   | Description                                                       |
| --------- | ------ | ----------------------------------------------------------------- |
| `query`   | string | What to look for, as a sentence or keywords                       |
| `glob`    | string | Glob pattern to search within (default `**/*.md`)                 |
| `where`   | string | Optional SQL condition on frontmatter, same columns as `query`    |
| `limit`   | number | Maximum documents to return, 1-50 (default 10)                    |
| `exclude_sections` | string[] | Headings whose passages are skipped, at any level (optional) |

**Example:**

```json
// Input
{ "query": "felt lonely on my birthday", "where": "date < '2025-11-01'", "limit": 5 }

// Output
{
  "results": [
    {
      "path": "daily/2025-10-15.md",
      "line": 42,
      "heading": "Timeline",
      "section": ["Daily", "Timeline"],
      "text": "Timeline\n- 20:48 Nobody around on my birthday ...",
      "score": 0.9312
    }
  ],
  "index": { "state": "ready", "has_index": true, "last_run": { "indexed": 1903, "removed": 0, "failed": 0, "error": null } }
}
```

`line` is where the passage starts in the file. `section` is the heading path from the top level down to `heading`, so a passage under a recurring section (for example comments added to each note by a tool) can be told apart; `exclude_sections` leaves such sections out of the search. Scores are only comparable within one search.

### index_status

Get the status of the semantic search index.

This tool is only available when `FRONTMATTER_ENABLE_SEMANTIC=true`.

**Example:**

```json
// Output (not started in this session; the first search starts it)
{ "state": "idle", "has_index": false, "last_run": null }

// Output (after a run)
{
  "state": "ready",
  "has_index": true,
  "last_run": { "indexed": 12, "removed": 0, "failed": 0, "error": null }
}
```

`has_index` stays true while a later refresh runs (the previous index is served). `last_run.error` says why a run stopped early (for example, the model could not be downloaded).

### index_wait

Wait until a running indexing run finishes (or the timeout passes).

This tool is only available when `FRONTMATTER_ENABLE_SEMANTIC=true`.

| Parameter | Type   | Description                        |
| --------- | ------ | ---------------------------------- |
| `timeout` | number | Maximum seconds to wait (default 60) |

**Example:**

```json
// Output
{ "success": true, "state": "ready", "has_index": true, "last_run": { "indexed": 3, "removed": 0, "failed": 0, "error": null } }
```

`success` is false when the timeout passed while indexing was still running.

### index_refresh

Refresh the semantic search index (differential update).

This tool is only available when `FRONTMATTER_ENABLE_SEMANTIC=true`.

**Example:**

```json
// Output
{ "state": "indexing", "message": "Indexing started", "target_count": 665 }

// Output (when already indexing)
{ "state": "indexing", "message": "Indexing already in progress" }
```

## Technical Notes

### Warnings

Tools that read or write many files report per-file problems instead of failing: `"warnings": [{ "path": "notes/a.md", "error": "..." }]` (malformed frontmatter, a property that is not an array, a frontmatter key named `path`, which is reserved for the file path). SQL errors fail the call and list the columns of the `files` table.

### Array Operations

`batch_array_remove` and `batch_array_replace` act on every occurrence of the value. `batch_array_sort` skips (with a warning) arrays whose values can't be compared.

### All Values Are Strings

All frontmatter values are passed to DuckDB as strings. Use `TRY_CAST` in SQL for type conversion when needed.

```sql
SELECT * FROM files
WHERE TRY_CAST(date AS DATE) >= '2025-11-01'
```

### Arrays Are JSON Strings

Arrays like `tags: [ai, python]` are stored as JSON strings `'["ai", "python"]'`. Use `from_json()` and `UNNEST` to expand them.

```sql
SELECT path, tag
FROM files, UNNEST(from_json(tags, '[""]')) AS t(tag)
WHERE tag = 'ai'
```

### Writes Keep the File's Formatting

The update tools rewrite only the frontmatter keys whose values change. Other keys, comments, quotes, line wrapping, and the body stay byte for byte. A replaced list keeps its style (`tags: [a, b]` stays inline, block lists keep their indentation), and a new list follows the style already used in the file. Files are written atomically, so a failed write never leaves a partial file.

### Templater Expression Support

Files containing Obsidian Templater expressions (e.g., `<% tp.date.now("YYYY-MM-DD") %>`) are handled gracefully. These expressions are treated as strings and naturally excluded by date filtering.

### Semantic Search

Each file's body is split into chunks of about 400 characters at headings and line breaks, and each chunk is embedded. Chunks with under 20 characters of text once links, embeds, URLs and list markers are removed are not indexed. A chunk whose text, ignoring checkbox state, numbers and whitespace, appears in 10 or more documents is template text (a daily checklist, for example) and is never returned by `search`. Indexing starts on the first semantic call (`search`, a `query` using `embed()`, or `index_refresh`), not at server startup, and only re-reads files whose mtime changed. Dot directories such as `.obsidian` are skipped.

The `search` tool combines three signals:

1. Dense: cosine similarity of query and chunk embeddings. With ruri-v3 models the recommended prefixes (`検索クエリ: ` / `検索文書: `) are applied
2. Lexical: BM25 over character bigrams, which needs no Japanese tokenizer and catches exact names and phrases
3. Rerank: a cross-encoder scores the best chunks of the top candidates from 1 and 2. With the reranker turned off, 1 and 2 are combined by weighted reciprocal rank fusion

On a 1,900-file Japanese vault with 16 queries that each have one known target document, the target ranked first for 2 queries with the previous whole-document embeddings and 13 with this pipeline (top 5: 6 and 15). Reranking adds about 0.3 seconds per query.

SQL access is still available: `embedding` is the normalized mean of a document's chunk vectors, and `embed()` encodes a query.

```sql
SELECT path, array_cosine_similarity(embedding, embed('feeling better')) AS score
FROM files
WHERE embedding IS NOT NULL AND date >= '2025-11-01'
ORDER BY score DESC
LIMIT 10
```

Environment variables:

| Variable                              | Default                                 | Description                                         |
| ------------------------------------- | --------------------------------------- | --------------------------------------------------- |
| FRONTMATTER_BASE_DIR                  | (required)                              | Base directory for files                            |
| FRONTMATTER_ENABLE_SEMANTIC           | false                                   | Enable semantic search                              |
| FRONTMATTER_EMBEDDING_MODEL           | cl-nagoya/ruri-v3-30m                   | Embedding model name                                |
| FRONTMATTER_EMBEDDING_QUERY_PREFIX    | model default (`検索クエリ: ` for ruri-v3) | Prefix added to queries                             |
| FRONTMATTER_EMBEDDING_DOCUMENT_PREFIX | model default (`検索文書: ` for ruri-v3)   | Prefix added to indexed chunks                      |
| FRONTMATTER_RERANKER_MODEL            | hotchpotch/japanese-reranker-xsmall-v2  | Cross-encoder for `search`; empty string turns it off |
| FRONTMATTER_CACHE_DIR                 | FRONTMATTER_BASE_DIR/.frontmatter-mcp   | Cache directory for embeddings                      |

Changing the model or the document prefix, or upgrading from a version before chunked indexing, rebuilds the cache on the next start.

Resource use, measured on a 1,900-file vault (27,700 chunks) on an M-series Mac:

| | |
| :- | :- |
| Server memory before any semantic call | about 110 MB (torch and the models are loaded on first use) |
| Memory after the first search | about 1.1 GB (torch, both models, vectors, BM25 index) |
| First full index | about 90 s; later runs only re-index changed files (300 files: about 15 s) |
| One search | about 0.4 s (retrieval about 10 ms, rerank about 0.3 s); the first search also loads the models (a few seconds) |
| Cache file | about 35 MB; rewritten after indexing once it grows 25% (and 8 MB) past its compact size |
| Model downloads (Hugging Face cache) | about 150 MB each for the embedding model and the reranker |

## License

MIT
