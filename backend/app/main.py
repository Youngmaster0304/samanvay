"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conflicts, georef, health, matching, sources
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.policy import PolicyError, get_policy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    try:
        bundle = get_policy(settings.policy_path)
    except PolicyError as exc:
        raise RuntimeError(f"refusing to start: {exc}") from exc
    logger.info("loaded policy %s v%s from %s", bundle.name, bundle.version, bundle.path)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="Samanvay API",
        version=settings.app_version,
        description=(
            "Harmonization engine for multi-source urban land records. "
            "Prototype for Smart India Hackathon 2026, problem statement 26013."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.web_origin.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(georef.router)
    app.include_router(conflicts.router)
    app.include_router(matching.router)
    return app


app = create_app()
