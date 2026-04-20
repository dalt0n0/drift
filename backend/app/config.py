from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Drift"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    SECRET_KEY: str = "CHANGE_ME_32_BYTE_HEX_SECRET_KEY_HERE"
    JWT_SECRET: str = "CHANGE_ME_64_BYTE_HEX_JWT_SECRET_HERE_LONGER"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://drift:changeme@db:5432/drift"

    # Redis
    REDIS_URL: str = "redis://:changeme@redis:6379/0"

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ROOT_USER: str = "drift"
    MINIO_ROOT_PASSWORD: str = "CHANGE_ME"
    MINIO_BUCKET_ARTIFACTS: str = "artifacts"
    MINIO_BUCKET_REPORTS: str = "reports"
    MINIO_BUCKET_AUDIT: str = "audit-archive"
    MINIO_SECURE: bool = False

    # Encryption
    VAULT_MASTER_KEY: str = "CHANGE_ME_FERNET_KEY_BASE64_32_BYTES"

    # Audit log
    AUDIT_LOG_PATH: str = "/var/drift/audit/audit.jsonl"
    AUDIT_RETENTION_DAYS: int = 365

    # Celery
    CELERY_BROKER_URL: str = "redis://:changeme@redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://:changeme@redis:6379/2"

    # Registration
    OPEN_REGISTRATION: bool = False

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
