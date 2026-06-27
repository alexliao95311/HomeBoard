from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        description="API for HOA document, contract, and financial review workflows.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_prefix)

    @application.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "status": "running",
            "docs": "/docs",
        }

    return application


app = create_app()
