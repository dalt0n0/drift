# ReconStrike

> **For authorized penetration testing engagements only.**
> Using this tool against systems you do not have written permission to test is illegal.

Open-source, web-based automated penetration testing platform.

## Architecture

- **Backend**: FastAPI (Python 3.11+), async SQLAlchemy 2.x
- **Queue**: Celery + Redis
- **DB**: PostgreSQL 16
- **Storage**: MinIO (S3-compatible)
- **Auth**: JWT + refresh tokens, TOTP MFA, RBAC (5 roles)
- **Audit**: Hash-chained tamper-evident audit log (SOC 2 aligned)

## Quickstart (Docker Compose)

```bash
git clone https://github.com/dalt0n0/reconstrike
cd reconstrike
cp .env.example .env
# Edit .env — set all CHANGE_ME values
# Generate secrets:
#   SECRET_KEY:      openssl rand -hex 32
#   JWT_SECRET:      openssl rand -hex 64
#   VAULT_MASTER_KEY: python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

docker compose -f deploy/docker-compose.yml up -d

# Run migrations
docker compose -f deploy/docker-compose.yml exec api alembic upgrade head

# Create first admin user
docker compose -f deploy/docker-compose.yml exec api python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password

async def main():
    async with AsyncSessionLocal() as db:
        u = User(username='admin', email='admin@reconstrike.local',
                 full_name='Admin', role='admin',
                 hashed_password=hash_password('ChangeMe123!'))
        db.add(u)
        await db.commit()
        print('Admin created')

asyncio.run(main())
"
```

API: http://localhost:8000/api/health
MinIO console: http://localhost:9001

## Development

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml up
```

Swagger UI (debug only): http://localhost:8000/api/docs

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v --cov=app
```

## Roles

| Role | Description |
|------|-------------|
| admin | Full access |
| lead | Manage team, view all engagements |
| tester | Create and run scans |
| viewer | Read-only on all findings |
| client_readonly | Redacted client portal view |

## License

AGPLv3 — see [LICENSE](LICENSE)
