from fastapi import APIRouter

from app.api.routes import contracts, documents, financials, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(financials.router, prefix="/financials", tags=["financials"])
