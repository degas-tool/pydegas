from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from loguru import logger
from sqlalchemy import create_engine, inspect, pool, text

from degas_api.db import database_url
from degas_api.log_config import cleanup_logging, configure_logging
from degas_api.models.session import OptimizationSession
from degas_api.settings import app_settings


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
BASELINE_REVISION = "98ebc0205c9b"
VERSION_TABLE = "alembic_version"


class DatabaseNotMigratedError(RuntimeError):
    pass


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR).replace("%", "%%"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _inspect(url: str) -> tuple[set[str], str | None]:
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            revision = None
            if VERSION_TABLE in tables:
                revision = connection.scalar(text(f"SELECT version_num FROM {VERSION_TABLE}"))
    finally:
        engine.dispose()
    return tables, revision


def head_revision() -> str | None:
    return ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()


def check_schema(db_path: str) -> None:
    if not Path(db_path).exists():
        raise DatabaseNotMigratedError(f"database {db_path} does not exist; run `degas-api migrate` first")
    _, current = _inspect(database_url(db_path))
    head = head_revision()
    if current != head:
        raise DatabaseNotMigratedError(
            f"database {db_path} is at revision {current or '<none>'}, expected {head}; run `degas-api migrate` first"
        )


def migrate(db_path: str, revision: str = "head") -> None:
    url = database_url(db_path)
    config = alembic_config(url)

    tables, before = _inspect(url)
    if OptimizationSession.__tablename__ in tables and VERSION_TABLE not in tables:
        logger.info(
            "database {db_path} was created without migrations; stamping baseline revision {revision}",
            db_path=db_path,
            revision=BASELINE_REVISION,
        )
        command.stamp(config, BASELINE_REVISION)
        before = BASELINE_REVISION

    command.upgrade(config, revision)

    _, after = _inspect(url)
    if before == after:
        logger.info("database {db_path} is up to date at revision {revision}", db_path=db_path, revision=after)
    else:
        logger.info(
            "migrated database {db_path} from revision {before} to {after}",
            db_path=db_path,
            before=before or "<empty>",
            after=after,
        )


def run(revision: str = "head") -> None:
    configure_logging(level=app_settings.logging.level)
    try:
        migrate(app_settings.db_path, revision)
    finally:
        cleanup_logging()


if __name__ == "__main__":
    run()
