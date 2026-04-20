# ReconStrike Threat Model

## Scope
This document covers the ReconStrike application itself (not the target systems being tested).

## Trust Boundaries
1. Browser ↔ Nginx (TLS)
2. Nginx ↔ FastAPI (Docker internal network)
3. FastAPI ↔ PostgreSQL (Docker internal network, password auth)
4. FastAPI ↔ Redis (Docker internal network, password auth)
5. Celery Workers ↔ Tool binaries (subprocess)

## Threats and Mitigations

### Authentication
| Threat | Mitigation |
|--------|-----------|
| Brute force login | 5-failure lockout per username+IP/15min; rate limiting at nginx |
| Credential stuffing | Same lockout + Argon2id (slow hash, 64MB memory) |
| Token theft (XSS) | httpOnly refresh cookie; short-lived (15min) access tokens |
| Session fixation | New refresh token on every rotation; old token immediately revoked |
| MFA bypass | TOTP required before token issuance; secret AES-256-GCM encrypted |

### Authorization
| Threat | Mitigation |
|--------|-----------|
| Privilege escalation | Role hierarchy enforced in every endpoint; users cannot set their own role |
| IDOR | All resource queries include ownership check |
| Horizontal escalation | User can only access own profile unless role >= lead |

### Injection
| Threat | Mitigation |
|--------|-----------|
| SQL injection | SQLAlchemy ORM with parameterized queries; no raw SQL |
| Audit log injection | Canonical JSON serialization; no interpolation in chain hash |
| Command injection (Phase 3+) | All tool invocations use `subprocess` with list args (no shell=True) |

### Audit Log
| Threat | Mitigation |
|--------|-----------|
| Log tampering | Hash-chained entries; daily integrity verification |
| Log deletion | Append-only table (no DELETE permission for app user in production); MinIO WORM mode |
| Log flooding | Structured logging with sampling; rate limiting on endpoints |

### Secrets
| Threat | Mitigation |
|--------|-----------|
| Secret leakage in logs | Sensitive keys redacted in audit log (`_SENSITIVE_KEYS` set) |
| Secret leakage in errors | Generic error messages; DEBUG=false in production |
| Env var exposure | Secrets via env vars; no secrets in code or Docker layers |
| VAULT_MASTER_KEY compromise | AES-256-GCM with per-record nonces; key rotation path via re-encrypt endpoint (Phase 2) |

### Infrastructure
| Threat | Mitigation |
|--------|-----------|
| Container escape | Non-root user (uid 1000); `no-new-privileges`; minimal base image |
| Network lateral movement | DB/Redis on isolated internal Docker network; API on both |
| Supply chain | Pinned dependency versions; Trivy + Grype in CI; Sigstore cosign (Phase 6) |
| Dependency vulnerability | Dependabot; pip-audit; Bandit; Semgrep in CI |
