# 3. Use DuckDB for SQL queries

Date: 2025-11-28

## Status

Accepted

## Context

frontmatter データに対してフィルタリング・集計を行う方法を検討した。

候補:
- pandas: SQL よりも学習コストが高い、MCP クライアント側での利用が困難
- SQLite: 配列操作が弱い、JSON 関数のサポートが限定的
- jq 風の DSL: 実装コストが高い、学習コストも発生
- DuckDB: SQL の表現力、配列操作、インメモリ実行

## Decision

DuckDB をインメモリ SQL エンジンとして採用した。

## Consequences

- WHERE、GROUP BY、JOIN など複雑なクエリが可能
- `UNNEST`、`from_json()` による配列展開が容易
- インメモリ実行で高速
- サーバープロセス不要、Python ライブラリとして組み込み可能
- DuckDB の SQL 方言に依存する
