# 6. JSON encode arrays

Date: 2025-11-28

## Status

Accepted

## Context

frontmatter の配列（`tags: [ai, python]`）を DuckDB でどう扱うか検討した。

ADR-0005 で全値を文字列として扱う方針を決定したため、配列も何らかの文字列表現が必要だった。

## Decision

配列は JSON 文字列としてエンコードし、SQL 側で `from_json()` と `UNNEST` を使用して展開する。

```python
# Python 側
if isinstance(value, list):
    return json.dumps(value, ensure_ascii=False)
```

```sql
-- SQL 側での展開
SELECT path, tag
FROM files, UNNEST(from_json(tags, '[""]')) AS t(tag)
```

## Consequences

- ADR-0005 の全値文字列方針と一貫性がある
- 全カラムが文字列型で統一される
- DuckDB の `from_json()` 関数で動的に配列に変換可能
- `from_json()` の第二引数にはスキーマヒント（`'[""]'`）が必要
