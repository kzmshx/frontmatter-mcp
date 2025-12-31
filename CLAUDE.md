# CLAUDE.md

## Conventional Commits / Branch Naming

| type       | purpose                                            |
| ---------- | -------------------------------------------------- |
| `feat`     | New feature                                        |
| `fix`      | Bug fix                                            |
| `docs`     | Documentation only                                 |
| `style`    | Changes that don't affect code meaning (whitespace, formatting) |
| `refactor` | Code change that is neither a fix nor a feature   |
| `test`     | Adding or modifying tests                          |
| `chore`    | Build process or tooling changes                   |

Branch name: `{type}/{description}` (e.g., `feat/rename-tools`, `fix/json-encoding`)

## PR Review Handling

| Operation      | Command                                                                                     |
| -------------- | ------------------------------------------------------------------------------------------- |
| Check CI       | `gh pr checks {n}`                                                                          |
| Get comments   | `gh api repos/{owner}/{repo}/pulls/{n}/comments`                                            |
| Reply          | `gh api repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies -X POST -f body="..."` |

Reply to comments with commit hash after fixes.

## Documentation Structure

### docs/adr/

Managed with `adr` CLI (adr-tools). Git tracked.

- Create: `adr new <title>`
- List: `adr list`
- Supersede: `adr new -s <number> <title>`

## Documentation Rules

### Common Rules

- No emojis
- No horizontal rules (`---`)

### Common Style

- State facts concisely
- Avoid unnecessary decoration or verbose explanations (lists and tables are fine for readability)
- Show concrete examples for code and config

### Security Rules (Important)

Documents under `docs/` are Git tracked, so the following are prohibited:

- Private keys, tokens, passwords
- API keys, credentials
- Personally identifiable information (names, emails, usernames)
- Local environment paths (e.g., `/Users/username/`)
- Project IDs and resource names are OK (e.g., `exp-batch-predictions`)
- For specific config values, reference template files like `.env.example`
- Local environment info should go in `CLAUDE.local.md`
