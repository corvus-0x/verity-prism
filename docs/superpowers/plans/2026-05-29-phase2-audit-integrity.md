# Phase 2 — Test Infra + Audit-Log Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make tests run Alembic migrations (not `create_all`), implement the missing audit-log immutability trigger, and add audit records for failed uploads and auth events.

**Architecture:** Three changes in dependency order — (1) switch conftest.py to session-scoped migration + per-test truncation, (2) add a new Alembic migration that installs the `BEFORE UPDATE OR DELETE` trigger on `audit_log`, (3) add `audit.log()` calls to `_fail()` and `auth.py`. Task 2's trigger test only works because Task 1's migration fixture applies it; Task 3 is independent of Task 2.

**Tech Stack:** Python 3.12, pytest, Alembic (Python API: `alembic.config.Config`, `alembic.command`), FastAPI, SQLAlchemy 2.0, PostgreSQL 16.

---

## CRITICAL: test run command

All test runs in this plan use:

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest <target> -v
```

---

## File structure

- **Modify:** `backend/alembic/env.py` — prefer `TEST_DATABASE_URL` over `settings.database_url` so the session fixture migrates the right DB.
- **Modify:** `backend/tests/conftest.py` — replace `create_all`/`drop_all` with session-scoped Alembic upgrade + per-test truncation; add `test_engine` fixture.
- **Create:** `backend/alembic/versions/<id>_add_audit_log_immutable_trigger.py` — new migration with trigger DDL.
- **Create:** `backend/tests/test_audit_immutability.py` — trigger tests (UPDATE/DELETE blocked, INSERT allowed).
- **Modify:** `backend/app/services/document_pipeline.py` — add `audit.log()` to `_fail()`.
- **Modify:** `backend/app/routers/auth.py` — add `audit.log()` to `register` and `login`.
- **Modify:** `backend/tests/test_audit.py` — extend with M4 assertions (create if it doesn't exist).

---

## Task 1: Switch conftest to Alembic migrations (H3)

**Files:**
- Modify: `backend/alembic/env.py`
- Modify: `backend/tests/conftest.py`

There is no failing test to write first for this task — the "test" is that the existing 102-test suite continues to pass after the change. The sequence is: modify env.py → modify conftest.py → verify 102 pass.

- [ ] **Step 1: Patch env.py to route migrations to the test DB**

`alembic/env.py` currently overwrites the DB URL with `settings.database_url` unconditionally. When the session fixture calls `alembic.command.upgrade()`, `env.py` runs and would point Alembic at the production `catalyst` DB instead of `catalyst_test`. Fix this by checking for `TEST_DATABASE_URL` first.

Replace `backend/alembic/env.py` with:

```python
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import app.models  # noqa — makes Alembic see all our models
from app.config import settings
from app.database import Base

config = context.config

