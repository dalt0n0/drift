#!/usr/bin/env bash
# Run the Drift E2E test suite against live Juice Shop + DVWA targets.
# Usage:
#   bash scripts/run-e2e.sh [--rebuild] [--admin-pass <pass>]
#
# Options:
#   --rebuild      Rebuild images before starting (adds --build to docker compose up)
#   --admin-pass   Admin password set during setup.sh (default: read from .env.e2e)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

REBUILD=false
ADMIN_PASS="${DRIFT_ADMIN_PASS:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rebuild) REBUILD=true; shift ;;
        --admin-pass) ADMIN_PASS="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

DC_MAIN="docker compose -f deploy/docker-compose.yml --env-file .env"
DC_E2E="docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.e2e.yml --env-file .env"

echo "[>] Starting Drift stack + E2E targets..."
if [[ "${REBUILD}" == "true" ]]; then
    $DC_E2E up -d --build
else
    $DC_E2E up -d
fi

echo "[>] Running E2E test suite..."
export DRIFT_API_URL="http://localhost:8000"
export DRIFT_ADMIN_PASS="${ADMIN_PASS}"
export JUICESHOP_URL="http://localhost:3180"
export DVWA_URL="http://localhost:3181"

cd "${ROOT}/backend"
python3 -m pytest tests/e2e -m e2e -v --tb=short "$@"
E2E_EXIT=$?

echo ""
if [[ $E2E_EXIT -eq 0 ]]; then
    echo "[+] E2E suite passed."
else
    echo "[!] E2E suite had failures. Check output above."
    echo "[!] Container logs: docker compose -f deploy/docker-compose.e2e.yml logs"
fi

exit $E2E_EXIT
