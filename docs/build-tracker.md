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

## Phase 2A — Extraction Intelligence + Review (2026-05-28)

| Task | What It Builds | Status |
|------|---------------|--------|
| Document viewer | Split-pane: PDF rendered in-browser (react-pdf, pdf.js bundled) + extracted fields panel. GET /documents/{id}/file endpoint. Route-based navigation, blob URL lifecycle management, status-aware fields panel. | ✅ Done |
| Extraction evaluation loop | `extraction_evaluator.py`: pure `evaluate()` + `run_retry()`. After save_extractions(), checks confidence against schema threshold, retries only failing fields as a mini-batch (attempt=2). Documents still below threshold flagged `needs_review`. | ✅ Done |
| Observability layer | `claude_call_logs` table + `_log_claude_call()` in extraction_engine.py. Every type detection and field extraction Claude call logged with model, latency_ms, input/output tokens. Isolated SessionLocal — logging never affects extraction transaction. | ✅ Done |
| Extraction review UI | `ExtractionReview.jsx` at `/review` — queue of `needs_review` documents with low-confidence field counts. Review button opens DocumentViewer with `?review=1`. ExtractionTable gains `editable` mode: inline edit, Accept/Cancel, green Corrected badge on attempt=3. | ✅ Done |

**Tests passing:** 80/80

---

## Phase 2C — UI Completeness (2026-05-28)

| Task | What It Builds | Status |
|------|---------------|--------|
| Toast notifications | Global toast system: bottom-right, title+message, 4 variants (success/error/info/warning), 4s auto-dismiss, max 3 visible. `useToast` hook + `ToastContainer`. Timer cleanup on unmount, memoized context value, ARIA live region. | ✅ Done |
| Document status badges | Pill badges on every document card — 5 extraction statuses with distinct colors. Updated `Badge.jsx` with `rounded-full`, `needs_review` (orange), `no_schema` (indigo), `failed` (red). | ✅ Done |
| Real-time extraction status (SSE) | `GET /documents/{id}/status/stream` StreamingResponse polls DB every 2s, closes on terminal status or 5-min timeout. `useExtractionStream` hook uses fetch+ReadableStream (not EventSource) for Bearer auth, exponential backoff reconnect (base 1s, cap 32s, max 5 retries). | ✅ Done |
| Data export | 4 backend endpoints: per-document CSV/JSON and workspace CSV/JSON. `_latest_extractions` helper reuses subquery pattern. ⋯ context menu on each document card (disabled when not exportable). "Export all" workspace button. | ✅ Done |
| Audit log UI | `GET /audit-log?page&limit` paginated endpoint. Timeline UI with colored dots per action type. Client-side search + action filter. Pagination with Previous/Next. "Every action on every document is tamper-proof." | ✅ Done |

**Tests passing:** 85/85

---

## Phase 2C — Cleanup + CI Hardening (2026-05-29)

| Task | What It Builds | Status |
|------|---------------|--------|
| Ruff import sorting | 54 import-sorting fixes across 19 backend files (I001). `pyproject.toml`: E712 ignored (SQLAlchemy `== False` pattern), `requires-python = ">=3.11"` added. | ✅ Done |
| useToast.jsx rename | `useToast.js` → `useToast.jsx` — Vite/Vitest requires `.jsx` extension to parse JSX syntax. | ✅ Done |
| ESLint JSX config | Added `languageOptions.parserOptions.ecmaFeatures.jsx` to `eslint.config.js` — ESLint was failing on all `.jsx` files with "Parsing error: Unexpected token <". | ✅ Done |
| CI workflow fixes | Added `DATABASE_URL` to test env (required by `config.py` on import). Excluded `tests/evals/` from automated run — eval tests call real Claude API, run locally only. | ✅ Done |
| CodeRabbit critical fix | `nextId = useRef(0)` added to `useToast.jsx` — `nextId.current++` was referenced before declaration, causing ReferenceError on every toast call. | ✅ Done |
| test_documents.jsx | Wrapped render with `ToastProvider` — `Documents` component now calls `useToast()` and requires the provider to be present in tests. | ✅ Done |

**Tests passing (CI):** 82/82 (evals excluded — require live API key)

---

## Code Audit Remediation — Phase 3 (2026-05-29)

> These are audit remediation phases (numbered 1–6 in `docs/code-audit-2026-05-29.md`) — separate from product phases (1–4 in `docs/roadmap.md`). Phases 1 and 2 of the audit remediation are already merged; this is remediation phase 3.

| Task | What It Builds | Status |
|------|---------------|--------|
| Pipeline test suite (H4) | `test_pipeline.py` — 9 tests: 3 evaluator unit tests, happy-path integration, C2 failure path, H5 truncation regression, L3 file cleanup, zero-field schema edge case. Written TDD-style: failing test committed before each fix. | ✅ Done |
| C2 fix — ExtractionBatchError | `_extract_batch` raises `ExtractionBatchError` on API failure instead of swallowing and returning `[]`. `extract_fields` re-raises if all batches fail. Pipeline-level guard: claude schema + defined fields + zero results → `_fail`. `run_retry` catches the exception non-fatally. | ✅ Done |
| H5 fix — TEXT_LIMIT | `TEXT_LIMIT = 200_000` constant in `extraction_engine.py`. OCR text cap raised from 4000 to 200k chars (≈50k tokens). Warning logged when a document exceeds the new limit. | ✅ Done |
| L3 fix — file cleanup in `_fail` | `_fail` in `document_pipeline.py` now calls `Path(doc.file_path).unlink(missing_ok=True)` before writing the audit log. No orphaned files on disk after any pipeline failure. | ✅ Done |

