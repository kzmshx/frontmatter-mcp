# Security Policy

## Reporting a vulnerability

Report vulnerabilities privately through GitHub: Security tab > Report a vulnerability. Do not open a public issue.

## Supported versions

Only the latest release receives fixes.

## Dependencies

Dependabot opens weekly update PRs and security PRs. CI audits both `uv.lock` and the newest versions allowed by `pyproject.toml` with pip-audit, and a weekly scheduled run reports new advisories.
