import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette import status
from starlette.middleware.trustedhost import TrustedHostMiddleware

from loguru import logger

from degas_api import __version__, middlewares
from degas_api.settings import app_settings
from degas_api.log_config import configure_logging
from degas_api.routers import api_router
from degas_api.lifespan import create_lifespan

type AppLifespan = Callable[[FastAPI], AbstractAsyncContextManager[Any]]


def create_app(
    routers: list[tuple[APIRouter, dict]] = [(api_router, {})],
    lifespan: AppLifespan = create_lifespan(
        host=app_settings.host, port=app_settings.port
    ),
    docs_url: str = app_settings.docs_url,
) -> FastAPI:
    """Create a FastAPI app with the given routers."""
    from degas_api.docs.api import (
        FASTAPI_DESCRIPTION,
        FASTAPI_SUMMARY,
        FASTAPI_TITLE,
    )

    configure_logging(level=app_settings.logging.level)

    app = FastAPI(
        docs_url=docs_url,
        version=__version__,
        title=FASTAPI_TITLE,
        description=FASTAPI_DESCRIPTION,
        summary=FASTAPI_SUMMARY,
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or request.headers.get(
            "DeGAS-Request-Id"
        )
        logger.opt(exception=True).error(
            "Unhandled exception (request_id={})", request_id
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error", "request_id": request_id},
            media_type="application/json; charset=utf-8",
        )

    # Reject requests whose Host header isn't in the allowlist.
    # Must be added before other middleware so scanners are dropped early.
    if app_settings.allowed_hosts != ["*"]:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=app_settings.allowed_hosts,
        )

    app.middleware("http")(middlewares.logging_context_middleware())
    app.middleware("http")(middlewares.add_request_id_header)
    app.middleware("http")(middlewares.api_version_middleware(__version__))
    app.middleware("http")(middlewares.add_request_duration_header)
    app.middleware("http")(middlewares.add_security_headers)

    for router, options in routers:
        app.include_router(router, **options)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, object]:
        limiter = getattr(app.state, "orl_limiter", None)
        max_concurrent = app_settings.optimization_limits.max_concurrent_runs
        slots_free = (
            await limiter.slots_free() if limiter is not None else max_concurrent
        )
        return {
            "unix": time.time(),
            "slots_free": slots_free,
            "max_concurrent": max_concurrent,
        }

    static_dir = Path(app_settings.static_dir) if app_settings.static_dir else None
    if static_dir is not None and static_dir.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(static_dir / "index.html")

    else:

        @app.get("/", tags=["root"])
        async def redirect_to_docs_root():
            logger.debug("Redirecting to docs")
            return RedirectResponse(url=docs_url)

    return app