**Tests passing:** 118/118 (PR #5)

---

## Phase 2 — Remaining Builds (2D — Data Connectors)

> Signal detection (formerly 2B) has been moved to Phase 3 — rules are domain logic, not engine infrastructure. See roadmap Phase 3A.

| Task | What It Builds | Phase | Status |
|------|---------------|-------|--------|
| Data connectors | `app/services/connectors/` — irs_teos.py (wraps existing fetch_990_xml.py), ohio_sos.py, county_auditor.py, building_permits.py. Each connector fetches public data and hands files to the pipeline. New endpoints: `POST /workspaces/{id}/connectors/{source}`. | 2D | 🔲 |

---

## Phase 3 — Vertical Packaging (Roadmap)

> **Trigger:** Phase 2D connectors complete. Extraction reliability measurable (2A done ✅). At least one full end-to-end case run with observable confidence metrics.

### 3A — Fraud Vertical v1.0

| Task | What It Builds | Status |
|------|---------------|--------|
| Signal detection framework | `signal_rules` table + rule evaluator against `document_extractions`. Built here as fraud cap logic, not generic engine infrastructure — rules are domain-specific. The framework is what gets extracted into the engine if a second vertical needs it. | 🔲 |
| SR signal definitions | SR-003 (valuation anomaly), SR-004 (UCC burst), SR-005 (zero consideration), SR-015 (deed title defect), SR-021 (revenue spike), SR-024 (charity conduit), SR-025 (false disclosure), SR-026 (construction overage). Full catalog in roadmap. | 🔲 |
| Network graph | Visual map of entities, properties, transactions, document links. Fraud cap defines edge types (officer_of, controls, owns, financed_by) and what to render. Engine provides entities/relationships tables. | 🔲 |
| Investigation timeline | Chronological view of fraud-relevant events across extracted date fields. Fraud cap selects which fields matter and what sequence means. | 🔲 |
| Referral export | AG/IRS/FBI/Farm Credit referral package generators. Fraud cap only — format is domain-specific. | 🔲 |
| Signal type seed data migration | Move `SIGNAL_TYPES_SEED` out of `findings.py` router and into `app/caps/fraud/signal_types.py` cap installer. Currently misplaced in the engine layer. | 🔲 |

### 3B — Insurance Vertical v1.0

| Task | What It Builds | Status |
|------|---------------|--------|
| Insurance schema set | INSURANCE-FORM, ACORD-FORM, PROPERTY-APPRAISAL, CONTRACTOR-INVOICE, MEDICAL-RECORD. Shared with fraud: PARCEL-RECORD. | 🔲 |
| Claims signal definitions | Contractor invoice date after claim close, estimated repair > appraised value, duplicate claims across policies. Defined when vertical is built. | 🔲 |
| Claim intake workflow | Upload → extract → flag discrepancies → adjuster review queue → decision. | 🔲 |
| Claims export | Claims system API push + structured PDF report. Integration TBD based on client system. | 🔲 |

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
| 2026-05-28 | Phase 2A complete. Extraction evaluation loop: evaluator runs after save_extractions(), retries only low-confidence fields as a mini-batch (attempt=2), flags needs_review if still below threshold. Observability: claude_call_logs table, every extraction Claude call logged with latency + tokens, isolated session. Review UI: /review queue page + DocumentViewer editable mode (?review=1) + ExtractionTable inline correction (attempt=3, confidence=1.0). list_extractions fixed to return latest-attempt-per-field by default (?include_history=true for full history). Migration e1f3a2b94c07: attempt column, needs_review enum value, claude_call_logs table. ADRs added (docs/decisions/). 80/80 tests. |
| 2026-05-29 | Phase 2C cleanup + CI hardening (PR #3). Ruff UP017 + import sorting across 19 files. ESLint JSX parserOptions. useToast.js → useToast.jsx. DATABASE_URL in CI env. Eval tests excluded from CI. CodeRabbit caught missing nextId ref (critical — ReferenceError on every toast call). test_documents.jsx wrapped with ToastProvider. ADR-0004 written (SSE over polling). Blog post-009 written. 82/82 CI tests (evals excluded). |
| 2026-05-29 | Code audit Phase 3 (PR #5). `ExtractionBatchError`: `_extract_batch` raises on API failure; `extract_fields` re-raises if all batches fail; pipeline guard prevents silent complete on empty claude extraction. `TEXT_LIMIT = 200_000`: OCR text cap raised from 4000 chars — full document evidence reaches Claude. `_fail` file cleanup: stored file deleted on pipeline failure. `test_pipeline.py`: 9 new tests written TDD-style (failing test before each fix). 118/118 tests. |
| 2026-05-28 | Phase 2C complete. Toast system (useToast + ToastContainer, timer cleanup, ARIA). Document status pill badges (needs_review/no_schema/failed added to Badge.jsx). SSE real-time extraction status (StreamingResponse + useExtractionStream with exponential backoff). Data export: 4 endpoints (per-doc + workspace CSV/JSON) + ⋯ context menu frontend. Audit log: paginated backend + timeline UI with search/filter. 85/85 tests. |
