# Code Style and Conventions

## Python Style

- Formatter/Linter: Ruff
- Quote style: Double quotes
- Indent style: Spaces
- Rules: E, F, I (isort), B (bugbear)

## Type Hints

- Use type hints for function signatures
- Use `dict[str, Any]` style (Python 3.9+ syntax)
- Use `list[str]` instead of `List[str]`

## Docstrings

- Use docstrings for public functions
- Google-style format:
  - Args:
  - Returns:
  - Notes:

## Naming

- Functions: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE

## Git Conventions

### Commit Messages (Conventional Commits)

| Type | Usage |
|------|-------|
| feat | New feature |
| fix | Bug fix |
| docs | Documentation only |
| style | Code style changes |
| refactor | Code refactoring |
| test | Test additions/changes |
| chore | Build/tool changes |

### Branch Naming

Pattern: `{type}/{description}`

Examples:
- `feat/rename-tools`
- `fix/json-encoding`
- `docs/update-readme`
