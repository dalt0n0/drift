#!/usr/bin/env bash
# Drift â€” first-run setup script
# Run from the project root: bash scripts/setup.sh
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

info()  { echo -e "${GREEN}[+]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
fatal() { echo -e "${RED}[âœ—]${RESET} $*"; exit 1; }

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"

echo ""
echo -e "${BOLD}Drift â€” Setup${RESET}"
echo ""

# â”€â”€ Check dependencies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
command -v docker  >/dev/null 2>&1 || fatal "Docker not found. Install from https://docs.docker.com/get-docker/"
command -v python3 >/dev/null 2>&1 || fatal "python3 not found."
docker compose version >/dev/null 2>&1 || fatal "Docker Compose v2 not found."
info "Docker: $(docker --version)"

# â”€â”€ Generate .env â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if [[ -f "$ROOT_DIR/.env" ]]; then
    warn ".env already exists â€” skipping generation. Delete it and re-run to regenerate."
else
    info "Generating .env with auto-generated secrets..."

    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 64)
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    MINIO_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    VAULT_KEY=$(python3 -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

    cat > "$ROOT_DIR/.env" <<ENVEOF
# â”€â”€ App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SECRET_KEY=${SECRET_KEY}
JWT_SECRET=${JWT_SECRET}
ENVIRONMENT=development
DEBUG=false
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,http://localhost:8000
OPEN_REGISTRATION=false

# â”€â”€ Database â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DATABASE_URL=postgresql+asyncpg://drift:${POSTGRES_PASSWORD}@db:5432/drift
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# â”€â”€ Redis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
REDIS_PASSWORD=${REDIS_PASSWORD}

# â”€â”€ MinIO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=drift
MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
MINIO_BUCKET_ARTIFACTS=artifacts
MINIO_BUCKET_REPORTS=reports
MINIO_BUCKET_AUDIT=audit-archive
MINIO_SECURE=false

# â”€â”€ Vault / field encryption â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
VAULT_MASTER_KEY=${VAULT_KEY}

# â”€â”€ Audit log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
AUDIT_LOG_PATH=/var/drift/audit/audit.jsonl
AUDIT_RETENTION_DAYS=365

# â”€â”€ Celery â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/2
ENVEOF

    info ".env generated."
    warn "Edit .env to set ALLOWED_ORIGINS and ENVIRONMENT=production before going live."
fi

# â”€â”€ Build images â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Building Docker images..."
docker compose -f deploy/docker-compose.yml build

# â”€â”€ Start DB + Redis first â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Starting database and Redis..."
docker compose -f deploy/docker-compose.yml up -d db redis minio

info "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
    if docker compose -f deploy/docker-compose.yml exec -T db pg_isready -U drift >/dev/null 2>&1; then
        info "PostgreSQL ready."
        break
    fi
    if [[ $i -eq 30 ]]; then
        fatal "PostgreSQL did not become ready in time."
    fi
    sleep 2
done

# â”€â”€ Run migrations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Running database migrations..."
docker compose -f deploy/docker-compose.yml run --rm api alembic upgrade head

# â”€â”€ Create admin user â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ADMIN_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 16)

info "Creating initial admin user..."
docker compose -f deploy/docker-compose.yml run --rm api python3 - <<PYEOF 2>/dev/null || warn "Admin user may already exist â€” skipping."
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

# â”€â”€ Start all services â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Starting all services..."
docker compose -f deploy/docker-compose.yml up -d

echo ""
echo -e "${BOLD}${GREEN}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${RESET}"
echo -e "${BOLD} Drift is running!${RESET}"
echo -e "${BOLD}${GREEN}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${RESET}"
echo ""
echo "  API:          http://$(hostname -I | awk '{print $1}'):8000"
echo "  Health:       http://$(hostname -I | awk '{print $1}'):8000/api/health"
echo "  MinIO console: http://$(hostname -I | awk '{print $1}'):9001"
echo ""
echo "  Username: admin"
echo "  Password: ${ADMIN_PASS}"
echo ""
warn "Save that password â€” it won't be shown again."
warn "For production: set ENVIRONMENT=production and ALLOWED_ORIGINS in .env"
warn "For production: put nginx in front with a real TLS cert."
echo ""
