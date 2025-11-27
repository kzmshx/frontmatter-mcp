# 7. Use relative paths from base directory

Date: 2025-11-28

## Status

Accepted

## Context

クエリ結果のファイルパスをどう表現するか検討した。

候補:
- 絶対パス: `/Users/kzmshx/Documents/Obsidian/atoms/daily/2025-11-01.md`
- 相対パス: `daily/2025-11-01.md`

## Decision

`--base-dir` からの相対パスを使用する。

```python
result["path"] = str(path.relative_to(base_dir))
```

## Consequences

- 環境に依存しない可搬性のあるパス表現
- 不要なプレフィックスが除去され、出力が簡潔
- base-dir 外のパスが結果に含まれない
- 絶対パスが必要な場合はクライアント側で base-dir と結合する必要がある
