# PLAN

## 概要

frontmatter-mcp にセマンティック検索機能を追加する。ローカル Embedding モデル（ruri-v3-30m）と DuckDB VSS 拡張を使用し、Markdown 本文の意味的検索を可能にする。

## 背景

現状の frontmatter-mcp は frontmatter のクエリに特化しており、本文の検索は Grep に依存している。キーワードベースの検索では「体調が回復した日」のような意味的な検索ができない。

## ゴール

- クエリに意味的に近いドキュメントを検索できる
- 環境変数で機能のオン/オフを切り替えられる
- Embedding はローカルで完結し、API コストゼロ
- インデックスは永続化し、差分更新で起動時間を最小化

## 技術選定

| 要素             | 選定                  | 理由                                    |
| ---------------- | --------------------- | --------------------------------------- |
| Embedding モデル | cl-nagoya/ruri-v3-30m | 日本語特化、軽量（30M）、JMTEB 高スコア |
| ベクトル検索     | DuckDB VSS 拡張       | 既存 DuckDB 基盤を活用、SQL で検索可能  |
| キャッシュ       | DuckDB ファイル永続化 | 差分更新可能、シンプル                  |

## 設計方針

既存の `query()` を拡張し、SQL 内でセマンティック検索を可能にする。

### 拡張ポイント

1. `embed()` 関数を DuckDB に登録（テキスト → ベクトル変換）
2. `embedding` カラムを files テーブルに追加
3. DuckDB 組み込みの `array_cosine_distance()` でベクトル検索

### 本文の取得

python-frontmatter の `post.content` で本文を取得する。

```python
post = frontmatter.load(path)
content = post.content  # frontmatter 以降の本文
```

### embed() 関数の登録

次元数はモデルから自動取得する。

```python
from duckdb.typing import VARCHAR
import numpy as np

model = SentenceTransformer(model_name)
dim = model.get_sentence_embedding_dimension()  # 384 など

def embed(sentence: str) -> np.ndarray:
    return model.encode(sentence)

conn.create_function("embed", embed, [VARCHAR], f'FLOAT[{dim}]')
```

### SQL での使用例

```sql
-- 基本的なセマンティック検索
SELECT path, 1 - array_cosine_distance(embedding, embed('体調が回復した')) as score
FROM files
ORDER BY score DESC
LIMIT 10

-- frontmatter との組み合わせ
SELECT path, date, tags, 1 - array_cosine_distance(embedding, embed('モチベーション低下')) as score
FROM files
WHERE date >= '2025-11-01'
  AND tags LIKE '%振り返り%'
ORDER BY score DESC
LIMIT 10
```

## アーキテクチャ

```
Claude Code
    | MCP
    v
frontmatter-mcp
    |-- query()           # 既存（embed() 関数が使えるようになる）
    |-- query_inspect()   # 既存（embedding カラムが見える）
    |-- index_status()    # 新規
    +-- index_refresh()   # 新規
            |
            v
        DuckDB + VSS
        |-- files テーブル (path, frontmatter..., embedding)
        +-- embed() 関数 (カスタム UDF)
            ^
            |
        Embedding Module
        |-- ruri-v3-30m (ローカル、遅延ロード)
        +-- Cache (永続化、mtime 比較で差分更新)
```

## 新規ツール

### index_status

```python
def index_status() -> dict:
    """インデックスの状態を返す。

    Returns:
        {
            "indexing": false,
            "indexed_count": 660,
            "model": "cl-nagoya/ruri-v3-30m",
            "cache_path": "{base_dir}/.frontmatter-mcp/embeddings.duckdb"
        }
    """
```

- `indexing: true` の間は `embedding` カラムは使用不可
- `indexing: false` になったら `embedding` カラムが使える

### index_refresh

```python
def index_refresh() -> dict:
    """インデックスを最新化する（差分更新）。

    バックグラウンドでインデキシングを開始する。
    初回実行時は全ファイルの embedding を生成。
    以降は mtime 比較で変更があったファイルのみ更新。

    既にインデキシング中の場合は何もせず現在の状態を返す。

    Returns:
        {
            "message": "Indexing started",  # or "Indexing already in progress"
            "target_count": 665
        }
    """
```

## 既存ツールの変更

### query_inspect

セマンティック検索有効かつインデキシング完了時、スキーマに `embedding` カラムが追加される。

```python
query_inspect("**/*.md")
# {
#     "file_count": 660,
#     "schema": {
#         "path": {...},
#         "date": {...},
#         "embedding": {"type": "FLOAT[384]", ...},  # インデキシング完了時のみ
#         ...
#     }
# }
```

### query

`embed()` 関数が SQL 内で使用可能になる（インデキシング完了後）。

```python
query(
    glob="daily/*.md",
    sql="""
        SELECT path, date, 1 - array_cosine_distance(embedding, embed('体調が回復した')) as score
        FROM files
        WHERE date >= '2025-11-01'
        ORDER BY score DESC
        LIMIT 10
    """
)
```

## 環境変数

