from __future__ import annotations

import time

from loguru import logger
from redis.asyncio import Redis

# Lua script for atomic check-and-increment (avoids TOCTOU race on the cap).
_ACQUIRE_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current >= tonumber(ARGV[1]) then
    return 0
end
redis.call('INCR', KEYS[1])
return 1
"""

_ACTIVE_KEY = "active_runs:optimization"


class OptimizationRateLimiter:
    """Per-IP sliding-window rate limit + concurrency cap, both backed by Redis."""

    def __init__(
        self,
        redis: Redis,
        *,
        max_concurrent_runs: int,
        rate_limit_requests: int,
        rate_limit_window_seconds: int,
    ) -> None:
        self._redis = redis
        self._max_concurrent = max_concurrent_runs
        self._rate_limit_requests = rate_limit_requests
        self._rate_limit_window_seconds = rate_limit_window_seconds

    async def try_acquire_slot(self) -> bool:
        """Atomically acquire a concurrency slot. Returns True if acquired."""
        acquired = bool(
            await self._redis.eval(
                _ACQUIRE_SCRIPT, 1, _ACTIVE_KEY, self._max_concurrent
            )
        )
        if acquired:
            logger.debug(
                "concurrency slot acquired; max={max}", max=self._max_concurrent
            )
        else:
            logger.warning(
                "concurrency limit reached; max={max}", max=self._max_concurrent
            )
        return acquired

    async def release_slot(self) -> None:
        val = await self._redis.decr(_ACTIVE_KEY)
        if val < 0:
            await self._redis.set(_ACTIVE_KEY, 0)
            logger.error("active_runs went negative — reset to 0; this is a bug")
        else:
            logger.debug("concurrency slot released; active={active}", active=val)

    async def slots_free(self) -> int:
        val = await self._redis.get(_ACTIVE_KEY)
        return self._max_concurrent - int(val or 0)

    async def check_rate_limit(self, client_ip: str) -> tuple[bool, int]:
        """Sliding-window check. Rejected requests do not consume a window slot."""
        key = f"rate_limit:optimization:{client_ip}"
        now = time.time()
        window_start = now - self._rate_limit_window_seconds
        member = f"{now:.6f}"

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zcard(key)
            pipe.zadd(key, {member: now})
            pipe.expire(key, self._rate_limit_window_seconds + 1)
            results = await pipe.execute()

        count_before = results[1]

        if count_before >= self._rate_limit_requests:
            await self._redis.zrem(key, member)
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = (
                    int(oldest[0][1] + self._rate_limit_window_seconds - now) + 1
                )
            else:
                retry_after = self._rate_limit_window_seconds
            logger.warning(
                "rate limit exceeded for {ip}: {count}/{limit} in window",
                ip=client_ip,
                count=count_before,
                limit=self._rate_limit_requests,
            )
            return False, max(retry_after, 1)

        return True, 0

    async def undo_rate_limit_entry(self, client_ip: str) -> None:
        await self._redis.zremrangebyrank(
            f"rate_limit:optimization:{client_ip}", -1, -1
        )
