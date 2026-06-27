from fastapi import APIRouter

from app.schemas.module import ModuleStatus

router = APIRouter()


@router.get("/status", response_model=ModuleStatus)
async def financial_module_status() -> ModuleStatus:
    return ModuleStatus(
        module="Financial oversight",
        status="planned",
        message="Transaction ingestion and financial reporting will be added in Phase 4.",
    )
