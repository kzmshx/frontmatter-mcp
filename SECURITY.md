# Security Policy

## Reporting a vulnerability

Report vulnerabilities privately through GitHub: Security tab > Report a vulnerability. Do not open a public issue.

## Supported versions

Only the latest release receives fixes.

## Dependencies

Dependabot opens one weekly PR with all updates (uv and GitHub Actions, major versions included), plus security PRs as advisories appear. CI audits both `uv.lock` and the newest versions allowed by `pyproject.toml` with pip-audit, and a weekly scheduled run reports new advisories.
