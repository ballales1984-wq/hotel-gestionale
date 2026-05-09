"""
Hotel ABC Platform — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.db.database import create_tables
from app.api.v1 import router as api_v1_router

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestisce il ciclo di vita dell'app (startup/shutdown)."""
    logger.info("🏨 Hotel ABC Platform avviato — %s", settings.environment)
    if settings.environment == "development":
        await create_tables()
        logger.info("Tabelle DB sincronizzate (dev mode)")
    yield
    logger.info("Hotel ABC Platform in spegnimento...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Piattaforma decisionale Activity-Based Costing per hotel multiservizio. "
            "Calcola costi, margini e redditività per servizio con logica ABC."
        ),
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],  # Personalizzare con i domini reali
        )

    # ── Prometheus metrics ─────────────────────────────────────────────────
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # ── Routers ────────────────────────────────────────────────────────────
    app.include_router(api_v1_router, prefix="/api/v1")

    # ── Health check ───────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    async def health_check():
        return {
            "status": "ok",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    return app


app = create_app()
