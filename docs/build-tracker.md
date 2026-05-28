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
| Task 8: Document Pipeline | SHA-256 hash → OCR → AI extraction → FTS index | ✅ Done |
| Task 9: NLP Search | Plain-English query → SQL/FTS results | ✅ Done |
| Task 10: AI Chat | Claude with full workspace context | ✅ Done |
| Task 11: Full Verification | All tests passing end-to-end in Docker, audit log immutability check | ✅ Done |
| Live demo verification | Real deed uploaded, 41 fields extracted, NLP search returned results, AI chat answered questions | ✅ Done |

**Tests passing:** 22/22 (Phase 1 baseline)

---

## Agentic Layer — Status

| Task | What It Builds | Status |
|------|---------------|--------|
| Tool-use chat agent | Replace static context dump with native Anthropic tool-use loop — 6 read-only tools, 10-round cap, synthesis pass, workspace-scoped dispatcher, vertical registry | ✅ Done |

**Tests passing:** 67/67

---

## IDP Core Hardening + Expansion Architecture — Status

| Task | What It Builds | Status |
|------|---------------|--------|
| Core fixes | CORS configurable, file size bounded, soft-delete on list_documents, get_workspace_or_404 null guard, Alembic verified on fresh DB | ✅ Done |
| parse_strategy on DocumentSchema | Schema owns XML vs Claude routing decision — pipeline no longer hardcodes document type strings | ✅ Done |
| default_confidence_threshold on DocumentSchema | Per-schema quality baseline for extraction evaluator (Phase 2A) | ✅ Done |
| Dynamic type detection | detect_document_type loads known types from document_schemas table — adding a schema row makes the type immediately detectable | ✅ Done |
| Pipeline uses parse_strategy | document_pipeline.py reads schema.parse_strategy; is_parseable_xml removed | ✅ Done |
| naming.py loads types from DB | generate_standardized_name loads doc types from DB; last hardcoded type list removed | ✅ Done |
| Seeds updated | All 11 seed constructors include parse_strategy and default_confidence_threshold; required fields in DEED + PARCEL-RECORD have per-field confidence_threshold | ✅ Done |
| OBITUARY → fraud vertical | Migration + seed move OBITUARY to vertical="fraud"; general workspaces no longer receive it | ✅ Done |
| Schema descriptions cleaned | SR signal codes (SR-0XX) and fraud investigation commentary removed from 9 general schema field descriptions and extraction prompts | ✅ Done |

**Tests passing:** 75/75

---

## Engine UI + Platform Layer — Status (2026-05-28)

| Task | What It Builds | Status |
|------|---------------|--------|
| Frontend vertical separation | WorkspaceContext fetches workspace once at layout level; WorkspaceSidebar driven by workspace.vertical — engine nav always, cap nav only for matching vertical; Overview stat cards adapt to vertical; VERTICAL_SECTIONS map makes adding new vertical nav a one-line change | ✅ Done |
| Workspace creation modal | Replaced browser prompt() with inline form — captures name + vertical (General / Fraud Investigation / Insurance); General is default; backend vertical field corrected from null to "general" | ✅ Done |
| Schema Library — backend | GET /schemas/ endpoint in new schemas.py router; registered in main.py; returns all active schemas with field_count and full field list; /schemas proxy added to vite.config.js | ✅ Done |
| Schema Library — frontend | SchemaLibrary.jsx at /schemas; cards grouped by vertical; expandable field list (name/type/description/required); "Schema Library" nav link in AppShell header; schemas.js API client | ✅ Done |
| Schema cleanup — full pass | All case-specific content removed from all 11 schemas (county names, person names, org names, signal codes); seed functions converted from skip-if-exists to upsert — re-running seed updates live DB | ✅ Done |

**Tests passing:** 75/75 (no backend changes requiring new tests)

---

## Phase 2 — Next Builds

