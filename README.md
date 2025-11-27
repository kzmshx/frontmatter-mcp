# filesystem-frontmatter-mcp

An MCP server for querying Markdown frontmatter with DuckDB SQL.

## Installation

```bash
uv tool install git+https://github.com/kzmshx/filesystem-frontmatter-mcp.git
```

## Configuration

```json
{
  "mcpServers": {
    "frontmatter": {
      "command": "filesystem-frontmatter-mcp",
      "args": ["--base-dir", "/path/to/markdown/directory"]
    }
  }
}
```

## Tools

### inspect_frontmatter

Get schema information from frontmatter across files.

| Parameter | Type | Description |
|-----------|------|-------------|
| `glob` | string | Glob pattern relative to base directory |

**Example:**

Input:

```json
{
  "glob": "**/*.md"
}
```

Output:

```json
{
  "file_count": 186,
  "schema": {
    "date": {
      "type": "string",
      "count": 180,
      "nullable": true,
      "sample_values": ["2025-11-01", "2025-11-02"]
    },
    "tags": {
      "type": "array",
      "count": 150,
      "nullable": true,
      "sample_values": [["ai", "claude"], ["python"]]
    }
  }
}
```

### query_frontmatter

Query frontmatter data with DuckDB SQL.

| Parameter | Type | Description |
|-----------|------|-------------|
| `glob` | string | Glob pattern relative to base directory |
| `sql` | string | DuckDB SQL query referencing `files` table |

**Example 1: Filter by date**

Input:

```json
{
  "glob": "**/*.md",
  "sql": "SELECT path, date, tags FROM files WHERE date LIKE '2025-11-%' ORDER BY date DESC"
}
```

Output:

```json
{
  "columns": ["path", "date", "tags"],
  "row_count": 24,
  "results": [
    {"path": "daily/2025-11-28.md", "date": "2025-11-28", "tags": "[\"journal\"]"},
    {"path": "daily/2025-11-27.md", "date": "2025-11-27", "tags": "[\"journal\"]"}
  ]
}
```

**Example 2: Aggregate tags**

Input:

```json
{
  "glob": "**/*.md",
  "sql": "SELECT tag, COUNT(*) as count FROM files, UNNEST(from_json(tags, '[\"\"]')) AS t(tag) GROUP BY tag ORDER BY count DESC LIMIT 5"
}
```

Output:

```json
{
  "columns": ["tag", "count"],
  "row_count": 5,
  "results": [
    {"tag": "ai", "count": 42},
    {"tag": "python", "count": 35},
    {"tag": "mcp", "count": 18}
  ]
}
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

## License

MIT
