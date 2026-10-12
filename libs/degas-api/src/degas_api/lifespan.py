from contextlib import asynccontextmanager
from datetime import datetime, timezone

import torch
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from degas_api.settings import app_settings
from loguru import logger

import redis.asyncio as redis_asyncio
from redis.exceptions import ConnectionError as RedisConnectionError


def create_lifespan(host: str, port: int):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from degas_api.docs.api import startup_message
        from degas_api.cache.process import OptimizationRateLimiter

        torch.set_default_dtype(torch.float64)
        logger.info(startup_message(host=host, port=port))

        from degas_api.db import get_engine, init_db
        from degas_api.models.session import OptimizationSession
        from sqlmodel import Session, delete

        init_db(app_settings.db_path)
        logger.info(
            "session database initialised at {db_path}",
            db_path=app_settings.db_path,
        )

        def _cleanup_expired_sessions() -> None:
            with Session(get_engine()) as db:
                result = db.exec(
                    delete(OptimizationSession).where(
                        OptimizationSession.expires_at
                        < datetime.now(timezone.utc).replace(tzinfo=None)
                    )
                )
                db.commit()
                if result.rowcount:
                    logger.info(
                        "cleaned up {row_count} expired session(s)",
                        row_count=result.rowcount,
                    )

        cleanup_hours = app_settings.session_cleanup_interval_hours
        scheduler = AsyncIOScheduler()
        scheduler.add_job(_cleanup_expired_sessions, "interval", hours=cleanup_hours)
        scheduler.start()
        logger.info(
            "session cleanup scheduler started (interval={cleanup_hours}h)",
            cleanup_hours=cleanup_hours,
        )

        orl = app_settings.optimization_rate_limiter
        limits = app_settings.optimization_limits
        app.state.orl_redis = None
        app.state.orl_limiter = None
        if orl.enabled:
            try:
                logger.info(
                    "initializing redis client host={host} port={port} db={db}",
                    host=orl.host,
                    port=orl.port,
                    db=orl.db,
                )
                app.state.orl_redis = redis_asyncio.Redis.from_url(
                    f"redis://{orl.host}:{orl.port}/{orl.db}",
                    password=orl.password,
                )

                pong = await app.state.orl_redis.ping()
                if pong:
                    logger.info(
                        "pinged redis instance host={host} port={port} db={db}",
                        host=orl.host,
                        port=orl.port,
                        db=orl.db,
                    )

                # Reset stale concurrency counter from previous (possibly crashed) run.
                await app.state.orl_redis.set("active_runs:optimization", 0)

                app.state.orl_limiter = OptimizationRateLimiter(
                    redis=app.state.orl_redis,
                    max_concurrent_runs=limits.max_concurrent_runs,
                    rate_limit_requests=limits.rate_limit_requests,
                    rate_limit_window_seconds=limits.rate_limit_window_seconds,
                )
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
            except RedisConnectionError as e:
                logger.exception(
                    "could not connect to the redis of optimization rate limiter."
                )
                raise e

        try:
            yield
        finally:
            logger.info("shutting down the DeGAS API server...")
            scheduler.shutdown(wait=False)

            if app.state.orl_redis:
                await app.state.orl_redis.close()

                logger.info(
                    "redis session closed with host {host}/{port}/{db}",
                    host=orl.host,
                    port=orl.port,
                    db=orl.db,
                )

            from degas_api.log_config import cleanup_logging

            cleanup_logging()

    return lifespan
