# Software Bill of Materials (SBOM)

## Overview

ReconStrike generates CycloneDX 1.5 and SPDX 2.3 SBOMs for:
1. The ReconStrike application (Python deps + OS packages)
2. Each Docker image (via Syft)
3. Per-engagement run metadata (tool versions used)

**Phase 6 deliverable** — this document describes the planned implementation.

## Endpoints

- `GET /api/sbom` — returns current application SBOM (CycloneDX JSON)
- `GET /api/sbom/image` — returns Docker image SBOM

## Generation

```bash
# Application SBOM
syft dir:backend -o cyclonedx-json > sbom-app.cdx.json
syft dir:backend -o spdx-json > sbom-app.spdx.json

# Docker image SBOM
syft reconstrike:latest -o cyclonedx-json > sbom-image.cdx.json

# Vulnerability scan
grype sbom:sbom-app.cdx.json --fail-on high
```

## Signing (Phase 6)

```bash
cosign sign --key cosign.key reconstrike:latest
cosign verify --key cosign.pub reconstrike:latest
```

## CI Integration

Every release:
1. Generate SBOMs with Syft
2. Scan with Grype (fail on HIGH/CRITICAL)
3. Sign image with cosign (Sigstore)
4. Publish SLSA provenance
5. Attach SBOM as release artifact
