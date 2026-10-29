"""Database engine and session handling (SQLAlchemy 2.0, sync)."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


class Database:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        """SQLite (tests, quick local runs) gets its tables directly. Postgres is managed by
        Alembic migrations: run `alembic upgrade head` (the Docker image does this on start)."""
        if self.engine.dialect.name != "sqlite":
            return
        from app.platform import models  # noqa: F401 - register tables

        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        with self.sessionmaker() as session:
            yield session
