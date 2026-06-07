# Phase 2 — Test Infra + Audit-Log Integrity (Design Spec)

**Date:** 2026-05-29
**Branch:** `feat/phase-2-audit-integrity`
**Source:** `docs/code-audit-2026-05-29.md` findings H3, C1, M4
**Status:** Approved (design), pending implementation plan

---

## Goal

Close the gap where tests never run Alembic migrations (so migration-only DDL is untested), implement the audit-log immutability trigger that was specified but never built, and add audit records for failed uploads and authentication events. These three findings must be fixed in dependency order: H3 first (test infra), C1 second (the trigger only becomes verifiable once tests run migrations), M4 third (straightforward additions on top of the existing audit service).

## Scope

In scope: H3, C1, M4.
Explicitly **out of scope** (deferred):
- `create_conversation` audit — `send_message` already audits at the conversation level; the created event is low value.
- Soft-delete consistency across all tables (L5) → Phase 4.
- Any changes to routers beyond adding audit calls (M5 → Phase 5).

---

## Decisions (approved)

- **H3 isolation strategy:** Session-scoped `alembic upgrade head` + per-test truncation (not transactional rollback). Gives the same clean-slate guarantee as the current `create_all`/`drop_all` approach but ~10× faster, and — critically — tests now run against the actual migration-produced schema including triggers, enum values, and columns that only exist in migrations.
- **M4 scope:** Four gaps: `upload_failed` (pipeline), `registered` (auth), `login_success` (auth), `login_failed` (auth). No workspace_id for auth events (AuditLog.workspace_id is nullable — already supported by the model).

---

## Components

### conftest.py (H3)

Replace the `autouse=True` `setup_db` fixture:

**Before:** per-test `Base.metadata.create_all` / `drop_all` — schema from ORM models, migrations never run.

**After:**
- One `session`-scoped fixture `migrate_db` (autouse, scope="session") runs `alembic upgrade head` at session start and `alembic downgrade base` at teardown. Uses the Alembic Python API (`alembic.config.Config`, `alembic.command.upgrade/downgrade`) with `alembic.ini` at `backend/alembic.ini` (confirmed present). The config's `sqlalchemy.url` is overridden to `TEST_DATABASE_URL` before running so migrations target the test DB, not the dev DB.
- One `function`-scoped fixture `setup_db` (autouse, replaces the old one) runs `TRUNCATE <all tables> RESTART IDENTITY CASCADE` before each test. This resets data without touching DDL, so the trigger and enum values survive across tests.
- The table list for truncation is derived at fixture time from `Base.metadata.sorted_tables` (reverse topological order to respect FK constraints) — no hardcoded table names.
- All other fixtures (`db`, `client`, `registered_user`, `auth_headers`) are **unchanged**.

### New migration: audit_log_immutable (C1)

New Alembic revision after `e1f3a2b94c07`, named `add_audit_log_immutable_trigger`.

**Upgrade:**
```sql
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is immutable: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
```

**Downgrade:**
```sql
DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;
DROP FUNCTION IF EXISTS audit_log_immutable();
```

### New test file: test_audit_immutability.py (C1)

Tests that only make sense against the migrated schema. Verify both `UPDATE` and `DELETE` on `audit_log` raise `sqlalchemy.exc.InternalError`. Uses the `db` fixture (now migration-backed). Depends on H3 being in place — would silently pass/miss the trigger under `create_all`.

### document_pipeline._fail() (M4)

Add one `audit.log()` call inside `_fail()`. The function already has `doc` (which carries `doc.uploaded_by` and `doc.workspace_id`) and `db`. No signature change needed.

### routers/auth.py (M4)

Three additions to the existing two endpoints:
- `register`: call `audit.log()` after `db.commit()` with `action="registered"`, `user_id=user.id`.
- `login` success: call `audit.log()` after verifying credentials, `action="login_success"`, `user_id=user.id`.
- `login` failure: call `audit.log()` before the 401 raise, `action="login_failed"`, `after_state={"email": payload.email}` (no `user_id` — the user may not exist).

The `audit` service is already imported in other routers; add the import to `auth.py`.

---

## Data flow (unchanged)

No model changes. The `AuditLog` model already has nullable `workspace_id` and `user_id`. All additions are call-site changes only (one new migration + four new `audit.log()` calls).

## Error handling

- Alembic migration failures at test-session startup surface immediately as a pytest collection error — tests won't run on a broken schema.
- Truncation failure surfaces as a fixture error before the test body runs.
- `audit.log()` in `_fail()` and auth routes already follows the codebase pattern of wrapping in try/except (see `document_pipeline._write_audit`) — failure is logged but does not block the action.

## Testing

All tests run against the migrated schema after H3. New tests:

1. **test_audit_immutability.py**: `UPDATE audit_log` → `InternalError`; `DELETE FROM audit_log` → `InternalError`; `INSERT` still succeeds (trigger is `BEFORE UPDATE OR DELETE` only).
2. **test_audit.py** (existing, extend): `_fail()` leaves an `upload_failed` audit row; `register` leaves a `registered` row; `login` success/failure leave their rows.
3. **Regression**: full 102-test suite still passes after conftest change (isolation is identical, just faster and migration-backed).

## Acceptance criteria

- `alembic upgrade head` runs as part of every test session against `catalyst_test`.
- `UPDATE` and `DELETE` on `audit_log` raise at the database level.
- A failed document upload writes an `upload_failed` audit row.
- Register and login write audit rows with correct actions.
- Full suite passes (≥102 tests).
