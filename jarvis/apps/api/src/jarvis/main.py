"""ASGI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jarvis.api.routes import router
from jarvis.config import Settings, get_settings
from jarvis.kernel import container
from jarvis.kernel.errors import JarvisError
from jarvis.observability.logging import configure_logging

log = structlog.get_logger(__name__)


def create_app(
    settings: Settings | None = None, *, jarvis: container.Jarvis | None = None
) -> FastAPI:
    """Build the ASGI app.

    ``jarvis`` lets a caller inject an already-assembled system — tests use it
    to run the real routes against offline providers and a frozen clock.
    """
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        system = jarvis or container.build(settings)
        app.state.jarvis = system
        await system.start()
        system.bus.publish(
            "system.started",
            {"environment": settings.environment, "storage": system.storage},
        )
        log.info("api_ready", environment=settings.environment, storage=system.storage)
        yield
        system.bus.publish("system.stopping", {})
        await system.stop()

    app = FastAPI(
        title="Jarvis",
        version="0.1.0",
        summary="Personal AI operating system",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(JarvisError)
    async def handle_jarvis_error(_: Request, exc: JarvisError) -> JSONResponse:
        # One place where the error taxonomy becomes HTTP status codes.
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": type(exc).__name__, "message": str(exc)},
        )

    app.include_router(router)
    return app


app = create_app()
