"""Database engine and session management.

SQLAlchemy splits this into two ideas:

* the ENGINE  - one per application; owns the pool of connections
* the SESSION - one per request; a unit of work that is committed or discarded
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# pool_pre_ping checks a pooled connection is still alive before using it.
# Without it, a connection dropped by the database produces a confusing error
# on the next request.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Parent class for every database model in the project."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: opens a session, hands it to the endpoint, and
    always closes it afterwards - even if the endpoint raised an error."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
