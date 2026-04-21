# Changelog

All notable changes to Drift are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/); versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-04-21

### Added

#### Core platform
- FastAPI backend with async SQLAlchemy 2.x, PostgreSQL 16, Redis 7, Celery 5, MinIO object storage
- JWT + refresh-token auth, RBAC (admin / operator / viewer), API key support
- Hash-chained tamper-evident audit log with JSONL storage and configurable retention
- Rate limiting via slowapi; `X-Request-ID`, security headers middleware
- WebSocket real-time feed per engagement (JWT-authenticated, Redis pub/sub)

#### Engagements & scope
- Engagement lifecycle (draft → active → completed → archived)
- Scope items with per-target allow/deny rules; strict scope guard enforced on every plugin invocation
- Engagement runs with status tracking, stdout/stderr capture, artifact upload to MinIO

#### Plugin system
- Extensible plugin registry; plugins declare scope requirements and receive a sandboxed runner
- **Passive recon:** subfinder, assetfinder, dnsx, httpx, gau, waybackurls, theHarvester, Amass
- **Active recon:** nmap, masscan, naabu, RustScan, nikto, wapiti, ZAP baseline/full, testssl.sh, sslyze, gobuster, ffuf, feroxbuster, katana, nuclei
- **Network enumeration:** smbclient, smbmap, enum4linux-ng, NetExec (nxc), onesixtyone, ldap-utils
- Screenshot evidence capture via Playwright/Chromium; evidence stored in MinIO with SHA-256 digest

#### Findings & intelligence
- Finding model with severity (critical/high/medium/low/info), status, CVSS 3.1 base score
- CVE correlation against NVD; MITRE ATT&CK technique tagging
- Automated report generation (Markdown + JSON) with per-engagement artifact bundles

#### SBOM & supply-chain
- CycloneDX 1.5 and SPDX 2.3 SBOM generation from `importlib.metadata`; `/api/sbom` endpoint
- GitHub Actions CI: Syft SBOM, Grype CVE scan, cosign image signing (keyless, Sigstore), SLSA provenance via `slsa-github-generator`
- Dependabot for Python and Go dependency updates

#### Deployment
- Docker Compose stack: API, Celery worker, tools container (Kali-based), PostgreSQL, Redis, MinIO
- Helm chart (`deploy/helm/drift/`) with HPA (autoscaling/v2), PVC audit retention, CronJobs for audit integrity check and Nuclei template updates, cert-manager Ingress TLS, optional external secret support
- `scripts/setup.sh`: full out-of-box setup — auto-detects OS, installs Docker CE + Compose v2, generates secrets, runs migrations, creates admin user
- `scripts/update.sh`: pull latest images, migrate, restart

#### Documentation
- `README.md` — quickstart, env reference, API overview
- `ARCHITECTURE.md` — component diagram, data flow, security boundaries
- `THREAT_MODEL.md` — STRIDE analysis, mitigations, trust boundaries
- `SOC2_CONTROLS.md` — control mapping for CC6/CC7/CC8
- `SECURITY.md` — responsible disclosure policy
- `SBOM.md` — supply-chain transparency note
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `DISCLAIMER.md`

### Security

- `readOnlyRootFilesystem: true` on all Kubernetes containers; `emptyDir` for `/tmp`
- Kali base image apt bootstrap fixed: wipe mirror lists, bootstrap `ca-certificates` before enabling SSL peer verification, lock to `kali.download` with redirect blocking
- `libpcap-dev` + `gcc` added for CGO naabu/gopacket build

---

## [Unreleased]

- E2E test suite against OWASP Juice Shop and DVWA
- Scheduled scan support (CronJob-driven engagements)
- Nuclei custom template upload via API
- SARIF export for finding reports
- Slack / webhook notification channels

[0.1.0]: https://github.com/dalt0n0/drift/releases/tag/v0.1.0
[Unreleased]: https://github.com/dalt0n0/drift/compare/v0.1.0...HEAD
