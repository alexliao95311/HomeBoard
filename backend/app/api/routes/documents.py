from fastapi import APIRouter, status

from app.schemas.module import ModuleStatus

router = APIRouter()


@router.get("/status", response_model=ModuleStatus, status_code=status.HTTP_200_OK)
async def document_module_status() -> ModuleStatus:
    return ModuleStatus(
        module="Document management",
        status="planned",
        message="Secure upload and extraction endpoints will be added in Phase 2.",
    )
