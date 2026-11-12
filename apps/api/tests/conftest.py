"""Test setup.

By default the tests run on in-memory SQLite, with no service to start. When
TEST_DATABASE_URL points to a PostgreSQL database, they run on it instead,
through the real migrations, which also enables the row-level security tests.
"""

import os
from collections.abc import Iterator
from pathlib import Path

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.main import app as fastapi_app

ON_POSTGRES = bool(TEST_DATABASE_URL)
API_ROOT = Path(__file__).resolve().parent.parent

requires_postgres = pytest.mark.skipif(
    not ON_POSTGRES, reason="row-level security needs PostgreSQL (set TEST_DATABASE_URL)"
)


@pytest.fixture(scope="session")
def _postgres_schema() -> None:
    if ON_POSTGRES:
        config = Config(str(API_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(API_ROOT / "alembic"))
        command.upgrade(config, "head")


@pytest.fixture
def session_factory(_postgres_schema: None) -> Iterator[sessionmaker[Session]]:
    """Sessions on a database that is empty at the start of each test."""
    if ON_POSTGRES:
        yield SessionLocal
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE users, organizations CASCADE"))
        return

    sqlite_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(sqlite_engine)
    yield sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)
    sqlite_engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
