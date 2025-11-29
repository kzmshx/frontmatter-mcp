# Task Completion Checklist

## Before Committing

1. Run linter and fix issues:
   ```bash
   make fix
   ```

2. Run tests:
   ```bash
   make test
   ```

3. Verify lint passes:
   ```bash
   make lint
   ```

## Workflow

1. Create branch: `{type}/{description}`
2. Create plan: `docs/workspace/{branch}/PLAN.md`
3. Implement changes
4. Create notes if needed: `docs/workspace/{branch}/NOTES_{YYYYMMDD_HHMMSS}.md`
5. Create PR and merge

## Documentation Rules

- No emojis
- No horizontal rules (`---`)
- Keep concise, use lists/tables
- No secrets/credentials in docs
- No local paths (e.g., `/Users/username/`)
