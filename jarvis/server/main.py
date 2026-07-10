"""JARVIS application entrypoint.

Creates the FastAPI app, wires routers, initializes the database, starts
the automation engine, and serves the single-page dashboard UI.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .automation.scheduler import engine
from .config import settings
from .db import init_db
from .tools import core_tools  # noqa: F401 — registers built-in tools on import
from .tools import live_tools  # noqa: F401 — weather + news
from .tools import connected_tools  # noqa: F401 — calendar/spotify/gmail

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("jarvis")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    engine.start()
    log.info("JARVIS %s started on %s:%s", settings.version, settings.host, settings.port)
    yield
    await engine.stop()


app = FastAPI(title="JARVIS AI Operating System", version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from .api import (  # noqa: E402
    agent_routes, analytics_routes, auth_routes, chat_routes, connection_routes,
    memory_routes, project_routes, voice_routes, workflow_routes,
)

for module in (
    auth_routes, chat_routes, agent_routes, memory_routes,
    project_routes, workflow_routes, voice_routes, analytics_routes,
    connection_routes,
):
    app.include_router(module.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.version}


@app.exception_handler(500)
async def internal_error(_request, exc):  # pragma: no cover - safety net
    log.exception("unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Serve the SPA. Static assets under /web, index for the app shell.
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(WEB_DIR / "index.html"))


def run() -> None:
    import uvicorn

    uvicorn.run("server.main:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    run()
