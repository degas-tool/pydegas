from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import torch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger
from redis.exceptions import RedisError
from sqlmodel import Session, col, delete

from degas_api.cache.process import OptimizationRateLimiter
from degas_api.db import get_engine, init_db
from degas_api.docs.api import startup_message
from degas_api.log_config import cleanup_logging
from degas_api.models.session import OptimizationSession
from degas_api.redis import create_redis_client
from degas_api.settings import app_settings


type AppLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def cleanup_expired_sessions() -> int:
    with Session(get_engine()) as db:
        result = db.exec(
            delete(OptimizationSession).where(
                col(OptimizationSession.expires_at)
                < datetime.now(UTC).replace(tzinfo=None)
            )
        )
        db.commit()
        removed = result.rowcount
    if removed:
        logger.info("cleaned up {row_count} expired session(s)", row_count=removed)
    return removed


def create_lifespan(host: str, port: int, docs_url: str = "/docs") -> AppLifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        torch.set_default_dtype(torch.float64)
        logger.info(startup_message(host=host, port=port, docs_url=docs_url))

        init_db(app_settings.db_path)
        logger.info(
            "session database initialised at {db_path}",
            db_path=app_settings.db_path,
        )

        orl = app_settings.optimization_rate_limiter
        limits = app_settings.optimization_limits
        app.state.orl_redis = None
        app.state.orl_limiter = None
        if orl.enabled:
            logger.info(
                "initializing redis client host={host} port={port} db={db} ssl={ssl}",
                host=orl.host,
                port=orl.port,
                db=orl.db,
                ssl=orl.ssl,
            )
            redis_client = create_redis_client(orl)
            try:
                pong = await cast(Awaitable[bool], redis_client.ping())
                if pong:
                    logger.info(
                        "pinged redis instance host={host} port={port} db={db}",
                        host=orl.host,
                        port=orl.port,
                        db=orl.db,
                    )

                limiter = OptimizationRateLimiter(
                    redis=redis_client,
                    max_concurrent_runs=limits.max_concurrent_runs,
                    rate_limit_requests=limits.rate_limit_requests,
                    rate_limit_window_seconds=limits.rate_limit_window_seconds,
                )
                await limiter.reset_slots()
            except RedisError:
                logger.exception(
                    "could not connect to the redis of optimization rate limiter."
                )
                await redis_client.aclose()
                raise

            app.state.orl_redis = redis_client
            app.state.orl_limiter = limiter
            logger.info(
                "optimization rate limiter initialized: "
                "max_concurrent={max_concurrent} "
                "rate_limit={rate}/{window}s "
                "max_steps={max_steps} max_kmax={max_kmax}",
                max_concurrent=limits.max_concurrent_runs,
                rate=limits.rate_limit_requests,
                window=limits.rate_limit_window_seconds,
                max_steps=limits.max_steps,
                max_kmax=limits.max_kmax,
            )

        cleanup_hours = app_settings.session_cleanup_interval_hours
        scheduler = AsyncIOScheduler()
        scheduler.add_job(cleanup_expired_sessions, "interval", hours=cleanup_hours)
        scheduler.start()
        logger.info(
            "session cleanup scheduler started (interval={cleanup_hours}h)",
            cleanup_hours=cleanup_hours,
        )

        try:
            yield
        finally:
            logger.info("shutting down the DeGAS API server...")
            scheduler.shutdown(wait=False)

            if app.state.orl_redis is not None:
                await app.state.orl_redis.aclose()

                logger.info(
                    "redis session closed with host {host}/{port}/{db}",
                    host=orl.host,
                    port=orl.port,
                    db=orl.db,
                )

            cleanup_logging()

    return lifespan
