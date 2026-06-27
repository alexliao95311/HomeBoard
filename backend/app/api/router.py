from fastapi import APIRouter

from app.api.routes import auth, contracts, documents, financials, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(financials.router, prefix="/financials", tags=["financials"])
