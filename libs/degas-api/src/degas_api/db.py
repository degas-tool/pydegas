from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

_engine: Engine | None = None


def init_db(db_path: str) -> None:
    global _engine
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        # WAL mode survives concurrent reads during an optimization run
        execution_options={"sqlite_pragma_journal_mode": "WAL"},
    )
    SQLModel.metadata.create_all(_engine)


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database not initialised, call init_db() first.")
    return _engine


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
