import os
import sqlite3
import urllib.error
from contextlib import closing
from email.message import Message
from importlib.metadata import version
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from degas_api import __version__, cli, migrate
from degas_api.settings import AppSettings, app_settings


runner = CliRunner()

IMPORT_TIME_SETTINGS = AppSettings()
EXPORTED_ENV = ("DEGAS_API_HOST", "DEGAS_API_PORT", "DEGAS_API_LOGGING__LEVEL")


class FakeResponse(BytesIO):
    def __init__(self, status: int, body: bytes) -> None:
        super().__init__(body)
        self.status = status


@pytest.fixture(autouse=True)
def restore_serve_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in EXPORTED_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(app_settings, "host", app_settings.host)
    monkeypatch.setattr(app_settings, "port", app_settings.port)


@pytest.fixture
def uvicorn_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def run(app: str, **kwargs: Any) -> None:
        calls.append({"app": app, **kwargs})

    monkeypatch.setattr(cli.uvicorn, "run", run)
    return calls


@pytest.fixture
def migration_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    for owner, name in [
        (migrate, "migrate"),
        (migrate, "run"),
        (migrate.command, "upgrade"),
        (migrate.command, "stamp"),
    ]:
        monkeypatch.setattr(owner, name, lambda *args, _name=name, **kwargs: calls.append(_name))
    return calls


def revisions(path: Path) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT version_num FROM alembic_version").fetchall()


def test_serve_defaults_come_from_the_settings(uvicorn_calls: list[dict[str, Any]], migration_calls: list[str]) -> None:
    result = runner.invoke(cli.app, ["serve"])

    assert result.exit_code == 0, result.output
    assert uvicorn_calls == [
        {
            "app": "degas_api.server:create_app",
            "factory": True,
            "host": IMPORT_TIME_SETTINGS.host,
            "port": IMPORT_TIME_SETTINGS.port,
            "workers": 1,
            "reload": False,
            "log_level": IMPORT_TIME_SETTINGS.logging.level.lower(),
        }
    ]
    assert migration_calls == []


def test_serve_options_reach_uvicorn_and_the_workers_settings(
    uvicorn_calls: list[dict[str, Any]], migration_calls: list[str]
) -> None:
    result = runner.invoke(
        cli.app, ["serve", "--host", "127.0.0.1", "--port", "9001", "--workers", "4", "--log-level", "DEBUG"]
    )

    assert result.exit_code == 0, result.output
    assert len(uvicorn_calls) == 1
    call = uvicorn_calls[0]
    assert (call["host"], call["port"], call["workers"], call["reload"], call["log_level"]) == (
        "127.0.0.1",
        9001,
        4,
        False,
        "debug",
    )
    assert {key: os.environ[key] for key in EXPORTED_ENV} == {
        "DEGAS_API_HOST": "127.0.0.1",
        "DEGAS_API_PORT": "9001",
        "DEGAS_API_LOGGING__LEVEL": "DEBUG",
    }
    worker_settings = AppSettings()
    assert (worker_settings.host, worker_settings.port, worker_settings.logging.level) == ("127.0.0.1", 9001, "DEBUG")
    assert (app_settings.host, app_settings.port, app_settings.logging.level) == ("127.0.0.1", 9001, "DEBUG")
    assert migration_calls == []


def test_serve_with_reload(uvicorn_calls: list[dict[str, Any]]) -> None:
    result = runner.invoke(cli.app, ["serve", "--reload"])

    assert result.exit_code == 0, result.output
    assert (uvicorn_calls[0]["reload"], uvicorn_calls[0]["workers"]) == (True, 1)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--reload", "--workers", "2"], "single worker only"),
        (["--workers", "0"], "--workers"),
        (["--log-level", "loud"], "is not one of"),
    ],
    ids=["reload-with-workers", "no-workers", "unknown-log-level"],
)
def test_serve_rejects_invalid_options(uvicorn_calls: list[dict[str, Any]], args: list[str], message: str) -> None:
    result = runner.invoke(cli.app, ["serve", *args])

    assert result.exit_code == 2
    assert message in result.output
    assert uvicorn_calls == []


@pytest.mark.parametrize("state", ["missing", "legacy"])
def test_serve_refuses_an_unmigrated_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uvicorn_calls: list[dict[str, Any]],
    migration_calls: list[str],
    state: str,
) -> None:
    path = tmp_path / "sessions.db"
    if state == "legacy":
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("CREATE TABLE optimization_sessions (id VARCHAR NOT NULL PRIMARY KEY)")
    monkeypatch.setattr(app_settings, "db_path", str(path))

    result = runner.invoke(cli.app, ["serve"])

    assert result.exit_code == 1
    assert "run `degas-api migrate` first" in result.output
    assert uvicorn_calls == []
    assert migration_calls == []
    assert path.exists() == (state == "legacy")


@pytest.mark.parametrize(
    ("args", "has_sessions_table"),
    [([], True), (["--revision", "base"], False)],
    ids=["head", "base"],
)
def test_migrate_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], has_sessions_table: bool
) -> None:
    path = tmp_path / "sessions.db"
    monkeypatch.setattr(app_settings, "db_path", str(path))

    result = runner.invoke(cli.app, ["migrate", *args])

    assert result.exit_code == 0, result.output
    with closing(sqlite3.connect(path)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert ("optimization_sessions" in tables) == has_sessions_table
    if has_sessions_table:
        assert revisions(path) == [(migrate.head_revision(),)]


def test_health_prints_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []

    def urlopen(url: str, timeout: float) -> FakeResponse:
        requested.append(url)
        return FakeResponse(200, b'{"slots_free": 2}')

    monkeypatch.setattr(cli.urllib.request, "urlopen", urlopen)

    result = runner.invoke(cli.app, ["health", "--url", "http://api:8000/"])

    assert result.exit_code == 0
    assert result.stdout.strip() == '{"slots_free": 2}'
    assert requested == ["http://api:8000/health"]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (urllib.error.HTTPError("http://x/health", 503, "Service Unavailable", Message(), None), "HTTP 503"),
        (urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")), "Connection refused"),
        (TimeoutError("timed out"), "timed out"),
        (None, "HTTP 204"),
    ],
    ids=["http-503", "refused", "timeout", "http-204"],
)
def test_health_fails_unless_the_answer_is_200(
    monkeypatch: pytest.MonkeyPatch, error: Exception | None, message: str
) -> None:
    def urlopen(url: str, timeout: float) -> FakeResponse:
        if error is not None:
            raise error
        return FakeResponse(204, b"")

    monkeypatch.setattr(cli.urllib.request, "urlopen", urlopen)

    result = runner.invoke(cli.app, ["health"])

    assert result.exit_code == 1
    assert message in result.stderr


def test_version() -> None:
    result = runner.invoke(cli.app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == [f"degas-api {__version__}", f"pydegas {version('pydegas')}"]