| Task | What It Builds | Phase | Status |
|------|---------------|-------|--------|
| Document viewer | Split-pane: PDF rendered in-browser (left) + extraction fields (right). New endpoint: GET /documents/{id}/file. Field-level linking. Prerequisite for extraction review UI. | 2A | 🔲 Next |
| Extraction evaluation loop | Post-extract evaluator: confidence check → retry with alternate prompt → escalate to human review if retry fails. First systematic data on where extraction fails. | 2A | 🔲 |
| Extraction review UI | Review queue for low-confidence fields. Reviewer sees document viewer + flagged fields. Accept or correct. Requires document viewer. | 2A | 🔲 |
| Observability layer | Log every Claude call: model, latency, tokens, confidence distribution per doc type. Extraction evaluator writes to this. | 2A | 🔲 |
| Real-time extraction status | SSE on GET /documents/{id}/status/stream — pushes pending→processing→complete to frontend. Document list updates live. | 2C | 🔲 |
| Data export | GET /documents/{id}/extractions.csv + .json; GET /workspaces/{id}/extractions.csv. Generic engine export — vertical-specific formats stay in the cap. | 2C | 🔲 |
| Audit log UI | Read-only chronological log per workspace. Surfaces the existing immutable audit_log table. Compliance selling point. | 2C | 🔲 |
| Signal detection framework | signal_rules table + rule evaluator against document_extractions. Framework only — no specific rules (those are vertical cap content). | 2B | 🔲 |
| Data connectors | irs_teos.py, ohio_sos.py, county_auditor.py, building_permits.py — each fetches public data, hands to pipeline. | 2D | 🔲 |

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
| 2026-05-19 | Schema derivation complete. 11 document type schemas seeded from 100+ real investigation documents: PARCEL-RECORD (370), DEED (64), 990 (235), SOS-FILING (47), UCC (52), BUILDING-PERMIT (13), AUDIT-REPORT (122), SCREENSHOT (26), OBITUARY (63), PLAT (51), CORRESPONDENCE (59). |
| 2026-05-19 | Task 8 complete. Document pipeline: BackgroundTasks, fail-fast error handling, no_schema auto-leads, XML direct parse path. 29/29 tests passing. |
| 2026-05-20 | Pipeline hardening: vertical-aware schema lookup, normalized extraction output (list[dict]), Alembic migration for Task 8 DB changes. Engine vs. cap architecture separation — all 11 schemas changed to vertical=general. Roadmap rewritten. Build inventory + roadmap created. |
| 2026-05-20 | Tasks 9–11 complete. NLP search (FTS + Claude query translation), AI chat (full workspace context), full verification (35/35 tests, live API, audit log immutability confirmed). Phase 1 backend complete. |
| 2026-05-20 | Live demo hardening: 3 production bugs found and fixed — JSON fence stripping (shared utility), key name normalization (belt+suspenders), batched extraction (BATCH_SIZE=40, ends token truncation). Real deed: 41 fields extracted. NLP search and AI chat confirmed working against live extracted data. |
| 2026-05-26 | Tool-use chat agent complete. Replaced static context dump with native Anthropic tool-use agentic loop (10-round cap, synthesis pass). 3 new service files: agent_tools.py (6 read-only tools + dispatcher), agent_registry.py (vertical registry), ai_engine.py rewritten. Router fix: user message saved after chat() returns to prevent duplicate history. 5 bugs caught in review: get_leads wrong column, Decimal zero falsy check, duplicate message timing, missing filename/doc_type in query_extractions, missing is_error flag. 67/67 tests. |
| 2026-05-26 (evening) | IDP core hardening + expansion architecture. Core fixes: CORS config, file size limit, soft-delete on list_documents, workspace null guard, Alembic verified on fresh DB. Expansion: parse_strategy + default_confidence_threshold on DocumentSchema (migration + seeds); KNOWN_DOCUMENT_TYPES removed — detect_document_type now queries DB; pipeline routes on schema.parse_strategy not type strings; naming.py loads doc types from DB; is_parseable_xml removed (dead code). Schema cleanup: OBITUARY moved to vertical="fraud" (migration + seed); SR signal codes and fraud investigation commentary removed from 9 general schema descriptions and extraction prompts. 75/75 tests. |
| 2026-05-28 | Engine UI + platform layer. Frontend vertical separation: WorkspaceContext, vertical-aware sidebar and overview, workspace creation modal with vertical picker (replaces prompt()). Schema Library: GET /schemas/ endpoint, SchemaLibrary page at /schemas, AppShell nav link, schemas API client, vite proxy. Full schema cleanup: case-specific content (county names, person names, org names, signal codes) scrubbed from all 11 schemas in seed file and live DB; seed functions converted to upserts. Roadmap + build inventory + build tracker updated. Phase 2 next builds: document viewer (next), extraction eval, review UI, real-time status, export, audit log UI, signal framework, connectors. 75/75 tests. |
