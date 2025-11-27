# 4. Use PyArrow for data passing

Date: 2025-11-28

## Status

Accepted

## Context

Python の dict リストを DuckDB に効率的に渡す方法を検討した。

## Decision

PyArrow テーブルを経由して DuckDB に登録する方式を採用した。

```python
schema = pa.schema([(key, pa.string()) for key in all_keys])
table = pa.table(columns_data, schema=schema)
conn.register("files", table)
```

## Consequences

- `pa.schema()` でカラムの型を明示的に指定できる
- Arrow 形式は列指向でメモリ効率が良い
- DuckDB は Arrow 形式をネイティブにサポートしており、変換コストが低い
- pyarrow への依存が追加された
