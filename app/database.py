"""SQLAlchemy engine and a separate session for each request."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Models share this metadata; Alembic uses it to detect schema changes."""


def build_engine(url: str, **kwargs) -> Engine:
    """SQLite is the local default; other database URLs use their own driver."""
    is_sqlite = url.startswith("sqlite:")
    engine = create_engine(
        url,
        # FastAPI may run synchronous dependencies/handlers on different threads.
        # This permits that for SQLite; it does not make sharing one Session safe.
        connect_args={"check_same_thread": False} if is_sqlite else {},
        pool_pre_ping=True,
        hide_parameters=True,
        **kwargs,
    )
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, connection_record) -> None:
            # Explicit transactions also make SQLite DDL/migrations transactional.
            connection.isolation_level = None
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        @event.listens_for(engine, "begin")
        def begin_sqlite_transaction(connection) -> None:
            connection.exec_driver_sql("BEGIN")

    return engine


# An engine/pool is process-wide; creating it does not create tables or open a Session.
engine = build_engine(get_settings().database_url)
# This is a session factory, not a singleton session. Every request calls it afresh.
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    # A context manager always closes the session and rolls back uncommitted work.
    # Routes explicitly commit writes, so a failed request cannot silently persist.
    with SessionLocal() as session:
        yield session
