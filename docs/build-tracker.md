# Verity Prism — Build Tracker

**Purpose:** History of what was built, why decisions were made, and what changed at each milestone. For what's planned next, see `docs/roadmap.md`. For current component status, see `docs/build-inventory.md`. Updated via `/log-session`.

---

## Backend Phase 1 (2026-05-18 to 2026-05-20)

| Task | What It Builds | Why |
|------|---------------|-----|
| Task 1: Scaffold + Docker | Folder structure, Dockerfile, docker-compose, config, main.py | Everything runs in Docker from day one — no "works on my machine" drift between dev and prod |
| Task 2: DB Models + Migration | All 13 SQLAlchemy models, Alembic migration, FTS index, audit trigger | Row-per-field extraction table is the central IDP design decision — every field individually queryable without JSON parsing |
| Task 3: Auth | JWT login/register, bcrypt hashing, `get_current_user` dependency | Evidence platform needs auth before any data goes in |
| Task 4: Workspaces | CRUD endpoints, membership access control | Workspace = case container. All data is workspace-scoped — no cross-case leakage |
| Task 5: Entities + Relationships | CRUD, soft delete, relationship links | Entities are engine-level. Soft delete — nothing is ever hard-deleted on an evidence platform |
| Task 6: Signal Types + Findings | Signal type seed data, findings CRUD | Findings are the output of signal detection — needed before pipeline can produce them |
| Task 7: Transactions + Leads + Notes | Financial transactions CRUD, investigation leads CRUD, notes on any entity | Transactions + leads are fraud-vertical scaffolding that happens to live in the engine layer |
| Task 2.5: Document Schema Seeds | PARCEL-RECORD (370) + DEED (64) + 990 (235) + SOS-FILING (47) + UCC (52) + BUILDING-PERMIT (13) + AUDIT-REPORT (122) + SCREENSHOT (26) + OBITUARY (63) + PLAT (51) + CORRESPONDENCE (59) | Derived from 100+ real investigation documents. Schema registry is the foundation — no schemas = no extraction |
| Task 8: Document Pipeline | SHA-256 hash → OCR → AI extraction → FTS index | Hash is first, always — evidence lock before any processing. BackgroundTasks fires after HTTP response so upload is instant |
| Task 9: NLP Search | Plain-English query → SQL/FTS results | Investigators shouldn't need to know field names. Query translation lets Claude bridge natural language to structured DB queries |
| Task 10: AI Chat | Claude with full workspace context | The end goal: ask a question about a case and get an answer grounded in actual extracted document data |
| Task 11: Full Verification | All tests passing end-to-end in Docker, audit log immutability check | Phase 1 doesn't ship until the audit trigger is confirmed working in the DB, not just in code |
| Live demo verification | Real deed uploaded, 41 fields extracted, NLP search returned results, AI chat answered questions | Proved the pipeline works against real evidence before building anything on top of it |

**Tests passing:** 35/35

---

## Agentic Layer (2026-05-26)

| Task | What It Builds | Why |
|------|---------------|-----|
| Tool-use chat agent | Replace static context dump with native Anthropic tool-use loop — 6 read-only tools, 10-round cap, synthesis pass, workspace-scoped dispatcher, vertical registry | Static context dump front-loaded all workspace data into every message — expensive, stale, and didn't scale. Tool use lets Claude pull only what it needs. `workspace_id` is injected by the dispatcher, never passable by Claude — cross-workspace access is architecturally impossible |

**Tests passing:** 67/67

**Bugs caught in review:** get_leads querying wrong column; Decimal zero evaluated as falsy; duplicate message timing (message saved before chat() returned, causing history duplication); missing filename/doc_type in query_extractions response; missing is_error flag on tool failures.

---

## IDP Core Hardening + Expansion Architecture (2026-05-26)

Decisions made before any vertical work could start. These were flagged in principal dev review.

