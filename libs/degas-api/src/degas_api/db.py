from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, create_engine


_engine: Engine | None = None


def database_url(db_path: str) -> str:
    return f"sqlite:///{db_path}"


def init_db(db_path: str) -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(
        database_url(db_path),
        connect_args={"check_same_thread": False},
    )


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database not initialised, call init_db() first.")
    return _engine


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