| 変数                        | デフォルト                    | 説明                       |
| --------------------------- | ----------------------------- | -------------------------- |
| FRONTMATTER_ENABLE_SEMANTIC | false                         | セマンティック検索を有効化 |
| FRONTMATTER_EMBEDDING_MODEL | cl-nagoya/ruri-v3-30m         | Embedding モデル           |
| FRONTMATTER_CACHE_DIR       | `--base-dir`/.frontmatter-mcp | キャッシュディレクトリ     |

## 永続化

```
{base_dir}/.frontmatter-mcp/
+-- embeddings.duckdb
    |-- embeddings テーブル
    |   |-- path (TEXT, PK)
    |   |-- mtime (REAL)
    |   +-- vector (FLOAT[dim])  # dim はモデルから自動取得
    +-- metadata テーブル
        |-- model_name (TEXT)
        |-- dimension (INTEGER)  # モデルの次元数
        +-- last_updated (TIMESTAMP)
```

## 起動時の挙動

1. セマンティック検索が無効 → 従来通り
2. セマンティック検索が有効 → バックグラウンドでインデキシング開始
   - キャッシュなし → 全ファイル対象
   - キャッシュあり → mtime 比較で差分更新
   - モデル名が異なる → キャッシュを破棄し全ファイル対象

## インデキシング中の挙動

- `index_status()` → `indexing: true` を返す
- `query()` → `embedding` カラムなしで実行（通常の frontmatter クエリは可能）
- `embed()` 関数 → 使用不可（エラーまたは登録されていない）

## インデックス更新の運用

- 起動時 → 自動でインデキシングが開始される
- セッション中にファイルを編集した場合 → AI が `index_refresh()` を明示的に呼び出して再インデキシングする

ツール説明に以下を記載:
> セッション中にファイルを編集した場合は `index_refresh()` を実行してください

## 依存関係

```toml
# pyproject.toml
[project.optional-dependencies]
semantic = [
    "sentence-transformers>=2.0.0",
]
```

### uvx での使用

uvx は optional dependency group を直接指定できないため、`--with` で明示指定する。

```json
{
  "mcpServers": {
    "frontmatter": {
      "command": "uvx",
      "args": [
        "--with", "sentence-transformers",
        "frontmatter-mcp",
        "--base-dir", "/path/to/vault"
      ],
      "env": {
        "FRONTMATTER_ENABLE_SEMANTIC": "true"
      }
    }
  }
}
```

VSS 拡張は DuckDB 本体に含まれており、`INSTALL vss; LOAD vss;` で有効化する。

### DuckDB VSS の注意点

- HNSW インデックスはデータ投入後に作成が高速
- 永続化は `SET hnsw_enable_experimental_persistence = true` が必要（実験的）
- 削除は即時反映されない（`PRAGMA hnsw_compact_index()` で圧縮）

## 実装タスク（TDD アプローチ）

各ステップでテストと実装を同時に進める。`pytest.mark.slow` で実モデルテストを分離。

### Step 1: Embedding モジュール

対象: `embedding.py`, `test_embedding.py`

- [ ] モデルロード（遅延ロード）
- [ ] テキスト → ベクトル変換
- [ ] 次元数の自動取得

テスト観点:

- モデルの遅延ロード確認
- encode() の出力形状
- 次元数取得

### Step 2: キャッシュモジュール

対象: `cache.py`, `test_cache.py`

- [ ] DuckDB 永続化（embeddings.duckdb）
- [ ] embeddings / metadata テーブル作成
- [ ] embedding の保存・取得
- [ ] mtime 比較による差分検出
- [ ] モデル変更時のキャッシュ破棄

テスト観点:

- テーブル作成
- embedding の CRUD
- mtime 差分検出
- モデル変更検知

### Step 3: インデキシング

対象: `indexer.py`, `test_indexer.py`

- [ ] threading による非同期処理
- [ ] 状態管理（indexing フラグ）
- [ ] 全ファイルインデキシング
- [ ] 差分更新
- [ ] 重複呼び出し対応

テスト観点:

- 非同期実行
- indexing フラグの状態遷移
- 差分更新の動作

### Step 4: query への統合

対象: `query.py`, `test_query.py`（既存拡張）

- [ ] VSS 拡張のセットアップ（INSTALL vss; LOAD vss;）
- [ ] embed() 関数の DuckDB 登録
- [ ] embedding カラムの追加（インデキシング完了時）

テスト観点:

- embed() 関数の動作
- array_cosine_distance との組み合わせ
- インデキシング未完了時の挙動

### Step 5: MCP ツール

対象: `server.py`, `test_server.py`（既存拡張）

- [ ] 環境変数による切り替え
- [ ] 起動時のバックグラウンドインデキシング
- [ ] index_status ツール
- [ ] index_refresh ツール
- [ ] query_inspect の embedding カラム対応

テスト観点:

- 環境変数の読み取り
- 各ツールのレスポンス形式
- インデキシング状態による挙動変化

### Step 6: ドキュメント

- [ ] README.md 更新
- [ ] SETUP.md にセマンティック検索セクション追加
