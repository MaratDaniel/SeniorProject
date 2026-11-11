"""ASGI entry point: `uvicorn app.main:create_app --factory`."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.db import make_engine, make_sessionmaker
from app.engine.registry import default_registry
from app.errors import install_error_handlers
from app.middleware import SecurityHeadersMiddleware
from app.realtime import ws
from app.realtime.broker import Broker, InMemoryBroker, RedisBroker
from app.routers import admin, auctions, auth, dev, listings, transactions
from app.scheduler import Scheduler
from app.security.ratelimit import RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    media_dir = Path(settings.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    docs = settings.env != "prod"

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        broker: Broker = RedisBroker(settings.redis_url) if settings.redis_url else InMemoryBroker()
        await broker.start()
        app.state.engine = engine
        app.state.sessionmaker = make_sessionmaker(engine)
        app.state.broker = broker
        scheduler_task: asyncio.Task[None] | None = None
        if settings.scheduler_enabled:
            scheduler = Scheduler(app.state.sessionmaker, broker, app.state.strategies, settings)
            scheduler_task = asyncio.create_task(scheduler.run_forever(), name="scheduler")
        try:
            yield
        finally:
            if scheduler_task is not None:
                scheduler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await scheduler_task
            await broker.stop()
            await engine.dispose()

    app = FastAPI(
        title="Adal API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.limiter = RateLimiter()
    app.state.strategies = default_registry(settings)

    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "prod")
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=sorted(o.rstrip("/") for o in settings.cors_origins),  # exact origins, never "*"
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    install_error_handlers(app)

    for module in (auth, listings, auctions, transactions, admin):
        app.include_router(module.router)
    if settings.env == "dev":
        app.include_router(dev.router)
    app.include_router(ws.router)
    app.mount("/media", StaticFiles(directory=media_dir), name="media")
    return app