| Task | What It Builds | Why |
|------|---------------|-----|
| Core fixes | CORS configurable, file size bounded, soft-delete on list_documents, get_workspace_or_404 null guard, Alembic verified on fresh DB | Deployment-blockers. CORS hardcoded to localhost was a security hole. get_workspace_or_404 returning None instead of 404 would cause 500s in prod |
| parse_strategy on DocumentSchema | Schema owns XML vs Claude routing decision — pipeline no longer hardcodes document type strings | Adding a new document type should be a DB row, not a code change. Hardcoded type strings made that impossible |
| default_confidence_threshold on DocumentSchema | Per-schema quality baseline for extraction evaluator | Different document types have different extraction difficulty. A 370-field parcel record tolerates lower confidence than a 64-field deed |
| Dynamic type detection | detect_document_type loads known types from document_schemas at call time | Same principle: adding a schema row immediately makes that type detectable. No redeployment |
| Pipeline uses parse_strategy | document_pipeline.py reads schema.parse_strategy; is_parseable_xml removed | Dead code removed. XML vs Claude is a schema property, not a runtime condition |
| naming.py loads types from DB | generate_standardized_name loads doc types from DB; last hardcoded type list removed | Completed the "no hardcoded type lists anywhere" goal |
| Seeds updated | All 11 seed constructors include parse_strategy and default_confidence_threshold | Seeds must match models exactly or a fresh DB install fails |
| OBITUARY → fraud vertical | Migration + seed move OBITUARY to vertical="fraud"; general workspaces no longer receive it | OBITUARY is fraud-investigation-specific. A general workspace or insurance workspace has no business seeing it |
| Schema descriptions cleaned | SR signal codes (SR-0XX) and fraud investigation commentary removed from 9 general schema field descriptions and extraction prompts | Signal codes are fraud cap content. If they're in a general schema, they leak fraud domain knowledge into every vertical |

**Tests passing:** 75/75

---

## Engine UI + Platform Layer (2026-05-28)

| Task | What It Builds | Why |
|------|---------------|-----|
| Frontend vertical separation | WorkspaceContext fetches workspace once at layout level; WorkspaceSidebar driven by workspace.vertical — engine nav always, cap nav only for matching vertical; Overview stat cards adapt to vertical; VERTICAL_SECTIONS map | Adding a new vertical's nav is a one-line change in VERTICAL_SECTIONS. Without this, vertical logic would scatter across every component |
| Workspace creation modal | Replaced browser prompt() with inline form — captures name + vertical (General / Fraud Investigation / Insurance); General is default | prompt() is blocking, unstyled, and can't be tested. Vertical selection at creation time drives the entire workspace experience |
| Schema Library — backend | GET /schemas/ endpoint in new schemas.py router; returns all active schemas with field_count and full field list | Investigators need to know what field names exist before they can build NLP queries or write signal rules |
| Schema Library — frontend | SchemaLibrary.jsx at /schemas; cards grouped by vertical; expandable field list (name/type/description/required) | Schema Library is a selling point — shows the breadth of what the platform can extract before any documents are uploaded |
| Schema cleanup — full pass | All case-specific content removed from all 11 schemas (county names, person names, org names, signal codes); seed functions converted from skip-if-exists to upsert | Schemas are a product artifact, not an investigation artifact. Case content in schema descriptions would be a confidentiality breach when the platform serves multiple clients. Upsert means re-running seed is safe against a live DB |

**Tests passing:** 75/75

---

## Phase 2A — Extraction Intelligence + Review (2026-05-28)

