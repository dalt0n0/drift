#!/usr/bin/env bash
# Drift -- first-run setup script
# Run from the project root: bash scripts/setup.sh
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

info()  { echo -e "${GREEN}[+]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
step()  { echo -e "${CYAN}[>]${RESET} $*"; }
fatal() { echo -e "${RED}[x]${RESET} $*"; exit 1; }

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║         Drift  —  Setup              ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════╝${RESET}"
echo ""

# ── OS detection ──────────────────────────────────────────────────────────────
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "${ID}"
    elif command -v uname >/dev/null 2>&1; then
        uname -s | tr '[:upper:]' '[:lower:]'
    else
        echo "unknown"
    fi
}

OS=$(detect_os)
ARCH=$(uname -m)

info "Detected OS: ${OS} (${ARCH})"

# ── Install Docker ────────────────────────────────────────────────────────────
install_docker() {
    step "Installing Docker Engine..."

    case "${OS}" in
        ubuntu|debian|linuxmint|pop|kali|parrot)
            # Official Docker apt repository
            apt-get update -qq
            apt-get install -y -qq ca-certificates curl gnupg lsb-release

            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/${OS}/gpg \
                | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || \
            # Fallback: use debian key for derivatives that share repos
            curl -fsSL https://download.docker.com/linux/debian/gpg \
                | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg

            # Determine the codename — use UBUNTU_CODENAME or VERSION_CODENAME
            CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-$(lsb_release -cs)}}"
            # Kali and some derivatives don't have Docker packages; use debian stable
            if [[ "${OS}" == "kali" || "${OS}" == "parrot" ]]; then
                CODENAME="bookworm"
                REPO_OS="debian"
            else
                REPO_OS="${OS}"
            fi

            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
              https://download.docker.com/linux/${REPO_OS} ${CODENAME} stable" \
              > /etc/apt/sources.list.d/docker.list

            apt-get update -qq
            apt-get install -y -qq \
                docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;

        fedora)
            dnf -y -q install dnf-plugins-core
            dnf config-manager --add-repo \
                https://download.docker.com/linux/fedora/docker-ce.repo
            dnf -y -q install docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;

        centos|rhel|rocky|almalinux)
            yum install -y -q yum-utils
            yum-config-manager --add-repo \
                https://download.docker.com/linux/centos/docker-ce.repo
            yum install -y -q docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;

        arch|manjaro|endeavouros)
            pacman -Sy --noconfirm docker docker-compose
            ;;

        opensuse*|sles)
            zypper -q install -y docker docker-compose
            ;;

        darwin)
            fatal "macOS detected. Please install Docker Desktop manually: https://docs.docker.com/desktop/mac/install/"
            ;;

        *)
            warn "Unknown OS '${OS}'. Attempting generic install via get.docker.com..."
            curl -fsSL https://get.docker.com | sh
            ;;
    esac

    # Enable and start Docker
    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable docker --now 2>/dev/null || true
    fi

    info "Docker installed: $(docker --version)"
}

install_docker_compose_standalone() {
    # Fallback: install docker-compose v2 standalone binary if plugin not present
    step "Installing Docker Compose standalone plugin..."
    COMPOSE_VERSION=$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest \
        | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/')
    COMPOSE_URL="https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)"
    curl -fsSL "${COMPOSE_URL}" -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    info "Docker Compose installed: $(docker compose version)"
}

add_user_to_docker_group() {
    # Add invoking user (not root) to the docker group
    local invoking_user="${SUDO_USER:-${USER:-}}"
    if [[ -n "${invoking_user}" && "${invoking_user}" != "root" ]]; then
        if ! groups "${invoking_user}" 2>/dev/null | grep -q docker; then
            usermod -aG docker "${invoking_user}"
            warn "Added '${invoking_user}' to the docker group."
            warn "You may need to log out and back in for this to take effect,"
            warn "or run: newgrp docker"
        fi
    fi
}

# ── Check / install Docker ────────────────────────────────────────────────────
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    info "Docker already installed: $(docker --version)"
    info "Docker Compose: $(docker compose version)"
else
    if [[ "${EUID}" -ne 0 ]]; then
        warn "Docker not found. Re-run with sudo to install automatically:"
        warn "  sudo bash scripts/setup.sh"
        fatal "Docker is required. Install it first: https://docs.docker.com/get-docker/"
    fi

    install_docker

    # Verify compose plugin; install standalone if missing
    if ! docker compose version >/dev/null 2>&1; then
        mkdir -p /usr/local/lib/docker/cli-plugins
        install_docker_compose_standalone
    fi

    add_user_to_docker_group
fi

# ── Check python3 (needed for secret generation) ─────────────────────────────
command -v python3 >/dev/null 2>&1 || fatal "python3 not found. Install python3 and re-run."
command -v openssl >/dev/null 2>&1 || fatal "openssl not found. Install openssl and re-run."

info "Docker: $(docker --version)"

# ── Alias for all compose commands ───────────────────────────────────────────
DC="docker compose -f deploy/docker-compose.yml --env-file .env"

# ── Generate .env ─────────────────────────────────────────────────────────────
if [[ -f "$ROOT_DIR/.env" ]]; then
    warn ".env already exists — skipping generation. Delete it and re-run to regenerate."
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
info "Building Docker images (this will take a few minutes on first run)..."
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
$DC run --rm api python3 - <<PYEOF 2>/dev/null || warn "Admin user may already exist — skipping."
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

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║             Drift is running!                    ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  API:           ${CYAN}http://${HOST_IP}:8000${RESET}"
echo -e "  Health check:  ${CYAN}http://${HOST_IP}:8000/api/health${RESET}"
echo -e "  MinIO console: ${CYAN}http://${HOST_IP}:9001${RESET}"
echo ""
echo -e "  Username: ${BOLD}admin${RESET}"
echo -e "  Password: ${BOLD}${ADMIN_PASS}${RESET}"
echo ""
warn "Save that password — it won't be shown again."
warn "For production: set ENVIRONMENT=production and ALLOWED_ORIGINS in .env"
warn "For production: put a reverse proxy with TLS in front."
echo ""
