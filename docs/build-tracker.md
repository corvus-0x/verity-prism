# Verity Prism — Build Tracker

**Plan:** `docs/superpowers/plans/2026-05-17-phase1-backend-api.md`
**Frontend Plan:** `docs/superpowers/plans/2026-05-17-phase1-frontend.md` (after backend complete)

---

## Backend Phase 1 — Status

| Task | What It Builds | Status |
|------|---------------|--------|
| Task 1: Scaffold + Docker | Folder structure, Dockerfile, docker-compose, config, main.py | ✅ Done |
| Task 2: DB Models + Migration | All 13 SQLAlchemy models, Alembic migration, FTS index, audit trigger | ✅ Done |
| Task 3: Auth | JWT login/register, bcrypt hashing, `get_current_user` dependency | ✅ Done |
| Task 4: Workspaces | CRUD endpoints, membership access control | ✅ Done |
| Task 5: Entities + Relationships | CRUD, soft delete, relationship links | ✅ Done |
| Task 6: Signal Types + Findings | Signal type seed data, findings CRUD | ✅ Done |
| Task 7: Transactions + Leads + Notes | Financial transactions CRUD, investigation leads CRUD, notes on any entity | ✅ Done |
| Task 2.5: Document Schema Seeds | PARCEL-RECORD (340) + DEED (64) + 990 (235) + SOS-FILING (47) + UCC (46) + BUILDING-PERMIT (13) + AUDIT-REPORT (122) seeded. | ✅ Done |
| Task 8: Document Pipeline | SHA-256 hash → OCR → AI extraction → FTS index | ⬜ Next |
| Task 9: NLP Search | Plain-English query → SQL/FTS results | ⬜ |
| Task 10: AI Chat | Claude with full workspace context | ⬜ |
| Task 11: Full Verification | All tests passing end-to-end in Docker, audit log immutability check | ⬜ |

**Tests passing:** 22/22

---

## Known Issues / Decisions

| Date | Issue | Resolution |
|------|-------|------------|
| 2026-05-18 | `passlib 1.7.4` incompatible with `bcrypt 4.x` | Pinned `bcrypt==3.2.2` in requirements.txt |
| 2026-05-18 | `HTTPBearer` returns 403 (not 401) when no token present | Updated tests to assert 403 |
| 2026-05-18 | Pydantic v2 deprecation: `class Config` | Replaced with `model_config = ConfigDict(...)` |
| 2026-05-18 | `email-validator` not in requirements | Added `email-validator==2.2.0` |

---

## How to Resume a Session

1. Start Docker: `docker-compose up -d` (from project root)
2. Verify it's running: `curl http://localhost:8000/health`
3. Run tests: `docker-compose exec -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v`
4. Pick up at the next ⬜ task in the table above

---

## Session Log

| Date | Work Done |
|------|-----------|
| 2026-05-18 | Tasks 1–6 complete. git init. 16/16 tests passing. First commit. |
| 2026-05-19 | Task 7 complete. Transactions, leads, and notes APIs. 22/22 tests passing. |
| 2026-05-19 | Task 2 migration complete. Alembic initialized, initial schema migrated, FTS index + audit trigger applied. |
