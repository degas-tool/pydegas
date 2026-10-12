import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory

from degas_api.db import database_url
from degas_api.migrate import BASELINE_REVISION, MIGRATIONS_DIR, alembic_config, migrate, run
from degas_api.settings import app_settings


LEGACY_SCHEMA = """
CREATE TABLE optimization_sessions (
    id VARCHAR NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    owner_token VARCHAR NOT NULL,
    name VARCHAR,
    loss_mode VARCHAR NOT NULL,
    loss_name VARCHAR NOT NULL,
    request VARCHAR NOT NULL,
    steps VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    outcome VARCHAR,
    PRIMARY KEY (id)
)
"""

ROW = (
    "abcd1234",
    "2026-10-01 10:00:00.000000",
    "2026-10-02 10:00:00.000000",
    "token",
    None,
    "builtin",
    "l2_distance",
    "{}",
    "[]",
    "done",
    None,
)


def head() -> str | None:
    return ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()


def query(path: Path, sql: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(sql).fetchall()


def insert_row(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("INSERT INTO optimization_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ROW)


def test_upgrade_creates_the_schema_on_an_empty_database(tmp_path: Path) -> None:
    path = tmp_path / "new.db"

    migrate(str(path))

    tables = query(path, "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    assert tables == [("alembic_version",), ("optimization_sessions",)]
    assert query(path, "SELECT version_num FROM alembic_version") == [(head(),)]


def test_migrations_match_the_models(tmp_path: Path) -> None:
    path = tmp_path / "check.db"
    migrate(str(path))

    command.check(alembic_config(database_url(str(path))))


def test_baseline_is_the_first_revision() -> None:
    baseline = ScriptDirectory(str(MIGRATIONS_DIR)).get_revision(BASELINE_REVISION)

    assert baseline is not None
    assert baseline.down_revision is None


def test_legacy_database_is_stamped_and_keeps_its_rows(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(LEGACY_SCHEMA)
    insert_row(path)

    migrate(str(path))

    assert query(path, "SELECT version_num FROM alembic_version") == [(head(),)]
    assert query(path, "SELECT * FROM optimization_sessions") == [ROW]


def test_migrate_twice_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "twice.db"
    migrate(str(path))
    insert_row(path)
    schema = query(path, "SELECT type, name, sql FROM sqlite_master ORDER BY name")

    migrate(str(path))

    assert query(path, "SELECT type, name, sql FROM sqlite_master ORDER BY name") == schema
    assert query(path, "SELECT version_num FROM alembic_version") == [(head(),)]
    assert query(path, "SELECT * FROM optimization_sessions") == [ROW]


def test_run_migrates_the_configured_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "configured.db"
    monkeypatch.setattr(app_settings, "db_path", str(path))

    run()

    assert query(path, "SELECT version_num FROM alembic_version") == [(head(),)]


def test_python_m_degas_api_migrate(tmp_path: Path) -> None:
    path = tmp_path / "module.db"
    env = {**os.environ, "DEGAS_API_DB_PATH": str(path)}

    subprocess.run([sys.executable, "-m", "degas_api.migrate"], cwd=tmp_path, env=env, check=True, capture_output=True)

    assert query(path, "SELECT version_num FROM alembic_version") == [(head(),)]
