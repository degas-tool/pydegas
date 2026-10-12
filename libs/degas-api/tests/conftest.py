from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from degas_api.server import create_app
from degas_api.settings import (
    LoggingSettings,
    OptimizationLimitsSettings,
    RedisRateLimiterSettings,
    app_settings,
)


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("degas-api") / "sessions.db"


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setattr(app_settings, "db_path", str(db_path))
    monkeypatch.setattr(app_settings, "docs_url", "/docs")
    monkeypatch.setattr(app_settings, "allowed_hosts", ["*"])
    monkeypatch.setattr(app_settings, "static_dir", None)
    monkeypatch.setattr(app_settings, "logging", LoggingSettings(level="WARNING"))
    monkeypatch.setattr(app_settings, "optimization_rate_limiter", RedisRateLimiterSettings(enabled=False))
    monkeypatch.setattr(app_settings, "optimization_limits", OptimizationLimitsSettings())


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
