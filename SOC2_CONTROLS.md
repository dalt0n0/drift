# SOC 2 Controls Mapping

Drift implements controls aligned to the SOC 2 Trust Services Criteria (TSC).

## CC6 - Logical and Physical Access Controls

### CC6.1 - Access Control Policies
- **Implementation**: Role-based access control (RBAC) with 5 tiers (admin/lead/tester/viewer/client_readonly)
- **Code**: `backend/app/core/permissions.py` - `Role` IntEnum, `require_role()`
- **Enforcement**: Every FastAPI endpoint declares `require_min_role(Role.X)` dependency

### CC6.2 - Authentication
- **Implementation**: Argon2id password hashing (64MB RAM, 3 iterations, 4 lanes); JWT access tokens (15min); rotating refresh tokens (SHA-256 stored in httpOnly Secure SameSite=Strict cookie); TOTP MFA (RFC 6238)
- **Code**: `backend/app/core/security.py`, `backend/app/routers/auth.py`
- **Brute force**: 5 failures/15min lockout; same error for unknown user vs wrong password

### CC6.3 - Access Restrictions
- **Implementation**: API endpoints return HTTP 403 if caller's role < minimum required
- **Code**: `backend/app/core/deps.py` - `require_min_role()` dependency factory

## CC7 - System Operations

### CC7.2 - Monitoring
- **Implementation**: Structured JSON logging via structlog; request IDs on all requests; audit log for every security event
- **Code**: `backend/app/core/middleware.py` - `RequestIDMiddleware`; `backend/app/core/audit.py`

### CC7.3 - Change Tracking
- **Implementation**: `before_state` / `after_state` JSONB fields in audit_log; every mutating API call records a diff
- **Code**: `backend/app/models/audit.py`, all router files

## CC8 - Change Management

### CC8.1 - Change Management Process
- **Implementation**: Alembic migrations with version-controlled scripts; CI pipeline with lint/test/scan gates
- **Code**: `backend/alembic/versions/`, `.github/workflows/ci.yml`

## CC9 - Risk Mitigation

### CC9.1 - Risk Mitigation
- **Implementation**: Rate limiting (slowapi, 100r/min general, 10r/min auth); brute-force lockout; CORS; CSP; HSTS; non-root containers; dependency scanning (Bandit, Semgrep, Trivy in CI)
- **Code**: `backend/app/core/middleware.py`, `backend/app/routers/auth.py`, `.github/workflows/ci.yml`

## CC1-CC5 - Organization and Risk Assessment

These controls (governance, risk assessment, vendor management) are organizational processes. Technical implementations that support them:
- **CC1**: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`
- **CC3**: `THREAT_MODEL.md` - documented threat model
- **CC4/CC5**: `SECURITY.md` - vulnerability disclosure, dependency scanning in CI
