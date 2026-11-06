"""Shared test fixtures.

Each test runs inside a transaction that is rolled back afterwards, so tests
cannot see or disturb each other's data and the database is never left dirty.
That is what makes the suite safe to run repeatedly.
"""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.session import Base
from app.models.enums import UserRole
from app.models.user import User

# A separate database so running tests never touches development data.
TEST_DATABASE_URL = settings.DATABASE_URL.rsplit("/", 1)[0] + "/safemed_test"


@pytest.fixture(scope="session")
def engine():
    """Create the test database and its tables once per run."""
    admin_url = settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.exec_driver_sql(
            "SELECT 1 FROM pg_database WHERE datname = 'safemed_test'"
        ).first()
        if not exists:
            conn.exec_driver_sql("CREATE DATABASE safemed_test")
    admin.dispose()

    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    """A session wrapped in a transaction that is always rolled back."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def patient(db: Session) -> User:
    user = User(
        email=f"patient-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
        full_name="Maria Santos",
        role=UserRole.PATIENT,
    )
    db.add(user)
    db.flush()
    return user
