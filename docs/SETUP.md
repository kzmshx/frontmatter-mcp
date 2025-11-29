# SETUP

## 開発環境構築

### 依存関係のインストール

```bash
uv sync
```

### Serena MCP のセットアップ

Serena はコード解析用の MCP サーバー。プロジェクト設定は `.serena/` に含まれている。

プロジェクトルートで以下を実行:

```bash
claude mcp add serena -s local -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context ide-assistant --project $(pwd)
```

## コマンド一覧

| コマンド | 説明 |
|---------|------|
| `make lint` | リンター実行 |
| `make fix` | リント問題を自動修正 |
| `make test` | テスト実行 |
| `make help` | コマンド一覧表示 |

## MCP サーバーの実行

```bash
uv run frontmatter-mcp --base-dir /path/to/markdown
```