| Task | What It Builds | Why |
|------|---------------|-----|
| Document viewer | Split-pane: PDF rendered in-browser (react-pdf, pdf.js bundled) + extracted fields panel. GET /documents/{id}/file endpoint. Route-based navigation, blob URL lifecycle management, status-aware fields panel | Side-by-side view is how investigation actually works — the investigator needs to see the source document and the extracted data at the same time to catch errors |
| Extraction evaluation loop | `extraction_evaluator.py`: pure `evaluate()` + `run_retry()`. After save_extractions(), checks confidence against schema threshold, retries only failing fields as a mini-batch (attempt=2). Documents still below threshold flagged `needs_review` | Claude extraction is probabilistic. Without a confidence check, low-quality extractions silently pass. The evaluator catches them automatically; human review is the escalation path |
| Observability layer | `claude_call_logs` table + `_log_claude_call()` in extraction_engine.py. Every type detection and field extraction Claude call logged with model, latency_ms, input/output tokens. Isolated SessionLocal | Can't tune extraction quality without measuring it. Isolated session: logging failure must never affect extraction — these are separate concerns |
| Extraction review UI | `ExtractionReview.jsx` at `/review` — queue of `needs_review` documents. DocumentViewer with `?review=1` for editable mode. ExtractionTable: inline edit, Accept/Cancel, green Corrected badge on attempt=3 | Human correction is `attempt=3`. All attempts are preserved — history is never deleted. list_extractions returns latest-attempt-per-field by default so callers always see the best available value |

**Tests passing:** 80/80

**Migration:** `e1f3a2b94c07` — attempt column (INTEGER NOT NULL DEFAULT 1) on document_extractions, needs_review added to extraction_status enum, claude_call_logs table with indexes on document_id and called_at.

---

## Phase 2C — UI Completeness (2026-05-28)

| Task | What It Builds | Why |
|------|---------------|-----|
| Toast notifications | Global toast system: bottom-right, title+message, 4 variants (success/error/info/warning), 4s auto-dismiss, max 3 visible. `useToast` hook + `ToastContainer`. Timer cleanup on unmount, memoized context value, ARIA live region | Every user action that hits the API needs feedback. Without toasts, failures are invisible |
| Document status badges | Pill badges on every document card — 5 extraction statuses with distinct colors. Updated `Badge.jsx` with `rounded-full`, `needs_review` (orange), `no_schema` (indigo), `failed` (red) | Status is the most important information on a document card — it tells the investigator whether the document is usable |
| Real-time extraction status (SSE) | `GET /documents/{id}/status/stream` StreamingResponse polls DB every 2s, closes on terminal status or 5-min timeout. `useExtractionStream` hook uses fetch+ReadableStream (not EventSource) for Bearer auth, exponential backoff reconnect (base 1s, cap 32s, max 5 retries) | EventSource doesn't support custom headers — can't pass a Bearer token. fetch+ReadableStream is the correct pattern for authenticated SSE |
| Data export | 4 backend endpoints: per-document CSV/JSON and workspace CSV/JSON. Formula injection protection (OWASP CSV-injection). ⋯ context menu on each document card. "Export all" workspace button | Export is asked for in every evaluation. Formula injection protection: field values starting with `= + - @` are prefixed with a single quote so Excel/Sheets doesn't execute them |
| Audit log UI | `GET /audit-log?page&limit` paginated endpoint. Timeline UI with colored action dots, client-side search + action filter, Previous/Next pagination | "Every action on every document is logged and tamper-proof" needs to be visible, not just true |

**Tests passing:** 85/85

---

## Phase 2C — Cleanup + CI Hardening (2026-05-29, PR #3)

| Task | What It Builds | Why |
|------|---------------|-----|
| Ruff import sorting | 54 import-sorting fixes across 19 backend files (I001). `pyproject.toml`: E712 ignored (SQLAlchemy `== False` pattern), `requires-python = ">=3.11"` added | CI must be clean before any external review. E712 suppressed because SQLAlchemy's `filter(Model.field == False)` is the idiomatic pattern, not a bug |
| useToast.jsx rename | `useToast.js` → `useToast.jsx` | Vite/Vitest requires `.jsx` extension to parse JSX syntax. js files are not processed through the JSX transform |
| ESLint JSX config | Added `languageOptions.parserOptions.ecmaFeatures.jsx` to `eslint.config.js` | ESLint was failing on all `.jsx` files with "Parsing error: Unexpected token <" |
| CI workflow fixes | Added `DATABASE_URL` to test env. Excluded `tests/evals/` from automated run | config.py validates DATABASE_URL at import time — missing it caused every test import to fail. Eval tests call real Claude API and cost money; they run locally only |
| CodeRabbit critical fix | `nextId = useRef(0)` added to `useToast.jsx` | CodeRabbit caught this in PR review. `nextId.current++` was referenced before declaration — ReferenceError on every toast call. Would have been invisible in dev because React's error boundary swallowed it |
| test_documents.jsx | Wrapped render with `ToastProvider` | Documents component calls `useToast()` — requires the provider in the tree. Missing it caused all document component tests to fail with "useToast must be used within a ToastProvider" |

