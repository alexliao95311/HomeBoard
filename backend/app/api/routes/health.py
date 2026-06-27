from datetime import UTC, datetime

from fastapi import APIRouter

from app.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
    )
