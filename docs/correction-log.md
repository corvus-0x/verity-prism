# Correction Log

Every encoded correction. Newest first. Written by `/encode-correction`.

This ledger is the compound record: each row is a manual correction that became a
durable rule, so its category of mistake can't recur. It is the deliberate-investment
trail — the proof that the development system gets stricter over time, not just the code.

| Date | Correction (what was wrong) | Surface | Where it lives |
|------|------------------------------|---------|----------------|
| 2026-06-25 | Migration created a named enum but downgrade() never dropped it (orphaned type → re-upgrade fails) | Hook | `.claude/hooks/check_migration_enum_drop.py` |
| 2026-06-21 | Routers contained DB logic (`db.query/add/commit`), violating the documented thin-router convention — architectural drift across 15 routers | Hook + refactor | `.claude/hooks/check_thin_routers.py`; DB logic moved to `app/services/*_service.py` |
| 2026-06-21 | New imports silently stripped by the ruff `--fix` hook when added in a separate edit before their first usage | CLAUDE.md rule | CLAUDE.md › Development System › Editing gotcha |
| 2026-06-21 | Six list queries omitted `is_deleted`, leaking soft-deleted rows (notes, leads, findings, relationships, connector-runs, transactions) — caught while refactoring; one flagged live by the soft-delete hook | Bug fix (category already guarded) | filters added across `app/services/*_service.py`; guard = `check_soft_delete.py` |
| 2026-06-21 | Service query on a soft-deletable model omitted the `is_deleted` filter, silently returning deleted rows (passes tests) | Hook | `.claude/hooks/check_soft_delete.py` (PostToolUse on `app/services/*.py`) |