**Tests passing (CI):** 82/82 (evals excluded — require live API key)

---

## Code Audit Remediation — Phases 1–2 (2026-05-29, PR #4)

> Audit conducted by Opus 4.8 on 2026-05-29. Full findings in `docs/code-audit-2026-05-29.md`. Phases 1 and 2 addressed the most critical server-side security and audit-integrity findings.

| Finding | What was fixed | Why it mattered |
|---------|---------------|-----------------|
| H6 — Weak JWT default | Removed `dev-secret-key-change-in-production` fallback from docker-compose. App now fails fast if SECRET_KEY is unset or too short | The default was publicly known. Anyone could forge a valid JWT for any user_id and bypass auth entirely |
| M1 — CSV formula injection | Cells beginning with `= + - @ \t \r` prefixed with single quote on CSV export | A value like `=CMD()` in a deed's grantor_name field would execute as a formula when opened in Excel. Attacker-influenced via OCR of uploaded documents |
| M2 — Header injection in Content-Disposition | Filenames sanitized to `[^\w\-.]` allowlist; RFC 5987 encoding for Content-Disposition | CR/LF in a raw upload filename could inject arbitrary response headers. `"` stripping alone didn't block it |
| M3 — No upload type allowlist | Extension allowlist enforced at upload; non-allowlisted files rejected 415. Served files get `X-Content-Type-Options: nosniff` + forced `attachment` disposition for non-inline types | Without an allowlist, an uploaded .html file served back could be MIME-sniffed into stored XSS in the app's origin |
| H3 — Tests never ran migrations | conftest.py replaced `Base.metadata.create_all` with `alembic upgrade head` | create_all builds the schema from ORM models, not migrations. Any migration-only guarantee (triggers, enum values, DDL) was untested and could silently diverge from production |
| C1 — Audit trigger didn't exist | Migration `3f29a7ad2392` creates the `BEFORE UPDATE OR DELETE` trigger on audit_log | The trigger was specified, documented in CLAUDE.md, and never implemented. CLAUDE.md said it was a database-level control; it was enforced by nothing |
| M4 — Audit gaps on failures and auth | Failed pipeline runs, login success/failure, registration, and conversation creation now all write audit rows | For a forensic platform, who-accessed-what-when must include auth events. A failed upload with no audit record was undetectable |

**Tests passing:** 109/109

---

## Code Audit Remediation — Phase 3 (2026-05-29, PR #5)

> Phase 3 targeted extraction pipeline correctness — the C2 silent-failure bug, H5 text truncation, and L3 orphaned files. H4 (no pipeline tests) was addressed first as the safety net for the other fixes.

