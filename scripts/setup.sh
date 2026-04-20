#!/usr/bin/env bash
# Drift -- first-run setup script
# Run from the project root: bash scripts/setup.sh
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

info()  { echo -e "${GREEN}[+]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
fatal() { echo -e "${RED}[x]${RESET} $*"; exit 1; }

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"

echo ""
echo -e "${BOLD}Drift -- Setup${RESET}"
echo ""

# Alias: every compose command uses --env-file so vars are found at project root
DC="docker compose -f deploy/docker-compose.yml --env-file .env"

# ── Check dependencies ────────────────────────────────────────────────────────
command -v docker  >/dev/null 2>&1 || fatal "Docker not found. Install: https://docs.docker.com/get-docker/"
command -v python3 >/dev/null 2>&1 || fatal "python3 not found."
docker compose version >/dev/null 2>&1 || fatal "Docker Compose v2 not found."
info "Docker: $(docker --version)"

# ── Generate .env ─────────────────────────────────────────────────────────────
if [[ -f "$ROOT_DIR/.env" ]]; then
    warn ".env already exists -- skipping generation. Delete it and re-run to regenerate."
else
    info "Generating .env with auto-generated secrets..."

    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 64)
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    MINIO_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    VAULT_KEY=$(python3 -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

    cat > "$ROOT_DIR/.env" <<ENVEOF
SECRET_KEY=${SECRET_KEY}
JWT_SECRET=${JWT_SECRET}
ENVIRONMENT=development
DEBUG=false
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,http://localhost:8000
OPEN_REGISTRATION=false

DATABASE_URL=postgresql+asyncpg://drift:${POSTGRES_PASSWORD}@db:5432/drift
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
REDIS_PASSWORD=${REDIS_PASSWORD}

MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=drift
MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
MINIO_BUCKET_ARTIFACTS=artifacts
MINIO_BUCKET_REPORTS=reports
MINIO_BUCKET_AUDIT=audit-archive
MINIO_SECURE=false

VAULT_MASTER_KEY=${VAULT_KEY}

AUDIT_LOG_PATH=/var/drift/audit/audit.jsonl
AUDIT_RETENTION_DAYS=365

CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/2
ENVEOF

    info ".env generated."
    warn "Edit .env to set ALLOWED_ORIGINS and ENVIRONMENT=production before going live."
fi

# ── Build images ──────────────────────────────────────────────────────────────
info "Building Docker images..."
$DC build

# ── Start DB + Redis + MinIO first ────────────────────────────────────────────
info "Starting database, Redis, and MinIO..."
$DC up -d db redis minio

info "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
    if $DC exec -T db pg_isready -U drift >/dev/null 2>&1; then
        info "PostgreSQL ready."
        break
    fi
    if [[ $i -eq 30 ]]; then
        fatal "PostgreSQL did not become ready in time. Check: $DC logs db"
    fi
    sleep 2
done

# ── Run migrations ────────────────────────────────────────────────────────────
info "Running database migrations..."
$DC run --rm api alembic upgrade head

# ── Create admin user ─────────────────────────────────────────────────────────
ADMIN_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 16)

info "Creating initial admin user..."
$DC run --rm api python3 - <<PYEOF 2>/dev/null || warn "Admin user may already exist -- skipping."
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
            hashed_password=hash_password("${ADMIN_PASS}"),
            is_active=True,
        )
        db.add(u)
        await db.commit()

asyncio.run(main())
PYEOF

# ── Start all services ────────────────────────────────────────────────────────
info "Starting all services..."
$DC up -d

echo ""
echo "================================================="
echo " Drift is running!"
echo "================================================="
echo ""
echo "  API:           http://$(hostname -I | awk '{print $1}'):8000"
echo "  Health check:  http://$(hostname -I | awk '{print $1}'):8000/api/health"
echo "  MinIO console: http://$(hostname -I | awk '{print $1}'):9001"
echo ""
echo "  Username: admin"
echo "  Password: ${ADMIN_PASS}"
echo ""
warn "Save that password -- it won't be shown again."
warn "For production: set ENVIRONMENT=production and ALLOWED_ORIGINS in .env"
warn "For production: put nginx in front with a real TLS cert."
echo ""
