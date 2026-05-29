import os
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://catalyst:catalyst@localhost:5432/catalyst_test"
)
os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL  # ensure env.py picks up the resolved value

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def migrate_db():
    """Run Alembic migrations once for the whole session against catalyst_test.

    Upgrade is idempotent — if the schema is already at head from a previous
    run, this is a no-op. No teardown: truncation handles per-test isolation,
    and the test DB is ephemeral enough that leaving the schema in place is fine.
    """
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    yield


@pytest.fixture(autouse=True)
def setup_db():
    """Truncate all app tables before each test for a clean data state.

    Uses RESTART IDENTITY CASCADE so sequences reset and FK children are cleared
    before parents. Equivalent to the old create_all/drop_all cycle but ~10x
    faster (no DDL round-trip) and preserves migration-only schema objects
    (triggers, enum values, indexes).
    """
    table_names = ", ".join(
        f'"{t.name}"'
        for t in reversed(Base.metadata.sorted_tables)
    )
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def test_engine():
    """Yield the test DB engine for tests that need raw SQL on a fresh connection."""
    return engine


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    client.post("/auth/register", json={
        "email": "tyler@example.com",
        "password": "TestPass123!",
        "full_name": "Tyler Collins"
    })
    return {"email": "tyler@example.com", "password": "TestPass123!"}


@pytest.fixture
def auth_headers(client, registered_user):
    response = client.post("/auth/login", json=registered_user)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