| Finding | What was fixed | Why it mattered |
|---------|---------------|-----------------|
| H4 — No pipeline test coverage | `test_pipeline.py` — 9 tests: evaluator unit tests, happy-path integration, C2 failure path, H5 truncation regression, L3 file cleanup, zero-field schema edge case. TDD: failing test committed before each fix | Without pipeline tests, every fix to extraction_engine or document_pipeline was unverifiable. The happy-path test also confirmed the fix didn't break the normal case |
| C2 — Silent false-complete on API failure | `_extract_batch` now raises `ExtractionBatchError` on failure instead of swallowing and returning `[]`. `extract_fields` re-raises if all batches fail. Pipeline-level guard: claude schema + defined fields + zero results → `_fail` | Claude API down + document pipeline = doc marked `complete` with zero extracted fields. Evidence looked successfully processed; none of it was extracted. A false complete is worse than a visible failure on an evidence platform |
| H5 — 4000-char OCR text cap | `TEXT_LIMIT = 200_000` constant. `ocr_text[:4000]` → `ocr_text[:TEXT_LIMIT]` in `_extract_batch`. Warning logged when exceeded | Every extraction batch saw only the first 4000 chars regardless of document length. A 370-field parcel record or a 235-field 990 — any field whose value appeared after position 4000 could never be extracted. Directly contradicted the platform's "extract every data point" premise |
| L3 — Orphaned files on pipeline failure | `_fail` calls `Path(doc.file_path).unlink(missing_ok=True)` before writing the audit log | Pipeline writes the file to disk before OCR. If OCR fails, the file stayed on disk forever with no cleanup. `missing_ok=True` handles the case where the file was never written or already cleaned up |

**Tests passing:** 118/118

---

## Docs & Planning — Build Tracker Restructure + Roadmap Alignment (2026-05-29)

| Decision | What changed | Why |
|----------|-------------|-----|
| Build tracker restructured to pure history | Removed Phase 2 Remaining and Phase 3 Vertical Packaging forward-looking tables. Added Why column to all task rows. Added Deferred & Relocated Work section to capture decisions with full reasoning. | The tracker was half forward-looking, half history — each doc should do one job. Forward-looking items belong in roadmap.md. The Deferred section preserves reasoning for moved items so future work doesn't start from scratch. |
| Signal detection confirmed Phase 3A | Was listed as Phase 2B remaining. Moved to Phase 3A as fraud cap logic, not engine infrastructure. | Building a generic framework before two verticals exist means designing an abstraction for one use case. Every vertical has different operators, thresholds, and evidence patterns. Wait to see two real implementations before extracting what's common. |
| Code audit phases 4–6 added as roadmap Phase 2D | Not previously on the roadmap. Placed in Phase 2 because these are engine correctness fixes that belong before vertical packaging starts. Former Phase 2D (data connectors) renamed Phase 2E. | Phases 4–6 are search integrity, thin routers, and JWT hardening — engine correctness, not vertical work. Must land before Phase 3 so verticals are built on a stable foundation. |
| Fixed five stale roadmap references | Phase 3 trigger now requires 2D complete (not just 2A). Phase 3A signal definitions removed "Phase 2B framework" label. Cross-phase principles updated — signal detection is Phase 3 work, not a Phase 2 prerequisite. | Stale references compound confusion when onboarding or planning. The roadmap must reflect the actual phase sequence. |
| Blog stays organic, session log serves interviews/sales | No system for blog timing — write when a discovery moment hits. Build tracker's Why column is the structured reference for demos and interviews. | Forced blog scheduling produces mediocre posts. The discovery is the story. The session log keeps the sales pitch accurate without requiring blog discipline. |
| Built /log-session skill | `verity-prism-log-session` skill at `~/.claude/skills/verity-prism-log-session/`. Invoked as `/log-session` at end of session. | The Why column is what feeds interviews and sales conversations but is hard to keep current manually. One command at session end keeps it accurate. |

---

## Deferred & Relocated Work

Things that were planned for one phase and moved, or explicitly punted. Captured here with the reasoning so when we reach that phase we're not starting from scratch.

---

### Signal Detection Framework — moved Phase 2B → Phase 3A

**Originally planned as:** Phase 2B — a generic engine-level `signal_rules` table + rule evaluator that any vertical could use.

**Moved to:** Phase 3A (Fraud Vertical), built as fraud cap logic, not engine infrastructure.

