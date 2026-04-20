# Drift Architecture

## Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Client (Browser)                    │
│              React SPA (index.html, CDN libs)            │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS / WSS
┌───────────────────────▼─────────────────────────────────┐
│                  Nginx (TLS termination)                  │
│           Rate limiting · Security headers                │
└────────────┬───────────────────────┬────────────────────┘
             │ /api/*                │ /ws/*
┌────────────▼────────────┐  ┌───────▼─────────────────────┐
│   FastAPI (Uvicorn)      │  │  WebSocket Handler           │
│   Auth · RBAC · Audit    │  │  Real-time scan output       │
│   Engagements · Findings │  └─────────────────────────────┘
│   Reports · Vault        │
└────────┬────────┬────────┘
         │        │
┌────────▼──┐  ┌──▼──────────┐
│ PostgreSQL │  │    Redis     │
│  (primary  │  │  (cache +   │
│   store)   │  │  task queue)│
└────────────┘  └─────────────┘
                      │
┌─────────────────────▼──────────────────────────────────┐
│              Celery Workers                             │
│  Passive Recon · Active Scan · Web Test · Network Test │
│  Each plugin: subprocess wrapper + result parser        │
└─────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────┐
│                   MinIO (S3)                            │
│  Artifacts · Evidence · Reports · Audit Archive         │
└─────────────────────────────────────────────────────────┘
```

## Phase Roadmap

| Phase | Scope |
|-------|-------|
| 1 (current) | Scaffold, auth, RBAC, audit log, API skeleton |
| 2 | Engagement/scope models, plugin manifest, orchestrator core |
| 3 | Passive + active recon (Subfinder, Amass, Nmap, httpx) |
| 4 | Web + network testing (Nuclei, ZAP, ffuf, NetExec) |
| 5 | CVE correlation, CVSS/EPSS, PDF/HTML/SARIF reporting |
| 6 | SBOM, cosign signing, SLSA provenance, Helm chart |
| 7 | E2E tests vs Juice Shop + DVWA, v0.1.0 release |

## Security Architecture

### Authentication Flow
1. POST /api/auth/login → verify Argon2id hash → check MFA → issue JWT (15min) + refresh cookie (30d)
2. Refresh cookie: httpOnly, Secure, SameSite=Strict, path=/api/auth
3. Refresh rotation: old token revoked on every /refresh call
4. API keys: drk_ prefix, SHA-256 stored, prefix shown in UI

### Audit Log Chain
Every write acquires a SELECT FOR UPDATE lock on the last row, computes SHA-256(prev_canonical_json), stores as chain_hash. Tamper detection: recompute all hashes in order; any mismatch = tamper detected.

### Network Isolation
- PostgreSQL + Redis on internal Docker network (not reachable externally)
- API + Nginx on external network
- Celery workers on internal + tools network
