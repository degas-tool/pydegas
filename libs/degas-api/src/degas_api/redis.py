from redis.asyncio import Redis

from degas_api.settings import RedisRateLimiterSettings


def create_redis_client(settings: RedisRateLimiterSettings) -> Redis:
    return Redis(
        host=settings.host,
        port=settings.port,
        db=settings.db,
        username=settings.username,
        password=settings.password,
        ssl=settings.ssl,
    )