**Why we moved it:** Signal rules are domain logic. Every vertical has its own operators, thresholds, and evidence patterns. Building a generic framework before two verticals exist means designing an abstraction for one use case. The fraud cap will define signal detection against fraud-specific field values. If insurance signals share enough structure with fraud signals, the common parts get extracted *then* — when we actually know what "common" means from two real implementations, not one hypothetical.

**What it needs when we get to Phase 3A:**
- `signal_rules` table with rule definitions (operator, threshold, field_name, comparison value)
- Rule evaluator that runs rules against `document_extractions` and creates `findings` rows
- SR signal definitions: SR-003 (valuation anomaly), SR-004 (UCC burst), SR-005 (zero consideration), SR-015 (deed title defect), SR-021 (revenue spike), SR-024 (charity conduit), SR-025 (false disclosure), SR-026 (construction overage)
- Move `SIGNAL_TYPES_SEED` out of `routers/findings.py` and into `app/caps/fraud/signal_types.py` — it's currently misplaced in the engine layer

---

### Partial Batch Failure Behavior — open decision from audit phase 3 (2026-05-29)

**Context:** The C2 fix handles total failure: all Claude batches fail → `extraction_status = "failed"`. But when *some* batches fail and some succeed, the document currently completes with partial fields and only a warning log — no visible signal to the investigator. They'd see a `complete` document that's missing some fields, with no indication why.

**The open question:** Should partial batch failure set `needs_review` instead of `complete`? Arguments:
- For `needs_review`: investigators can't trust a document where extraction silently dropped fields
- Against: `needs_review` was designed for low-confidence fields, not missing ones — blurring the meaning could confuse the review queue

**Decision needed before:** Phase 3 vertical work, since signals run against extracted fields and a partial extraction could cause false negatives on signal detection.

---

### Field-Level PDF Linking — deferred from Phase 2A (2026-05-28)

**What it is:** Clicking an extracted field in the fields panel highlights its location in the PDF viewer.

**Why deferred:** Requires text layer extraction from react-pdf to get character-level bounding boxes. The split-pane viewer delivers the core value (see source + extracted data side by side) without it. Deferred until extraction quality is stable — no point highlighting positions if the extraction is wrong.

**What it needs when we pick it up:** react-pdf's `onGetTextSuccess` callback returns a text layer with position data. Match extracted field values against text layer tokens to get bounding boxes, then draw highlight overlays on the PDF canvas.

---

### Frontend Test Coverage (Vitest) — deferred from Engine Core Hardening review

**Context:** Flagged in principal dev review during core hardening (2026-05-26) — "establish a Vitest baseline before Phase 3." Still not done. A few component tests exist (`test_documents.jsx`) but there's no systematic frontend test coverage.

**Why it matters:** Backend has 118 tests. Frontend has almost none. As the frontend grows with vertical-specific pages (fraud graph, insurance review queue), bugs there will be invisible without tests.

---

### Code Audit Remaining Phases — Roadmap Phase 2D

Phases 1–3 merged (PRs #4 and #5). Phases 4–6 are now tracked in the roadmap as Phase 2D. Full finding details and fix instructions in `docs/code-audit-2026-05-29.md`.

---

## Known Issues / Decisions

| Date | Issue | Resolution |
|------|-------|------------|
| 2026-05-18 | `passlib 1.7.4` incompatible with `bcrypt 4.x` | Pinned `bcrypt==3.2.2` in requirements.txt |
| 2026-05-18 | `HTTPBearer` returns 403 (not 401) when no token present | Updated tests to assert 403 — this is FastAPI's behavior, not a bug |
| 2026-05-18 | Pydantic v2 deprecation: `class Config` | Replaced with `model_config = ConfigDict(...)` |
| 2026-05-18 | `email-validator` not in requirements | Added `email-validator==2.2.0` |

---

## How to Resume a Session

1. Start Docker: `docker-compose up -d` (from project root)
2. Verify it's running: `curl http://localhost:8000/health`
3. Run tests: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v`
4. Check `docs/roadmap.md` for what's next
