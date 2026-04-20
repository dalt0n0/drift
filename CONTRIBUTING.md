# Contributing to Drift

Thank you for your interest in contributing.

## Before You Start

- Read the `CODE_OF_CONDUCT.md`
- Check existing issues and pull requests
- For significant changes, open an issue first to discuss

## Development Setup

```bash
git clone https://github.com/dalt0n0/drift
cd Drift
cp .env.example .env
# Edit .env with dev secrets

# Start services
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml up -d

# Install dev deps
cd backend && pip install -r requirements-dev.txt
```

## Code Standards

- Python: `ruff` for linting/formatting; `mypy` for type checking
- All new endpoints must: have type annotations, log to audit trail, enforce RBAC
- Tests required for new features (aim for 80%+ coverage on new code)
- No secrets in code; all config via environment variables

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Write tests for your changes
3. Run `ruff check`, `bandit -r app`, `pytest tests/ -v`
4. Submit PR with a clear description and link to any related issues
5. Ensure CI passes

## Security Contributions

- **Do not** submit PRs that weaken security controls
- New tool integrations must: use list args (no `shell=True`), validate input, scope-check targets
- Crypto changes require maintainer review

## Reporting Issues

- Security vulnerabilities: see `SECURITY.md` (private disclosure)
- Bugs: open a GitHub issue with reproduction steps
- Feature requests: open a GitHub discussion
