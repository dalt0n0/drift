# Drift

> **Authorized penetration testing engagements only.**
> Using this tool against systems you do not have written permission to test is illegal.
> See [DISCLAIMER.md](DISCLAIMER.md).

Open-source, web-based automated penetration testing platform. Drift wraps best-in-class open-source security tools (Nmap, Nuclei, Subfinder, ZAP, ffuf, and 28 more) behind a clean web UI with engagement management, real-time scan output, vulnerability correlation, and SOC 2-aligned audit logging.

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
- [Engagement Workflow](#engagement-workflow)
- [Modules](#modules)
- [API](#api)
- [WebSocket](#websocket)
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
| Object storage | MinIO (S3-compatible) -- artifacts, evidence, reports, audit archive |
| Auth | JWT (15 min) + rotating refresh tokens, TOTP MFA, API keys, RBAC |
| Audit log | Hash-chained, tamper-evident, SOC 2 aligned |
| Tools container | Kali-based Docker image with all security tools pre-installed |

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

### 2. Automated setup (recommended)

```bash
bash scripts/setup.sh
```

This will:
- Generate all required secrets
- Write a `.env` file
- Build and start all services
- Run database migrations
- Create an admin user (password printed once)

### 3. Manual setup

```bash
cp .env.example .env
# Fill in all CHANGE_ME values (see Environment File Reference below)

# Always include --env-file when using -f
DC="docker compose -f deploy/docker-compose.yml --env-file .env"

$DC build
$DC up -d db redis minio
$DC run --rm api alembic upgrade head
$DC up -d
```

### 4. Verify

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"0.1.0"}
```

Log in:

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<password>"}' | python3 -m json.tool
```

---

## Environment File Reference

Copy `.env.example` to `.env`. Every variable is described below.

**Generate secrets:**

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

### App

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | -- | 32-byte hex string. Used for misc signing. |
| `JWT_SECRET` | Yes | -- | 64-byte hex string. Signs JWT access tokens. |
| `ENVIRONMENT` | | `development` | Set to `production` to enable HSTS and disable debug endpoints. |
| `DEBUG` | | `false` | `true` enables Swagger UI at `/api/docs`. Never true in production. |
| `ALLOWED_ORIGINS` | | `http://localhost:3000` | Comma-separated CORS origins. |
| `OPEN_REGISTRATION` | | `false` | `true` allows self-registration. Keep false in production. |

### Engagement & Scope

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOW_RFC1918` | `false` | Set `true` to allow RFC-1918 private IPs in scope. **Off by default** -- all private ranges are hard-blocked to prevent internal network scanning. |
| `ENABLE_CLOUD_MODULES` | `false` | Set `true` to enable cloud security assessment plugins (Prowler, ScoutSuite, CloudSploit). Requires cloud credentials configured separately. |

### Database

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://drift:<password>@db:5432/drift` -- must match `POSTGRES_PASSWORD`. |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password for the `drift` user. |

### Redis

| Variable | Required | Description |
|----------|----------|-------------|
| `REDIS_URL` | Yes | `redis://:<password>@redis:6379/0` -- must match `REDIS_PASSWORD`. |
| `REDIS_PASSWORD` | Yes | Redis auth password. |

### MinIO (Object Storage)

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `minio:9000` | MinIO host:port (internal Docker hostname). |
| `MINIO_ROOT_USER` | `drift` | MinIO admin username. |
| `MINIO_ROOT_PASSWORD` | **required** | MinIO admin password. |
| `MINIO_BUCKET_ARTIFACTS` | `artifacts` | Bucket for scan evidence and tool output. |
| `MINIO_BUCKET_REPORTS` | `reports` | Bucket for generated PDF/HTML reports. |
| `MINIO_BUCKET_AUDIT` | `audit-archive` | Bucket for WORM audit log archival. |
| `MINIO_SECURE` | `false` | Set `true` if MinIO is behind TLS. |

### Encryption

| Variable | Required | Description |
|----------|----------|-------------|
| `VAULT_MASTER_KEY` | Yes | 32-byte urlsafe-base64 key for AES-256-GCM field encryption (MFA secrets). |

### Audit Log

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIT_LOG_PATH` | `/var/drift/audit/audit.jsonl` | Local JSONL mirror of the audit log. |
| `AUDIT_RETENTION_DAYS` | `365` | Hot retention in days. |

### Celery (Task Queue)

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://:...@redis:6379/1` | Celery broker URL. |
| `CELERY_RESULT_BACKEND` | `redis://:...@redis:6379/2` | Celery result backend URL. |

---

## First-Run Setup

### Services started

| Service | Internal port | Exposed | Description |
|---------|--------------|---------|-------------|
| `api` (FastAPI) | 8000 | 8000 | REST API + WebSocket |
| `db` (PostgreSQL 16) | 5432 | -- | Primary database |
| `redis` (Redis 7) | 6379 | -- | Cache + Celery broker |
| `minio` (object storage) | 9000 | -- | Artifact/report storage |
| `minio` console | 9001 | 9001 | MinIO web console |
| `tools` (Kali-based) | -- | -- | Security tools container |

### Stop / restart

```bash
DC="docker compose -f deploy/docker-compose.yml --env-file .env"

# Stop (preserves data)
$DC down

# Stop and wipe all data
$DC down -v

# Restart
$DC up -d
```

### Update after code changes

```bash
bash scripts/update.sh
```

Or manually:

```bash
DC="docker compose -f deploy/docker-compose.yml --env-file .env"
git pull && $DC build api && $DC run --rm api alembic upgrade head && $DC up -d
```

### View logs

```bash
DC="docker compose -f deploy/docker-compose.yml --env-file .env"
$DC logs -f          # all services
$DC logs -f api      # API only
$DC logs -f tools    # tools container
```

### MinIO console

Navigate to `http://<host>:9001` -- log in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`.

---

## Development Mode

Enables hot-reload, Swagger UI, and open registration:

```bash
docker compose \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.dev.yml \
  --env-file .env \
  up
```

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- OpenAPI JSON: `http://localhost:8000/api/openapi.json`

---

## Running Tests

Tests use in-memory SQLite -- no running Postgres needed.

```bash
cd backend
pip install -r requirements-dev.txt

# Full suite with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Individual test files
pytest tests/test_auth.py -v
pytest tests/test_scope_validator.py -v
pytest tests/test_web_plugins.py -v
pytest tests/test_network_plugins.py -v
pytest tests/test_evidence.py -v

# Coverage HTML report
pytest tests/ --cov=app --cov-report=html
```

---

## Roles & Access Control

| Role | Description |
|------|-------------|
| `admin` | Full access -- user management, audit log, all endpoints |
| `lead` | Manage engagements, view all findings, list users |
| `tester` | Create and run scans, manage findings |
| `viewer` | Read-only across all engagements |
| `client_readonly` | Redacted view of their own engagement only |

Role hierarchy: `admin > lead > tester > viewer > client_readonly`

Users cannot elevate their own role. All role changes are audit-logged.

---

## Engagement Workflow

1. **Create engagement** (`POST /api/engagements`) -- title, client name, start/end dates
2. **Add scope** (`POST /api/engagements/{id}/scope`) -- CIDRs, domains, IPs, URLs, wildcards
3. **Upload authorization letter** (`POST /api/engagements/{id}/authorization`) -- stored in MinIO, SHA-256 hashed
4. **Confirm authorization** (`POST /api/engagements/{id}/confirm-authorization`) -- type "I HAVE AUTHORIZATION" to unlock intrusive modules
5. **Dry run** (`POST /api/engagements/{id}/runs/dry-run`) -- validates scope + plugin order without executing anything
6. **Create run** (`POST /api/engagements/{id}/runs`) -- select plugins, options; run is queued via Celery
7. **Stream output** -- connect WebSocket at `ws://host:8000/ws/{engagement_id}?token=<jwt>` for live output
8. **Review findings** -- findings land in the DB as tools complete; download artifacts from MinIO
9. **Generate report** -- Phase 5 (coming): PDF/HTML/SARIF/CSV

### Scope hard-blocks (enforced in all phases, cannot be overridden)

The following are always blocked regardless of scope items:

| Category | Blocked ranges |
|----------|---------------|
| RFC-1918 private | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` |
| Loopback | `127.0.0.0/8`, `::1/128` |
| Link-local | `169.254.0.0/16`, `fe80::/10` |
| CGNAT | `100.64.0.0/10` |
| Cloud metadata | `169.254.169.254/32`, `fd00:ec2::254/128` |
| TLDs | `.gov`, `.mil` |
| Cloud metadata domains | `metadata.google.internal`, `metadata.azure.com` |

To allow RFC-1918 ranges (e.g., internal network pentest with explicit authorization): set `ALLOW_RFC1918=true` in `.env`.

---

## Modules

Drift ships 33 built-in plugins across four categories. Cloud modules require `ENABLE_CLOUD_MODULES=true`.

### Passive Recon (safe mode allowed)

| Plugin | Tool | Description |
|--------|------|-------------|
| `subfinder` | Subfinder 2.6.6 | Subdomain discovery via passive sources |
| `amass` | Amass 4.x | Subdomain + ASN enumeration |
| `assetfinder` | Assetfinder | Related domain/subdomain discovery |
| `dnsx` | dnsx | DNS resolution and validation |
| `httpx` | httpx | HTTP probing -- alive hosts, status codes, tech fingerprint |
| `waybackurls` | Waybackurls | URL discovery from Wayback Machine |
| `gau` | gau | URL discovery from various archives |
| `theharvester` | theHarvester | Email, subdomain, name harvesting from public sources |
| `sherlock` | Sherlock | Username enumeration across social platforms |
| `katana` | Katana | JS-aware web crawler for endpoint discovery |
| `sslyze` | sslyze | TLS/SSL configuration analysis |
| `testssl` | testssl.sh | Comprehensive TLS/SSL testing |

### Active Recon (requires authorization confirmation)

| Plugin | Tool | Description |
|--------|------|-------------|
| `nmap` | Nmap | Port scanning with service/version detection (`-sV -sC`) |
| `masscan` | Masscan | Fast port discovery at high speed |
| `naabu` | Naabu | Fast port scanner from ProjectDiscovery |
| `rustscan` | RustScan | Ultra-fast port scanner |

### Web Testing (requires authorization confirmation)

| Plugin | Tool | Description |
|--------|------|-------------|
| `nuclei` | Nuclei 3.x | Template-based vulnerability scanner (community templates) |
| `zap` | OWASP ZAP 2.14 | Passive + active web application scanner |
| `ffuf` | ffuf | Fast web fuzzer for directory/parameter discovery |
| `feroxbuster` | Feroxbuster | Recursive content/directory discovery |
| `gobuster` | Gobuster | Directory/DNS/vhost brute-forcer |
| `wapiti` | Wapiti | Web application vulnerability scanner |
| `nikto` | Nikto | Web server misconfiguration scanner |

### Network Testing (requires authorization confirmation)

| Plugin | Tool | Description |
|--------|------|-------------|
| `enum4linux-ng` | enum4linux-ng | SMB/RPC/LDAP enumeration |
| `netexec` | NetExec (nxc) | SMB/WinRM/LDAP/SSH network exec framework |
| `smbmap` | smbmap | SMB share enumeration and access testing |
| `ldapsearch` | ldapsearch | LDAP directory enumeration |
| `onesixtyone` | onesixtyone | SNMP community string brute-forcer |

### Cloud Security (opt-in via `ENABLE_CLOUD_MODULES=true`)

| Plugin | Tool | Description |
|--------|------|-------------|
| `prowler` | Prowler 4.x | AWS/Azure/GCP security posture assessment |
| `scoutsuite` | ScoutSuite | Multi-cloud security auditing |
| `cloudsploit` | CloudSploit | Cloud infrastructure misconfiguration scanner |

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

### Auth endpoints

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| POST | `/auth/login` | -- | Login; returns access token, sets refresh cookie |
| POST | `/auth/refresh` | -- | Rotate refresh token |
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

### Users

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/users/` | lead | List all users |
| GET | `/users/{id}` | self or lead | Get user |
| PATCH | `/users/{id}` | self (name/email) or admin (role/status) | Update user |
| DELETE | `/users/{id}` | admin | Delete user |

### Engagements

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/engagements/` | viewer | List engagements |
| POST | `/engagements/` | tester | Create engagement |
| GET | `/engagements/{id}` | viewer | Get engagement |
| PATCH | `/engagements/{id}` | tester | Update engagement |
| DELETE | `/engagements/{id}` | lead | Delete engagement |
| POST | `/engagements/{id}/authorization` | tester | Upload authorization letter |
| POST | `/engagements/{id}/confirm-authorization` | tester | Confirm authorization (unlocks intrusive modules) |

### Scope

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/engagements/{id}/scope` | viewer | List scope items |
| POST | `/engagements/{id}/scope` | tester | Add scope item |
| POST | `/engagements/{id}/scope/batch` | tester | Add multiple scope items |
| DELETE | `/engagements/{id}/scope/{item_id}` | tester | Remove scope item |

### Runs

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/engagements/{id}/runs` | viewer | List runs |
| POST | `/engagements/{id}/runs` | tester | Create run (queues scan pipeline) |
| POST | `/engagements/{id}/runs/dry-run` | tester | Validate without executing |
| GET | `/runs/{run_id}` | viewer | Get run detail + status |
| POST | `/runs/{run_id}/resume` | tester | Resume paused run |
| POST | `/runs/{run_id}/cancel` | tester | Cancel running scan |

### Modules

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/modules/` | viewer | List all registered plugins with manifests |
| GET | `/modules/{name}` | viewer | Get plugin manifest by name |

### Audit Log

| Method | Path | Min role | Description |
|--------|------|----------|-------------|
| GET | `/audit/` | admin | Paginated, filterable audit log |
| GET | `/audit/verify` | admin | Verify hash chain integrity |
| GET | `/audit/export?format=json\|csv` | admin | Export full audit log |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (unauthenticated) |
| GET | `/api/openapi.json` | OpenAPI 3.1 spec |

---

## WebSocket

Real-time scan output is streamed over WebSocket:

```
ws://host:8000/ws/{engagement_id}?token=<jwt_access_token>
```

Authenticate with a JWT access token as a query parameter (cookie auth is not supported for WS).

### Event types

```json
{"type": "output",   "tool": "nuclei", "line": "..."}
{"type": "progress", "tool": "nmap",   "status": "running",   "command": "nmap"}
{"type": "progress", "tool": "nmap",   "status": "completed", "duration": 12.3, "findings_count": 5}
{"type": "finding",  "tool": "nuclei", "severity": "high",    "name": "...",    "matched_at": "..."}
{"type": "error",    "tool": "ffuf",   "message": "timeout"}
{"type": "done",     "run_id": "..."}
```

Messages are published by Celery workers to Redis pub/sub (`engagement:{id}:stream`) and forwarded to all connected WebSocket clients for that engagement.

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
- [ ] Nginx or existing reverse proxy in front with valid TLS cert
- [ ] MinIO port 9001 not exposed publicly
- [ ] MinIO object lock (WORM) enabled on `audit-archive` bucket
- [ ] Firewall: only ports 80/443 open externally
- [ ] Backups configured for PostgreSQL volume (`pgdata`)
- [ ] `ALLOW_RFC1918=false` unless explicitly needed for internal testing

Security controls active in all environments:

- Argon2id password hashing (64 MB RAM, 3 iterations, 4 lanes)
- 5-failure brute-force lockout per username+IP per 15 minutes
- Rotating refresh tokens (httpOnly, Secure, SameSite=Strict)
- AES-256-GCM field encryption for sensitive data (MFA secrets)
- Hash-chained audit log -- tamper detection via `GET /api/audit/verify`
- `X-Frame-Options: DENY`, CSP, `X-Content-Type-Options` on all responses
- Rate limiting via slowapi (100 req/min general, 10 req/min auth)
- Scope hard-blocks enforced before any tool execution

---

## Project Phases

| Phase | Status | Scope |
|-------|--------|-------|
| **1** | Done | Scaffold, auth, RBAC, hash-chained audit log, docker-compose |
| **2** | Done | Engagement + scope models, plugin manifest, orchestrator core, WebSocket |
| **3** | Done | Passive + active recon plugins (9 passive, 4 active) |
| **4** | Done | Web + network + cloud testing plugins, evidence screenshots |
| **5** | Planned | CVE correlation (NVD/OSV/CISA KEV/EPSS), CVSS/EPSS, PDF/HTML/SARIF reporting |
| **6** | Planned | SBOM (Syft/Grype), cosign signing, SLSA provenance, Helm chart |
| **7** | Planned | E2E tests vs Juice Shop + DVWA, CHANGELOG.md, v0.1.0 release |

---

## License

[AGPLv3](LICENSE) -- if you run a modified version as a network service, you must publish your source.
