from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis_asyncio
from loguru import logger


@asynccontextmanager
async def initialize_redis_pool(
    host: str, port: int, db: int, password: str
) -> AsyncIterator[redis_asyncio.Redis]:
    logger.info(
        "initializing redis client host={host} port={port} db={db}",
        host=host,
        port=port,
    )
    session = redis_asyncio.Redis.from_url(
        f"redis://{host}:{port}/{db}",
        password=password,
    )

    await session.ping()
    try:
        yield session
    finally:
        await session.close()
        logger.info(
            "redis session closed with host {host}/{port}/{db}",
            host=host,
            port=port,
            db=db,
        )
