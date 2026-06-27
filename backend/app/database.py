"""Database engine and connection lifecycle.

Models and migrations will be added in a later phase.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.config import settings

engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_database_connection() -> Iterator[Connection]:
    """Yield a transaction-managed database connection."""
    with engine.begin() as connection:
        yield connection


def verify_database_connection() -> None:
    """Fail startup early when the configured database cannot be reached."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
