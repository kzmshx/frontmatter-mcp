# 5. Pass all values as strings to DuckDB

Date: 2025-11-28

## Status

Accepted

## Context

frontmatter の値には様々な型（文字列、数値、日付、配列、Templater 式など）が混在する。

当初は Python 側で型推論を行い、適切な DuckDB 型にマッピングしていた。しかし、Obsidian Templater プラグインの式（`<% tp.date.now("YYYY-MM-DD") %>`）が含まれるファイルで問題が発生した:

```
date カラムに "2025-11-01" と "<% tp.date.now(...) %>" が混在
→ 型推論が "date" と判定
→ Templater 式が DATE 型に変換できずエラー
```

## Decision

すべての値を文字列として DuckDB に渡す方式に変更した。

```python
def _serialize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
```

型変換が必要な場合は SQL 側で `TRY_CAST` を使用する。

## Consequences

- 型推論の失敗を回避できる
- すべてのカラムが文字列という一貫した動作になる
- SQL 側で必要に応じて型変換可能
- Templater 式がそのまま文字列として保持され、日付フィルタリングで自然に除外される
- 数値比較などで `TRY_CAST` が必要になる
