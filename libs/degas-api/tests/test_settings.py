import asyncio
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import SSLConnection

import degas_api
import degas_api.redis
from degas_api.redis import create_redis_client
from degas_api.server import create_app
from degas_api.settings import AppSettings, RedisRateLimiterSettings, app_settings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in list(os.environ):
        if name.upper().startswith("DEGAS_API_"):
            monkeypatch.delenv(name)
    return monkeypatch


def test_unprefixed_env_vars_do_not_reach_nested_settings(
    clean_env: pytest.MonkeyPatch,
) -> None:
    for name, value in {
        "PORT": "1234",
        "HOST": "elsewhere",
        "USERNAME": "someone",
        "PASSWORD": "secret",
        "SSL": "true",
        "ENABLED": "false",
        "LEVEL": "ERROR",
        "MAX_STEPS": "7",
    }.items():
        clean_env.setenv(name, value)

    settings = AppSettings()

    assert settings.optimization_rate_limiter == RedisRateLimiterSettings()
    assert settings.logging.level == "INFO"
    assert settings.optimization_limits.max_steps == 500


def test_prefixed_nested_env_vars_update_single_fields(
    clean_env: pytest.MonkeyPatch,
) -> None:
    clean_env.setenv("DEGAS_API_OPTIMIZATION_RATE_LIMITER__PORT", "6380")
    clean_env.setenv("DEGAS_API_OPTIMIZATION_RATE_LIMITER__USERNAME", "degas")
    clean_env.setenv("DEGAS_API_OPTIMIZATION_LIMITS__MAX_STEPS", "50")

    settings = AppSettings()

    assert settings.optimization_rate_limiter.port == 6380
    assert settings.optimization_rate_limiter.username == "degas"
    assert settings.optimization_rate_limiter.host == "localhost"
    assert settings.optimization_limits.max_steps == 50
    assert settings.optimization_limits.max_kmax == 100


def test_redis_client_uses_username_password_and_ssl() -> None:
    settings = RedisRateLimiterSettings(
        host="redis.internal",
        port=6380,
        db=3,
        username="degas",
        password="secret",
        ssl=True,
    )

    client = create_redis_client(settings)
    try:
        pool = client.connection_pool
        assert pool.connection_class is SSLConnection
        kwargs = pool.connection_kwargs
        assert kwargs["host"] == "redis.internal"
        assert kwargs["port"] == 6380
        assert kwargs["db"] == 3
        assert kwargs["username"] == "degas"
        assert kwargs["password"] == "secret"
    finally:
        asyncio.run(client.aclose())


def test_redis_client_without_ssl() -> None:
    client = create_redis_client(RedisRateLimiterSettings())
    try:
        assert client.connection_pool.connection_class is not SSLConnection
        assert client.connection_pool.connection_kwargs["username"] is None
    finally:
        asyncio.run(client.aclose())


class FakeRedis:
    instances: list["FakeRedis"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.values: dict[str, Any] = {}
        self.closed = False
        FakeRedis.instances.append(self)

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def aclose(self) -> None:
        self.closed = True


def test_lifespan_connects_the_limiter_with_all_redis_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeRedis.instances.clear()
    monkeypatch.setattr(degas_api.redis, "Redis", FakeRedis)
    monkeypatch.setattr(
        app_settings,
        "optimization_rate_limiter",
        RedisRateLimiterSettings(username="degas", password="secret", ssl=True),
    )

    with TestClient(create_app()) as client:
        assert client.get("/health").json()["slots_free"] == 2

    [redis] = FakeRedis.instances
    assert redis.kwargs["username"] == "degas"
    assert redis.kwargs["password"] == "secret"
    assert redis.kwargs["ssl"] is True
    assert redis.values == {"active_runs:optimization": 0}
    assert redis.closed


def test_version_fallback_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> str:
        raise degas_api.PackageNotFoundError(name)

    monkeypatch.setattr(degas_api, "version", missing)

    assert degas_api.get_version() == "0.0.0"
