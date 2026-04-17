from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.deps import CurrentUser, DB
from app.core.permissions import require_role
from app.config import settings as app_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class WorkspaceInfo(BaseModel):
    instance_name: str
    host: str
    environment: str
    version: str = "1.8.2"


@router.get("")
async def get_settings(user: CurrentUser) -> dict:
    require_role(user.role, "lead")
    return {
        "instance_name": app_settings.INSTANCE_NAME,
        "host": app_settings.DRIFT_HOST,
        "environment": app_settings.ENVIRONMENT,
        "version": "1.8.2",
        "smtp_configured": bool(app_settings.SMTP_USER),
    }
