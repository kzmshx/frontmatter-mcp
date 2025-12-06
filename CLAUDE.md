# CLAUDE.md

## Conventional Commits / ブランチ命名

| type       | 用途                                                 |
| ---------- | ---------------------------------------------------- |
| `feat`     | 新機能                                               |
| `fix`      | バグ修正                                             |
| `docs`     | ドキュメントのみ                                     |
| `style`    | コードの意味に影響しない変更（空白、フォーマット等） |
| `refactor` | バグ修正でも機能追加でもないコード変更               |
| `test`     | テストの追加・修正                                   |
| `chore`    | ビルドプロセスやツールの変更                         |

ブランチ名: `{type}/{description}` (例: `feat/rename-tools`, `fix/json-encoding`)

## 開発ワークフロー

1. ブランチを作成 (`{type}/{description}`)
2. `docs/workspace/{branch}/PLAN.md` を作成
3. ユーザーと PLAN.md の内容を確認・吟味してから実装開始
4. 実装
5. 作業一段落ごとに `NOTES_{YYYYMMDD_HHMMSS}.md` を作成
6. PR 作成・マージ

## PR レビュー対応

| 操作             | コマンド                                                                                    |
| ---------------- | ------------------------------------------------------------------------------------------- |
| CI 状態確認      | `gh pr checks {n}`                                                                          |
| コメント取得     | `gh api repos/{owner}/{repo}/pulls/{n}/comments`                                            |
| コメントへの返信 | `gh api repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies -X POST -f body="..."` |

修正後はコミットハッシュ付きでコメントに返信する。

## ドキュメント構成

### docs/workspace/{branch}/

ブランチごとの作業ドキュメント。`.gitignore` で除外されている。

構成:

- `PLAN.md`: 機能仕様と実装タスク
- `NOTES_{YYYYMMDD_HHMMSS}.md`: 作業ログ（発見、問題、解決策）。作業一段落ごとに作成

### docs/adr/

`adr` CLI（adr-tools）で管理する。Git 管理対象。

- 新規作成: `adr new <タイトル>`
- 一覧表示: `adr list`
- 既存 ADR の置換: `adr new -s <番号> <タイトル>`

## ドキュメント作成ルール

### 共通ルール

- 絵文字使用禁止
- 区切り線 (`---`) 使用禁止

### 共通記述スタイル

- 簡潔に事実を記載
- 不要な装飾や冗長な説明を避ける（可読性を重視しリストやテーブルは使って良い）
- コードや設定は具体例を示す

### セキュリティルール（重要）

`docs/` 以下のドキュメントは Git 管理されるため、以下の情報は記載禁止:

- 秘密鍵、トークン、パスワード
- API キー、認証情報
- 個人を特定可能な情報（氏名、メールアドレス、ユーザー名）
- ローカル環境固有のパス（`/Users/username/` など）
- プロジェクト ID やリソース名は記載可（例: `exp-batch-predictions`）
- 具体的な設定値が必要な場合は `.env.example` などのテンプレートファイルを参照する
- ローカル環境固有の情報は `CLAUDE.local.md` に記載する

### docs/workspace/{branch}/PLAN.md ルール

- h1 見出しは `# PLAN` とする
- h2、h3、h4 は使用してよい（ただし過度な階層化は避ける）

### docs/workspace/{branch}/NOTES_{YYYYMMDD_HHMMSS}.md ルール

- ファイル名の時刻は `date +%Y%m%d_%H%M%S` の出力をそのまま使用（加工禁止）
- h1 見出しはファイル名と同じにする（例: `# NOTES_20251129_094523`）
- h3 以下は使わず、h2 見出し直下に要点を簡潔に記載
- 参照リンクは各見出し内に記載
