#!/usr/bin/env bash
# Drift — pull latest and restart
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[+] Pulling latest..."
git pull

echo "[+] Rebuilding API image..."
docker compose -f deploy/docker-compose.yml build api

echo "[+] Running migrations..."
docker compose -f deploy/docker-compose.yml run --rm api alembic upgrade head

echo "[+] Restarting..."
docker compose -f deploy/docker-compose.yml up -d

echo "[+] Done."
