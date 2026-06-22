---
name: gen-migration
description: Generate an Alembic migration for the Verity Prism backend. Reads current model changes, runs autogenerate inside Docker, shows the result. Invoke as /gen-migration "description of change".
---

The user has invoked `/gen-migration "<description>"`. Generate and validate an Alembic migration.

## Steps

### 1. Confirm what changed

Before generating, read the relevant model file(s) in `backend/app/models/` to understand exactly what column or table changed. State it clearly so the user can verify you have the right change.

### 2. Generate the migration

Run autogenerate inside the running Docker backend container:

```bash
docker-compose run --rm backend alembic revision --autogenerate -m "<description>"
```

If the backend container is not running, start it first:
```bash
docker-compose up -d db backend
```

### 3. Read and show the migration

Find the new migration file in `backend/alembic/versions/`. Read the entire file and show the user:
- The `upgrade()` function — what SQL will run on `alembic upgrade head`
- The `downgrade()` function — what SQL will run on rollback

### 4. Verify correctness

Check the migration against these rules:

| Rule | Why |
|---|---|
| All new columns must have defaults or be nullable | Non-null columns on existing tables will fail if rows exist |
| Enum additions use `ALTER TYPE` not `DROP/CREATE` | DROP destroys data |
| Migrations targeting `audit_log` must NEVER include DELETE | The PostgreSQL trigger blocks it — migration will fail |
| Soft-delete columns (`is_deleted`, `deleted_at`) should be added together | The service layer always expects both |
| Search vector columns should be `TSVECTOR`, not `TEXT` | TEXT won't use the GIN index |

Flag any violation clearly before the user runs `upgrade head`.

### 5. Confirm before running

Tell the user:
```text
Migration generated: backend/alembic/versions/<id>_<slug>.py

To apply:
  docker-compose run --rm backend alembic upgrade head

To roll back:
  docker-compose run --rm backend alembic downgrade -1

To run tests after:
  docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Do NOT run `alembic upgrade head` automatically — always let the user do this after reviewing the migration.

## Current migration head

The current head is tracked in `backend/alembic/versions/`. The most recent migration sets the head. Each new migration's `down_revision` must match the current head.
