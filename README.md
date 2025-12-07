# frontmatter-mcp

An MCP server for querying Markdown frontmatter with DuckDB SQL.

## Configuration

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

To enable semantic search, use the `[semantic]` extras:

```json
{
  "mcpServers": {
    "frontmatter": {
      "command": "uvx",
      "args": ["--from", "frontmatter-mcp[semantic]", "frontmatter-mcp"],
      "env": {
        "FRONTMATTER_BASE_DIR": "/path/to/markdown/directory",
        "FRONTMATTER_ENABLE_SEMANTIC": "true"
      }
    }
  }
}
```

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
    "date": { "type": "string", "count": 180, "nullable": true },
    "tags": { "type": "array", "count": 150, "nullable": true }
  }
}

// Output (with semantic search ready)
{
  "file_count": 186,
  "schema": {
    "date": { "type": "string", "count": 180, "nullable": true },
    "tags": { "type": "array", "count": 150, "nullable": true },
    "embedding": { "type": "FLOAT[256]", "nullable": false }
  }
}
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
{ "path": "notes/idea.md", "frontmatter": {"title": "Idea", "status": "published"} }
```

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

### index_status

Get the status of the semantic search index.

This tool is only available when `FRONTMATTER_ENABLE_SEMANTIC=true`.

**Example:**

```json
// Output (not started)
{ "state": "idle" }

// Output (indexing in progress)
{ "state": "indexing" }

// Output (ready)
{ "state": "ready" }
```

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

### Templater Expression Support

Files containing Obsidian Templater expressions (e.g., `<% tp.date.now("YYYY-MM-DD") %>`) are handled gracefully. These expressions are treated as strings and naturally excluded by date filtering.

### Semantic Search

When semantic search is enabled, you can use the `embed()` function and `embedding` column in SQL queries. After running `index_refresh`, the markdown body content is indexed as vectors.

```sql
-- Find semantically similar documents
SELECT path, 1 - array_cosine_distance(embedding, embed('feeling better')) as score
FROM files
ORDER BY score DESC
LIMIT 10

-- Combine with frontmatter filters
SELECT path, date, 1 - array_cosine_distance(embedding, embed('motivation')) as score
FROM files
WHERE date >= '2025-11-01'
ORDER BY score DESC
LIMIT 10
```

Environment variables:

| Variable                    | Default                               | Description                    |
| --------------------------- | ------------------------------------- | ------------------------------ |
| FRONTMATTER_BASE_DIR        | (required)                            | Base directory for files       |
| FRONTMATTER_ENABLE_SEMANTIC | false                                 | Enable semantic search         |
| FRONTMATTER_EMBEDDING_MODEL | cl-nagoya/ruri-v3-30m                 | Embedding model name           |
| FRONTMATTER_CACHE_DIR       | FRONTMATTER_BASE_DIR/.frontmatter-mcp | Cache directory for embeddings |

## License

MIT
