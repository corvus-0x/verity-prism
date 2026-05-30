# Verity Prism — Build History

**Purpose:** Record of what shipped, when, and the test count at each milestone.  
**For what's planned:** `docs/roadmap.md`  
**For component details:** `docs/build-inventory.md`

---

## Session Log

| Date | What shipped | Tests |
|------|-------------|-------|
| 2026-05-18 | Tasks 1–6 complete. Scaffold, Docker, all 13 DB models, Alembic migration, FTS index, audit trigger, auth (JWT/bcrypt), workspaces, entities + relationships, signal types + findings. git init. | 16/16 |
| 2026-05-19 | Task 7: transactions, leads, notes APIs. | 22/22 |
| 2026-05-19 | Alembic initialized. Initial schema migrated. FTS index + audit trigger applied. | — |
| 2026-05-19 | 11 document type schemas seeded from 100+ real investigation documents: PARCEL-RECORD (370), DEED (64), 990 (235), SOS-FILING (47), UCC (52), BUILDING-PERMIT (13), AUDIT-REPORT (122), SCREENSHOT (26), OBITUARY (63), PLAT (51), CORRESPONDENCE (59). | — |
| 2026-05-19 | Task 8: document pipeline — SHA-256 evidence lock, BackgroundTasks, fail-fast error handling, no_schema auto-leads, XML direct parse path. | 29/29 |
| 2026-05-20 | Pipeline hardening: vertical-aware schema lookup, normalized extraction output (list[dict]), migration for Task 8 DB changes. Engine vs. cap architecture separation — all 11 schemas changed to vertical=general. Roadmap + build inventory created. | 29/29 |
| 2026-05-20 | Tasks 9–11: NLP search (FTS + Claude query translation), AI chat (full workspace context), full verification. Phase 1 backend complete. | 35/35 |
| 2026-05-20 | Live demo hardening: JSON fence stripping, key name normalization, batched extraction (BATCH_SIZE=40). Real deed: 41 fields extracted. NLP search and AI chat confirmed working against live extracted data. | 35/35 |
| 2026-05-26 | Tool-use chat agent. Replaced static context dump with native Anthropic tool-use agentic loop (10-round cap, synthesis pass). agent_tools.py (6 read-only tools + workspace-scoped dispatcher), agent_registry.py (vertical registry), ai_engine.py rewritten. Migration a3b8e1f92d44 (is_deleted on documents). 5 bugs caught in review. | 67/67 |
| 2026-05-26 | IDP core hardening + expansion architecture. CORS config, file size limit, soft-delete on list_documents, workspace null guard. parse_strategy + default_confidence_threshold on DocumentSchema; detect_document_type and generate_standardized_name load types from DB; pipeline routes on schema.parse_strategy; is_parseable_xml removed. OBITUARY moved to vertical="fraud". SR signal codes and fraud commentary removed from 9 general schemas. | 75/75 |
| 2026-05-28 | Frontend vertical separation: WorkspaceContext, vertical-aware sidebar + overview, workspace creation modal with vertical picker. Schema Library: GET /schemas/ endpoint, SchemaLibrary page, AppShell nav link, schemas API client, vite proxy. Full schema cleanup: case-specific content scrubbed; seed functions converted to upserts. | 75/75 |
| 2026-05-28 | Phase 2A: document viewer (react-pdf, 65/35 split, status-aware fields panel), extraction evaluation loop (evaluate + run_retry, attempt=2 retry, needs_review flag), observability (claude_call_logs table, every Claude call logged), review UI (/review queue + DocumentViewer editable mode, attempt=3 corrections). Migration e1f3a2b94c07: attempt column, needs_review enum, claude_call_logs table. | 80/80 |
| 2026-05-28 | Phase 2C: toast notifications (4 variants, ARIA, timer cleanup), document status badges (5 statuses), SSE real-time extraction status (StreamingResponse + useExtractionStream, exponential backoff), data export (4 endpoints: per-doc + workspace CSV/JSON, formula injection protection), audit log UI (paginated, timeline, search + filter). | 85/85 |
| 2026-05-29 | Phase 2C cleanup + CI hardening (PR #3). Ruff import sorting (54 fixes, 19 files). ESLint JSX parserOptions. useToast.js → useToast.jsx. DATABASE_URL in CI env. Eval tests excluded from CI. CodeRabbit critical fix: missing nextId ref (ReferenceError on every toast). ADR-0004 (SSE over polling). Blog post-009. | 82/82 CI |
| 2026-05-29 | Code audit remediation phases 1–2 (PRs #4). Security hardening (H6 weak JWT default, M1 CSV injection, M2 header injection, M3 upload allowlist). Test infra (H3: conftest.py now runs migrations instead of create_all). Audit log integrity (C1: trigger migration). Audit gaps (M4: failed uploads + auth events now audited). | 109/109 |
| 2026-05-29 | Code audit remediation phase 3 (PR #5). C2: ExtractionBatchError — _extract_batch raises on API failure instead of returning []; pipeline guard prevents silent complete on empty extraction. H5: TEXT_LIMIT=200_000 — OCR text cap raised from 4000 to 200k chars. L3: _fail deletes stored file on pipeline failure. H4: test_pipeline.py — 9 tests written TDD-style (failing test before each fix). | 118/118 |

---

## Known Issues / Decisions

| Date | Issue | Resolution |
|------|-------|------------|
| 2026-05-18 | `passlib 1.7.4` incompatible with `bcrypt 4.x` | Pinned `bcrypt==3.2.2` in requirements.txt |
| 2026-05-18 | `HTTPBearer` returns 403 (not 401) when no token present | Updated tests to assert 403 |
| 2026-05-18 | Pydantic v2 deprecation: `class Config` | Replaced with `model_config = ConfigDict(...)` |
| 2026-05-18 | `email-validator` not in requirements | Added `email-validator==2.2.0` |

---

## How to Resume

1. Start Docker: `docker-compose up -d` (from project root)
2. Verify it's running: `curl http://localhost:8000/health`
3. Run tests: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v`
4. Check `docs/roadmap.md` for what's next