# When running under the test suite, TEST_DATABASE_URL is set and must take
# precedence so migrations target catalyst_test, not the production DB.
url = os.environ.get("TEST_DATABASE_URL") or settings.database_url
config.set_main_option("sqlalchemy.url", url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

- [ ] **Step 2: Replace conftest.py**

Replace the entire `backend/tests/conftest.py` with:

```python
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
```

- [ ] **Step 3: Run the full suite to verify all 102 tests pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/ -v`

Expected: `102 passed` (same count as Phase 1). The session output will show `alembic upgrade head` running before collection. If you see a schema-already-exists error for enum types, the test DB has stale state — connect to it and run `DROP DATABASE catalyst_test; CREATE DATABASE catalyst_test OWNER catalyst;` then retry.

- [ ] **Step 4: Commit**

```
git add backend/alembic/env.py backend/tests/conftest.py
git commit -m "fix(tests): run Alembic migrations in test session instead of create_all (H3)"
```

---

## Task 2: Audit-log immutability trigger (C1)

**Files:**
- Create: `backend/alembic/versions/<generated_id>_add_audit_log_immutable_trigger.py`
- Create: `backend/tests/test_audit_immutability.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_audit_immutability.py`:

```python
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError

from app.models.audit import AuditLog


def _make_entry(db):
    """Insert a single audit_log row and return it."""
    entry = AuditLog(
        id=str(uuid.uuid4()),
        action="test_event",
        entity_type="test",
        entity_id=str(uuid.uuid4()),
    )
    db.add(entry)
    db.commit()
    return entry


def test_insert_audit_log_succeeds(db):
    entry = _make_entry(db)
    assert entry.id is not None


def test_update_audit_log_is_blocked(db, test_engine):
    entry = _make_entry(db)
    with pytest.raises(InternalError):
        with test_engine.begin() as conn:
            conn.execute(
                text("UPDATE audit_log SET action = 'tampered' WHERE id = :id"),
                {"id": entry.id},
            )


def test_delete_audit_log_is_blocked(db, test_engine):
    entry = _make_entry(db)
    with pytest.raises(InternalError):
        with test_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM audit_log WHERE id = :id"),
                {"id": entry.id},
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_audit_immutability.py -v`

Expected: `test_insert_audit_log_succeeds` PASSES (inserts work now), `test_update_audit_log_is_blocked` and `test_delete_audit_log_is_blocked` FAIL — the UPDATE and DELETE succeed because the trigger doesn't exist yet.

- [ ] **Step 3: Generate the migration file**

Run inside the backend container:
```
docker-compose exec backend alembic revision -m "add_audit_log_immutable_trigger"
```

This creates `backend/alembic/versions/<generated_id>_add_audit_log_immutable_trigger.py`. Open it. The file will have:
- `revision`: an auto-generated hex string — **keep it as-is**
- `down_revision`: should be `'e1f3a2b94c07'` (the previous head)

Replace the `upgrade()` and `downgrade()` functions with:

```python
from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is immutable: % is not permitted', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable();")
```

Keep the generated `revision`, `down_revision`, `branch_labels`, `depends_on`, and the docstring at the top. Only replace the `upgrade()` and `downgrade()` function bodies.

- [ ] **Step 4: Run tests to verify they now pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_audit_immutability.py -v`

Expected: all 3 PASS. The `migrate_db` session fixture runs `alembic upgrade head`, which now applies the new trigger migration before any test runs.

- [ ] **Step 5: Run full suite to confirm no regressions**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/ -v`

Expected: `105 passed` (102 prior + 3 new immutability tests).

- [ ] **Step 6: Commit**

```
git add backend/alembic/versions/ backend/tests/test_audit_immutability.py
git commit -m "fix(security): add audit_log immutability trigger (C1)"
```

---

## Task 3: Audit failed uploads (M4a)

**Files:**
- Modify: `backend/app/services/document_pipeline.py` (lines 55–61, `_fail` function)
- Test: `backend/tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_audit.py`:

```python
import uuid
import pytest
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.services.document_pipeline import _fail


@pytest.fixture
def user_ws_doc(db):
    user = User(
        id=str(uuid.uuid4()),
        email="pipeline_test@example.com",
        password_hash="hashed",
        full_name="Test User",
    )
    db.add(user)
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Test WS",
        vertical="fraud",
        created_by=user.id,
    )
    db.add(ws)
    db.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        sha256_hash="a" * 64,
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()
    return user, ws, doc


