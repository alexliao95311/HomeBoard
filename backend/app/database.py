"""Database engine, ORM base, and session lifecycle."""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_database_connection() -> Iterator[Connection]:
    """Yield a transaction-managed database connection."""
    with engine.begin() as connection:
        yield connection


def get_database_session() -> Iterator[Session]:
    """Yield a request-scoped ORM session."""
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def verify_database_connection() -> None:
    """Fail startup early when the configured database cannot be reached."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def initialize_database() -> None:
    """Create the current MVP tables when they do not exist."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
