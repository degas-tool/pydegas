from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import Session, SQLModel, create_engine


_engine: Engine | None = None


def _create_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in SQLModel.metadata.sorted_tables:
            connection.execute(CreateTable(table, if_not_exists=True))
            for index in table.indexes:
                connection.execute(CreateIndex(index, if_not_exists=True))


def init_db(db_path: str) -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    _create_tables(_engine)


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database not initialised, call init_db() first.")
    return _engine


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
