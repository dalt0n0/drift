#!/usr/bin/env bash
# Reset (or create) the admin user and print a new random password.
# Run from the project root: bash scripts/reset-admin.sh
set -euo pipefail

cd "$(dirname "$0")/.."

DC="docker compose -f deploy/docker-compose.yml --env-file .env"

NEW_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 18)

$DC run --rm api python3 << PYEOF
import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.username == "admin"))
        user = r.scalar_one_or_none()
        if user:
            user.hashed_password = hash_password("${NEW_PASS}")
            user.must_change_password = True
            user.is_active = True
            print("Admin password reset.")
        else:
            db.add(User(
                username="admin",
                email="admin@drift.local",
                full_name="Admin User",
                role="admin",
                hashed_password=hash_password("${NEW_PASS}"),
                is_active=True,
                must_change_password=True,
            ))
            print("Admin user created.")
        await db.commit()

asyncio.run(main())
PYEOF

echo ""
echo "  Username: admin"
echo "  Password: ${NEW_PASS}"
echo ""
echo "You will be prompted to change this password on first login."