def test_fail_writes_upload_failed_audit_row(db, user_ws_doc):
    user, ws, doc = user_ws_doc

    _fail(doc, "OCR failed: corrupted file", db)

    entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "upload_failed", AuditLog.entity_id == doc.id)
        .first()
    )
    assert entry is not None
    assert entry.user_id == user.id
    assert entry.workspace_id == ws.id
    assert "OCR failed" in entry.after_state["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_audit.py::test_fail_writes_upload_failed_audit_row -v`

Expected: FAIL — no `upload_failed` audit row is written by `_fail()` currently.

- [ ] **Step 3: Add the audit call to `_fail()`**

In `backend/app/services/document_pipeline.py`, replace the `_fail` function (lines 55–61):

```python
def _fail(doc: Document, error: str, db: Session) -> None:
    """Mark a document as failed with a reason."""
    doc.extraction_status = "failed"
    doc.extraction_error = error[:500]
    db.commit()
    logger.error(f"Pipeline failed for doc {doc.id}: {error}")
    try:
        audit.log(
            db,
            action="upload_failed",
            user_id=doc.uploaded_by,
            workspace_id=doc.workspace_id,
            entity_type="document",
            entity_id=doc.id,
            after_state={"error": error[:500], "status": "failed"},
        )
    except Exception as e:
        logger.warning(f"Audit log failed for _fail on doc {doc.id}: {e}")
```

(`audit` is already imported at line 33: `from app.services import audit`)

- [ ] **Step 4: Run test to verify it passes**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_audit.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/services/document_pipeline.py backend/tests/test_audit.py
git commit -m "fix(audit): write upload_failed audit row on pipeline failure (M4)"
```

---

## Task 4: Audit auth events (M4b)

**Files:**
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_audit.py` (the `AuditLog` import is already at the top of the file from Task 3 — do not add it again):

```python
def test_register_writes_audit_row(client, db):
    client.post("/auth/register", json={
        "email": "audit_reg@example.com",
        "password": "TestPass123!",
        "full_name": "Audit Reg",
    })
    entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "registered")
        .first()
    )
    assert entry is not None
    assert entry.workspace_id is None
    assert entry.after_state["email"] == "audit_reg@example.com"


def test_login_success_writes_audit_row(client, registered_user, db):
    client.post("/auth/login", json=registered_user)
    entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "login_success")
        .first()
    )
    assert entry is not None
    assert entry.user_id is not None
    assert entry.workspace_id is None


def test_login_failure_writes_audit_row(client, db):
    client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "wrongpassword",
    })
    entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "login_failed")
        .first()
    )
    assert entry is not None
    assert entry.user_id is None
    assert entry.after_state["email"] == "nobody@example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_audit.py::test_register_writes_audit_row tests/test_audit.py::test_login_success_writes_audit_row tests/test_audit.py::test_login_failure_writes_audit_row -v`

Expected: all 3 FAIL — no audit rows written by auth routes currently.

- [ ] **Step 3: Add audit calls to auth.py**

Replace the entire contents of `backend/app/routers/auth.py` with:

```python
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenOut, UserLogin, UserOut, UserRegister
from app.services import audit
from app.services.auth import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        audit.log(
            db,
            action="registered",
            user_id=user.id,
            after_state={"email": user.email},
        )
    except Exception as e:
        logger.warning(f"Audit log failed for register user {user.id}: {e}")
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        try:
            audit.log(
                db,
                action="login_failed",
                after_state={"email": payload.email},
            )
        except Exception as e:
            logger.warning(f"Audit log failed for login_failed {payload.email}: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        audit.log(
            db,
            action="login_success",
            user_id=user.id,
            after_state={"email": user.email},
        )
    except Exception as e:
        logger.warning(f"Audit log failed for login_success user {user.id}: {e}")
    return {"access_token": create_access_token(user.id)}
```

- [ ] **Step 4: Run test_audit.py to verify all pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_audit.py -v`

Expected: all 4 tests PASS (`test_fail_writes_upload_failed_audit_row` + 3 new auth tests).

- [ ] **Step 5: Run full suite to confirm no regressions**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/ -v`

Expected: `109 passed` (105 prior + 4 new audit tests). Verify `test_auth.py` existing tests still pass — specifically `test_login_returns_jwt_token` and `test_wrong_password_returns_401`, since auth.py was replaced in full.

- [ ] **Step 6: Commit**

```
git add backend/app/routers/auth.py backend/tests/test_audit.py
git commit -m "fix(audit): write audit rows for register and login events (M4)"
```
