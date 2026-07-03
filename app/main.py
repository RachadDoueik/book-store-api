"""FastAPI application factory and middleware setup."""

import logging
import time
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
import asyncio
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from sqlalchemy import text

from app.api.v1.router import api_router
from app.api.v1.routers import realtime as realtime_router
from app.core.database import engine
from app.core.config import Settings, get_settings
from app.core.inventory_cache import build_inventory_cache
from app.core.limiter import limiter
from app.core.refresh_token_store import build_refresh_token_store
from app.core.realtime import WebSocketHub

from app.core.database import AsyncSessionFactory
from app.services.embedding.service import EmbeddingService
from app.services.workers.embedding_worker import run_worker


logger = structlog.get_logger()


def _configure_logging(debug: bool) -> None:
    """Use human-readable logs in debug mode and structured JSON otherwise."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, format="%(message)s")
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _normalize_allowed_origins(allow_origins: list[str] | str, *, debug: bool) -> list[str]:
    """Parse CORS origins from env values and avoid wildcard credentials in production."""
    if isinstance(allow_origins, str):
        try:
            import json

            parsed = json.loads(allow_origins)
            if isinstance(parsed, list):
                allow_origins = parsed
            else:
                allow_origins = [origin.strip() for origin in allow_origins.split(",") if origin.strip()]
        except Exception:
            allow_origins = [origin.strip() for origin in allow_origins.split(",") if origin.strip()]

    normalized = [origin.strip() for origin in allow_origins if origin and origin.strip()]
    if normalized == ["*"] and not debug:
        logger.warning(
            "cors.wildcard_disabled",
            message="Credentialed CORS requests require explicit origins outside debug mode.",
        )
        return []
    return normalized


async def _ensure_database_ready() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _ensure_redis_ready(redis_client) -> None:
    await redis_client.ping()


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Log request duration with method, path, and status code."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "request.failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request.complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings: Settings = get_settings()
    _configure_logging(settings.DEBUG)
    # Enable Sentry error reporting when configured.
    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN)

    # Log startup and shutdown events for service visibility.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("app.startup", service=settings.APP_NAME)

        # ADD: start the embedding worker as a background task
        _embedding_db = AsyncSessionFactory()
        _embedding_service = EmbeddingService()
        _worker_task = asyncio.create_task(
            run_worker(_embedding_db, _embedding_service)
        )

        yield

        # ADD: shut the worker down gracefully
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        await _embedding_db.close()

        # your existing shutdown code stays unchanged:
        inventory_cache = getattr(app.state, "inventory_cache", None)
        if inventory_cache is not None:
            await inventory_cache.close()
        refresh_store = getattr(app.state, "refresh_token_store", None)
        if refresh_store is not None:
            await refresh_store.close()
        logger.info("app.shutdown", service=settings.APP_NAME)
        

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )
    # Store shared objects on app.state for later use.
    app.state.settings = settings
    app.state.limiter = limiter
    app.state.inventory_cache = build_inventory_cache(settings)
    app.state.refresh_token_store = build_refresh_token_store(settings)
    app.state.websocket_hub = WebSocketHub()

    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestTimingMiddleware)
    allow_origins = _normalize_allowed_origins(settings.ALLOWED_ORIGINS, debug=settings.DEBUG)

    logger.info("cors.config", allowed_origins=allow_origins)

    # Do not use a wildcard origin when credentials are enabled. Browser
    # requests that include cookies require the backend to echo an explicit
    # frontend origin instead of "*".

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/ready", tags=["health"])
    async def ready() -> dict:
        checks: dict[str, str] = {}
        errors: dict[str, str] = {}

        for name, check in (
            ("database", _ensure_database_ready),
            ("inventory_cache", lambda: _ensure_redis_ready(app.state.inventory_cache.redis)),
            ("refresh_token_store", lambda: _ensure_redis_ready(app.state.refresh_token_store.redis)),
        ):
            try:
                await check()
                checks[name] = "ok"
            except Exception as exc:  # pragma: no cover - surfaced through the response payload
                checks[name] = "error"
                errors[name] = str(exc)

        if errors:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "degraded", "checks": checks, "errors": errors},
            )

        return {"status": "ok", "checks": checks}

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(realtime_router.router)

    return app


app = create_app()
