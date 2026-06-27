from fastapi import APIRouter

from app.schemas.module import ModuleStatus

router = APIRouter()


@router.get("/status", response_model=ModuleStatus)
async def contract_module_status() -> ModuleStatus:
    return ModuleStatus(
        module="Contract review",
        status="planned",
        message="Contract analysis and vendor comparison will be added in Phase 3.",
    )
