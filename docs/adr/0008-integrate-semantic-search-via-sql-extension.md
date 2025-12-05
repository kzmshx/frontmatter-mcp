# 8. Integrate semantic search via SQL extension

Date: 2025-12-05

## Status

Accepted

## Context

When adding semantic search capability to frontmatter-mcp, we needed to decide how users would interact with the feature.

Two main approaches were considered:

1. **Dedicated tool**: Create a new `semantic_search(query, limit)` tool
2. **SQL extension**: Extend the existing `query()` tool with `embed()` function and `embedding` column

## Decision

Adopted the SQL extension approach. The existing `query()` tool is extended with:

- `embed()` UDF registered in DuckDB for text-to-vector conversion
- `embedding` column added to the `files` table via JOIN
- DuckDB's built-in `array_cosine_distance()` for similarity calculation

Example usage:

```sql
SELECT path, date, 1 - array_cosine_distance(embedding, embed('recovered from illness')) as score
FROM files
WHERE date >= '2025-11-01'
ORDER BY score DESC
LIMIT 10
```

## Consequences

Benefits:

- Users can naturally combine frontmatter filtering with semantic search in a single SQL query
- No new tool to learn; leverages existing SQL knowledge
- Full flexibility of SQL (GROUP BY, JOIN, subqueries) available for semantic queries

Trade-offs:

- Slightly more complex queries compared to a simple `semantic_search(query)` call
- Users need to understand `embed()` function and cosine distance calculation
- Error messages for semantic search issues appear as SQL errors
