import os
from dataclasses import dataclass, field


def _cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "HOA AI Assistant")
    api_title: str = os.getenv("API_TITLE", "HOA AI Assistant API")
    environment: str = os.getenv("ENVIRONMENT", "development")
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = field(default_factory=_cors_origins)
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://hoa:hoa_dev_password@localhost:5432/hoa",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
    firebase_storage_bucket: str = os.getenv(
        "FIREBASE_STORAGE_BUCKET",
        "your-project-id.firebasestorage.app",
    )


settings = Settings()
