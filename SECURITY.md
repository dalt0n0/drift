# Security Policy

## Reporting Vulnerabilities

**Do not open public issues for security vulnerabilities.**

Email: security@Driftsec.io (or open a GitHub Security Advisory)

Include: description, reproduction steps, impact assessment, suggested fix.

We will respond within 72 hours and aim to patch within 14 days.

## Security Controls

### Authentication
- Argon2id (time=3, mem=64MB, par=4) password hashing
- 15-minute JWT access tokens with jti claim
- 30-day rotating refresh tokens (SHA-256 stored, httpOnly cookie)
- TOTP MFA (RFC 6238, ±30s window)
- API keys with drk_ prefix, SHA-256 stored

### Authorization
- 5-tier RBAC: admin > lead > tester > viewer > client_readonly
- Every endpoint declares minimum role
- Users cannot escalate their own role

### Brute Force Protection
- 5 failed attempts per username+IP in 15 minutes → lockout
- Same error message for unknown user vs wrong password (no enumeration)
- nginx rate limiting: 100r/min general, 10r/min auth endpoints

### Audit Log
- Hash-chained (SHA-256 of previous entry's canonical JSON)
- Append-only PostgreSQL table
- Mirrored JSONL to disk + MinIO archival
- Sensitive fields (passwords, tokens, secrets) always redacted
- Daily integrity verification job

### Transport Security
- TLS 1.2/1.3 only (nginx)
- HSTS (1 year, includeSubDomains, preload) in production
- X-Frame-Options: DENY
- Content-Security-Policy
- Referrer-Policy: strict-origin-when-cross-origin

### Secrets Management
- All secrets via environment variables
- VAULT_MASTER_KEY for AES-256-GCM field encryption (MFA secrets)
- Never logged, never in responses

### Container Security
- Non-root user (drift, uid 1000)
- Multi-stage Docker build
- Trivy scan in CI
