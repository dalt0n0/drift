# Drift

> **Authorized penetration testing engagements only.**
> Using this tool against systems you do not have written permission to test is illegal.
> See [DISCLAIMER.md](DISCLAIMER.md).

Open-source, web-based automated penetration testing platform. Drift wraps best-in-class open-source security tools (Nmap, Nuclei, Subfinder, ZAP, ffuf, and more) behind a clean web UI with engagement management, real-time scan output, vulnerability correlation, and SOC 2-aligned audit logging.

---

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment File Reference](#environment-file-reference)
- [First-Run Setup](#first-run-setup)
- [Development Mode](#development-mode)
- [Running Tests](#running-tests)
- [Roles & Access Control](#roles--access-control)
- [API](#api)
- [Production Hardening](#production-hardening)
- [Project Phases](#project-phases)

---

## Architecture

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 SPA (single `index.html`, CDN libs, no build step) |
| Backend | FastAPI 0.111 + Python 3.11, async SQLAlchemy 2.x |
| Task queue | Celery 5 + Redis 7 |
| Database | PostgreSQL 16 |
| Object storage | MinIO (S3-compatible) — artifacts, evidence, reports, audit archive |
| Auth | JWT (15 min) + rotating refresh tokens, TOTP MFA, API keys, RBAC |
| Audit log | Hash-chained, tamper-evident, SOC 2 aligned |

---

## Prerequisites

- **Docker** 24+ and **Docker Compose** v2 (`docker compose`)
- **Git**
- A Linux/macOS host or WSL2 on Windows for production

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/dalt0n0/drift.git
cd drift
```

### 2. Create your `.env`

```bash
cp .env.example .env
```

Then open `.env` and fill in every `CHANGE_ME` value. See the full reference below.

**Generate secrets with these one-liners:**

```bash
# SECRET_KEY (32-byte hex)
openssl rand -hex 32

# JWT_SECRET (64-byte hex)
openssl rand -hex 64

# POSTGRES_PASSWORD / REDIS_PASSWORD / MINIO_ROOT_PASSWORD
openssl rand -base64 32

# VAULT_MASTER_KEY (32-byte urlsafe-base64)
python3 -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### 3. Start services

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Services started:

| Service | Internal port | Exposed |
|---------|--------------|---------|
| api (FastAPI) | 8000 | 8000 |
| db (PostgreSQL 16) | 5432 | — |
| redis (Redis 7) | 6379 | — |
| minio (object storage) | 9000 | — |
| minio console | 9001 | 9001 |

### 4. Run database migrations

```bash
docker compose -f deploy/docker-compose.yml exec api alembic upgrade head
```

### 5. Create the first admin user

```bash
docker compose -f deploy/docker-compose.yml exec api python3 - <<'PYEOF'
import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password

async def main():
    async with AsyncSessionLocal() as db:
        u = User(
            username="admin",
            email="admin@drift.local",
            full_name="Admin",
            role="admin",
            hashed_password=hash_password("ChangeMe123!"),
        )
        db.add(u)
        await db.commit()
        print("Admin created — change the password after first login.")

asyncio.run(main())
PYEOF
```

### 6. Verify

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"0.1.0"}
```

Log in and get a token:

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"ChangeMe123!"}' | python3 -m json.tool
```

---

## Environment File Reference

Copy `.env.example` to `.env`. Every variable is described below.

### App

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | 32-byte hex string. Used for misc signing. `openssl rand -hex 32` |
| `JWT_SECRET` | Yes | — | 64-byte hex string. Signs JWT access tokens. `openssl rand -hex 64` |
| `ENVIRONMENT` | | `development` | Set to `production` to enable HSTS and disable debug endpoints |
| `DEBUG` | | `false` | `true` enables Swagger UI at `/api/docs` and verbose logs. **Never true in production.** |
| `ALLOWED_ORIGINS` | | `http://localhost:3000` | Comma-separated CORS origins. Production: `https://yourdomain.com` |
| `OPEN_REGISTRATION` | | `false` | `true` allows anyone to self-register. **Keep false in production.** |

### Database

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://drift:<password>@db:5432/drift` — must match `POSTGRES_PASSWORD` |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password for the `drift` user |

### Redis

| Variable | Required | Description |
|----------|----------|-------------|
| `REDIS_URL` | Yes | `redis://:<password>@redis:6379/0` — must match `REDIS_PASSWORD` |
| `REDIS_PASSWORD` | Yes | Redis auth password |

### MinIO (Object Storage)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MINIO_ENDPOINT` | | `minio:9000` | MinIO host:port (internal Docker hostname) |
| `MINIO_ROOT_USER` | | `drift` | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | Yes | — | MinIO admin password |
| `MINIO_BUCKET_ARTIFACTS` | | `artifacts` | Bucket for scan evidence and tool output |
| `MINIO_BUCKET_REPORTS` | | `reports` | Bucket for generated PDF/HTML reports |
| `MINIO_BUCKET_AUDIT` | | `audit-archive` | Bucket for WORM audit log archival |
| `MINIO_SECURE` | | `false` | Set `true` if MinIO is behind TLS |

### Encryption

| Variable | Required | Description |
|----------|----------|-------------|
| `VAULT_MASTER_KEY` | Yes | 32-byte urlsafe-base64 key for AES-256-GCM field encryption (MFA secrets). Generate: `python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` |

### Audit Log

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIT_LOG_PATH` | `/var/drift/audit/audit.jsonl` | Local JSONL mirror of the audit log |
| `AUDIT_RETENTION_DAYS` | `365` | Hot retention in days; cold archival to MinIO is configurable |

### Celery (Task Queue)

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://:…@redis:6379/1` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://:…@redis:6379/2` | Celery result backend |

> Celery workers are wired but scan tasks are stubs in Phase 1. Full execution lands in Phase 3.

---

## First-Run Setup

### Stop / restart

```bash
# Stop (preserves volumes/data)
docker compose -f deploy/docker-compose.yml down

# Stop and wipe all data
docker compose -f deploy/docker-compose.yml down -v

# Restart
docker compose -f deploy/docker-compose.yml up -d
```

### Update after a code change

```bash
git pull
docker compose -f deploy/docker-compose.yml build api
docker compose -f deploy/docker-compose.yml exec api alembic upgrade head
docker compose -f deploy/docker-compose.yml up -d
```

### View logs

```bash
# All services
docker compose -f deploy/docker-compose.yml logs -f

# API only
docker compose -f deploy/docker-compose.yml logs -f api
```

### MinIO console

Navigate to `http://<host>:9001` — log in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`.

---

## Development Mode

Enables hot-reload, Swagger UI, and open registration:

```bash
docker compose \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.dev.yml \
  up
```

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- OpenAPI JSON: `http://localhost:8000/api/openapi.json`

The dev override sets `DEBUG=true` and `OPEN_REGISTRATION=true` automatically.

### Local Python (without Docker)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Edit .env to point DATABASE_URL at localhost:5432
uvicorn app.main:app --reload --port 8000
```

---

## Running Tests

No running Postgres needed — tests use an in-memory SQLite database.

```bash
cd backend
pip install -r requirements-dev.txt

# Full suite with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Single file
pytest tests/test_audit.py -v

# HTML coverage report
pytest tests/ --cov=app --cov-report=html && open htmlcov/index.html
```

Test coverage targets: auth flows, audit chain integrity, RBAC enforcement.

---

## Roles & Access Control

| Role | Description |
|------|-------------|
| `admin` | Full access — user management, audit log, all endpoints |
| `lead` | Manage engagements, view all findings, list users |
| `tester` | Create and run scans, manage findings |
| `viewer` | Read-only across all engagements |
| `client_readonly` | Redacted view of their own engagement only |

Role hierarchy: `admin > lead > tester > viewer > client_readonly`

Users cannot elevate their own role. All role changes are audit-logged.

---

## API

Base URL: `http://localhost:8000/api`

### Authentication

**JWT Bearer:**
```
Authorization: Bearer <access_token>
```

**API key:**
```
Authorization: Bearer drk_<key>
```

### Endpoints

#### Auth

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| POST | `/auth/login` | — | Login; returns access token, sets refresh cookie |
| POST | `/auth/refresh` | — | Rotate refresh token |
| POST | `/auth/logout` | any | Revoke current session |
| POST | `/auth/logout-all` | any | Revoke all sessions |
| POST | `/auth/register` | admin (prod) | Create user |
| GET | `/auth/me` | any | Current user profile |
| POST | `/auth/change-password` | any | Change password, invalidate all sessions |
| POST | `/auth/mfa/setup` | any | Generate TOTP secret + provisioning URI |
| POST | `/auth/mfa/confirm` | any | Enable MFA |
| POST | `/auth/mfa/disable` | any | Disable MFA (requires current TOTP code) |
| POST | `/auth/api-keys` | any | Create API key (raw shown once) |
| GET | `/auth/api-keys` | any | List your API keys |
| DELETE | `/auth/api-keys/{id}` | any | Revoke API key |

#### Users

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/users/` | lead | List all users |
| GET | `/users/{id}` | self or lead | Get user |
| PATCH | `/users/{id}` | self (name/email) or admin (role/status) | Update user |
| DELETE | `/users/{id}` | admin | Delete user |

#### Audit Log

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/audit/` | admin | Paginated, filterable audit log |
| GET | `/audit/verify` | admin | Verify hash chain integrity |
| GET | `/audit/export?format=json\|csv` | admin | Export full audit log |

#### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (unauthenticated) |
| GET | `/api/openapi.json` | OpenAPI 3.1 spec |
| WS | `/ws/{engagement_id}` | Real-time scan output (Phase 2) |

---

## Production Hardening

```bash
# .env settings for production
ENVIRONMENT=production
DEBUG=false
OPEN_REGISTRATION=false
ALLOWED_ORIGINS=https://yourdomain.com
```

Checklist before go-live:

- [ ] All `CHANGE_ME` values replaced with strong generated secrets
- [ ] `ENVIRONMENT=production` (enables HSTS, disables docs)
- [ ] `DEBUG=false`
- [ ] `ALLOWED_ORIGINS` set to your actual domain only
- [ ] Nginx in front with valid TLS cert (see `nginx/drift.conf`)
- [ ] MinIO port 9001 not exposed publicly
- [ ] MinIO object lock (WORM) enabled on `audit-archive` bucket
- [ ] Firewall: only ports 80/443 (or proxy port) open externally
- [ ] Backups configured for PostgreSQL volume (`pgdata`)

Security controls active in all environments:

- Argon2id password hashing (64 MB RAM, 3 iterations, 4 lanes)
- 5-failure brute-force lockout per username+IP per 15 minutes
- Rotating refresh tokens (httpOnly, Secure, SameSite=Strict)
- AES-256-GCM field encryption for sensitive data (MFA secrets)
- Hash-chained audit log — tamper detection via `GET /api/audit/verify`
- `X-Frame-Options: DENY`, CSP, `X-Content-Type-Options` on all responses
- Rate limiting via slowapi (100 req/min general, 10 req/min auth)

---

## Project Phases

| Phase | Status | Scope |
|-------|--------|-------|
| **1** | Done | Scaffold, auth, RBAC, hash-chained audit log, docker-compose |
| **2** | Next | Engagement + scope models, plugin manifest, orchestrator core |
| **3** | Planned | Passive + active recon (Subfinder, Amass, Nmap, httpx) |
| **4** | Planned | Web + network testing (Nuclei, ZAP, ffuf, NetExec) |
| **5** | Planned | CVE correlation, CVSS/EPSS, PDF/HTML/SARIF reporting |
| **6** | Planned | SBOM, cosign signing, SLSA provenance, Helm chart |
| **7** | Planned | E2E tests vs Juice Shop + DVWA, v0.1.0 release |

---

## License

[AGPLv3](LICENSE) — if you run a modified version as a network service, you must publish your source.
