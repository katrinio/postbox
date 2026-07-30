from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from postbox.config import WebSettings
from postbox.database import Database
from postbox.logging import configure_logging
from postbox.views import register_web


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Set cache headers for HTML and static assets."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # HTML responses: no-cache (check with server every time)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Static files with version query param: aggressive cache
        # (URL changes with static_version, so this is safe for long periods)
        if request.url.path.startswith("/static/") and "v=" in str(request.url.query):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

        return response


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as session:
        yield session


def create_app(settings: WebSettings | None = None) -> FastAPI:
    web_settings = settings or WebSettings.from_env()
    configure_logging(web_settings.log_level)
    database = Database(web_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = database
        app.state.web_settings = web_settings

        if web_settings.auto_create_tables:
            from postbox.database.base import Base

            async with database.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        yield
        await database.dispose()

    app = FastAPI(
        title="Postbox",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(CacheControlMiddleware)

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness check: confirms process is running."""
        return HealthResponse()

    @app.get("/api/ready", response_model=HealthResponse)
    async def ready(session: Annotated[AsyncSession, Depends(database_session)]) -> HealthResponse:
        """Readiness check: confirms database is accessible."""
        try:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
            return HealthResponse()
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not ready",
            ) from error

    register_web(app)

    return app


def run() -> None:
    import os

    host = os.getenv("POSTBOX_API_HOST", "127.0.0.1")
    port = int(os.getenv("POSTBOX_API_PORT", "8000"))
    reload = os.getenv("POSTBOX_API_RELOAD", "false").lower() == "true"

    uvicorn.run(
        "postbox.api:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )
