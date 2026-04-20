#!/usr/bin/env bash
# Drift -- pull latest and restart
set -euo pipefail

cd "$(dirname "$0")/.."

DC="docker compose -f deploy/docker-compose.yml --env-file .env"

echo "[+] Pulling latest..."
git pull

echo "[+] Rebuilding API image..."
$DC build api

echo "[+] Running migrations..."
$DC run --rm api alembic upgrade head

echo "[+] Restarting..."
$DC up -d

echo "[+] Done."
