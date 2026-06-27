from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.config import settings
from app.database import engine, verify_database_connection


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    verify_database_connection()
    yield
    engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.api_title,
        description="API for HOA document, contract, and financial review workflows.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(api_router, prefix=settings.api_prefix)

    @application.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.api_title,
            "status": "running",
            "docs": "/docs",
        }

    return application


app = create_app()
