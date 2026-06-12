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

## Blog + Skills + Config (2026-05-29)

| Task | What was built or decided | Why |
|------|--------------------------|-----|
| Blog post 010 — The Audit | Wrote post covering the full audit: trigger that didn't exist, false-complete on API outage, 4000-char text cap, fixes in phases. Title: "The Audit." | Audit was a complete story — a new developer bringing in an external reviewer before building Phase 3 on top of the engine. Enough decisions and fixes to warrant a standalone post. |
| Post 010 voice revisions | Rewrote opening to be observation-first (grep came back empty) instead of thesis-first. Added personal weight ("if the record doesn't hold, none of the work matters"). Deadbolt metaphor for false-complete. "Cut short" for text cap — honest over metaphor. Trimmed over-explained close. | Reading the post against all 15 voice characteristics revealed: opening was a reflection not an observation, no personal weight, over-explained close. Physical metaphors only when natural — the deadbolt came from thinking through the actual failure mode, "cut short" was more honest than reaching for an image. |
| Post 007 voice revision | Added: "A county auditor deputy named by name. A county name across multiple fields. A nonprofit's own subdivision as the example value. Anyone reading the schema could trace back what investigation this engine was built on. That came out the same session I found it." | The "oh shit" moment — not a technical failure, a privacy alarm. Seeing a real person's name in a public repo built on an active investigation. The urgency is in the brevity: "that came out the same session I found it." |
| Post 008 voice revisions | Added "The scoring was working. There was just nowhere to go with it." Added "That kind of gap doesn't show up in the code. It shows up when you look at what you built from the investigator's side." | The discovery was quiet — not an alarm, a connection gap. Built confidence scoring, didn't wire it to a viewer. The dual-perspective line (dev side vs investigator side) is a through-line of the whole blog and earns its place here explicitly. |
| Post 009 — left unchanged | The trigger claim in post 9 ("the audit log has a PostgreSQL trigger that blocks UPDATE and DELETE") is the belief at the time Phase 2C shipped. Post 10 reveals it wasn't true. | Changing post 9 kills the tension in post 10. The reader needs to believe the trigger existed before the audit reveals it didn't. That's the arc. |
| `/log-session` skill | `~/.claude/skills/verity-prism-log-session/SKILL.md` — invoked as `/log-session` at end of session or before `/clear`. Reads git log, extracts why from conversation, writes section to build tracker. | The Why column is what feeds interviews and sales conversations but hard to keep current manually. Run before clearing context — the conversation is where the why lives. |
| `/blog-post` skill | `~/.claude/skills/verity-prism-blog-post/SKILL.md` — covers finding the discovery moment, overlap check, voice rules. Step 1 now reads the voice memory file first, then the template, then two recent posts. | Voice memory captures register (15 characteristics); template captures structure. Baseline test showed that without reading existing posts + memory file, the agent invents a voice instead of finding it and writes about things already covered. |
| CodeRabbit config | `.coderabbit.yaml` — auto-review on PRs to main only, drafts excluded. | Was triggering on every commit. Only needs to run when a PR is ready for review. Draft PRs excluded so work-in-progress doesn't get reviewed. |
| Blog timing decision | Blog stays organic — write when a discovery moment hits. Session log is for interviews and sales reference, not blog prep. | Forced blog scheduling produces mediocre posts. The discovery is the story. |

**Skills note:** `/log-session` and `/blog-post` require a Claude Code restart to appear in the skill list. Both are installed at `~/.claude/skills/`.

---

## Code Audit Remediation — Phases 4–6 (2026-05-30, PRs #6–9)

> Completed the second half of the 2026-05-29 audit. Phases 4–6 addressed search data integrity, architecture refactoring, and frontend security hardening.

| Finding | What was fixed | Why it mattered |
|---------|---------------|-----------------|
| Phase 4 — Search integrity | `run_search` and `query_extractions` now filter `Document.is_deleted`. `search_vector` column migrated from TEXT to TSVECTOR with GIN index. Soft-delete columns added to Transaction, Finding, Lead, Note, Relationship. `get_conversation_history` workspace-scoped | Soft-deleted documents were still appearing in search results. The TSVECTOR migration was purely correctness — TEXT can hold tsvector values but the GIN index requires the native type and the query planner won't use it otherwise |
| Phase 5 — Thin routers + lazy client | `get_workspace_or_404` extracted to `app/deps.py`. Export/SSE logic moved to `export_service.py`. Four module-level `Anthropic()` clients consolidated into lazy singleton `claude_client.py` | Three separate Anthropic client instances couldn't be patched from a single point in tests — every test that mocked Claude had to patch multiple locations. The singleton gives one patch target. Export logic in routers meant the router files were hundreds of lines of business logic — wrong layer |
| Phase 6 — JWT hardening + frontend resilience | Login sets httpOnly SameSite=Lax cookie. `GET /auth/me` restores session on page refresh. `get_current_user` accepts Bearer or cookie (hybrid). Frontend dropped all localStorage. `AuthInit` on startup. `ProtectedRoute` checks auth store. `AIChat.handleSend` rolls back optimistic message on failure. SSE reader cancelled on unmount. 401 interceptor uses router navigation | localStorage is accessible to any XSS on the page. httpOnly cookie is invisible to JavaScript — a stolen token can't exfiltrate the session. The hybrid auth (Bearer or cookie) meant zero test changes — all existing tests use Bearer headers and still work |

**Tests passing:** 141/141

**Migration:** `a1b2c3d4e5f6` — `is_deleted`/`deleted_at` columns on Transaction, Finding, Lead, Note, Relationship. `search_vector` column type changed from TEXT to TSVECTOR with GIN index.

---

## Docs & Planning — Phase 2E Research + Roadmap (2026-05-30)

> Before writing a line of Phase 2E code, ran a competitive research session against Hyland IDP (IDC MarketScape Leader 2025–2026), their technical documentation, and the Alfresco ng2-components library. The research shaped the entire phase design.

| Decision | What changed | Why |
|----------|-------------|-----|
| Dual confidence model | Added `ocr_confidence` as a second per-field score alongside `confidence` (AI certainty) | Hyland's glossary confirmed the distinction: OCR confidence = text recognition reliability (weakest word for text fields, average across cells for table fields); AI confidence = model certainty in the extraction. One score can't diagnose both scan quality problems and schema prompt problems. |
| Automation Rate as north star metric | Roadmap explicitly names automation rate as the primary dashboard metric | Hyland and every IDP vendor lead with this number. It answers the one question that matters: what fraction of documents require zero human intervention? Every Phase 2E improvement should move this number up. |
| Five confirmed dashboards | Roadmap updated with exact dashboard names and data sources | Hyland shipped these in Q4 2025 / Q1 2026. They're now table stakes, not differentiators. Building to the industry standard rather than guessing. |
| "Zero training" design principle | Encoded in Phase 2E roadmap section | Hyland charges $5,000/year per person for their training university — that cost signals product complexity. Target users are investigators and claims processors, not IT admins. The platform should be operable by someone who's never seen it in 20 minutes. |
| OCR confidence from Claude, not pytesseract | Architecture decision: Claude estimates OCR readability per field during extraction | pytesseract gives page-level confidence, not field-level. Claude sees the OCR text and can assess how clearly each field's value appeared in the source — gives the field-level granularity the observability dashboard needs. |
| Data connectors (Phase 2E → 2F) | Pushed to just before Phase 3 | Engine needs to be measurably reliable first — observability, quality metrics, thresholds. Piping in external data at volume before the engine is tuned wastes the data. Quality first, then scale. |
| NL schema creation deferred | Listed as deferred in Phase 2E roadmap | "Zero training" matters but schema creation is a growth feature, not a quality prerequisite. The observability dashboard and field validation are what make the engine trustworthy. NL schema creation adds after that foundation exists. |
| Output format normalization identified | Added to roadmap as deferred follow-on | Hyland confirmed this capability (remove_chars, find_replace, date_format, case, truncate, format_number). Significant capability but not a Phase 2E prerequisite — signal detection and dashboard both work on raw extracted values for now. |
| Parent/child schema inheritance identified | Added to Phase 3 candidate list | Hyland has parent class → child class inheritance for document types (e.g., DEED parent → WARRANTY_DEED, QUITCLAIM_DEED children). Relevant for fraud cap schema packaging but not before verticals are built. |

---

## Phase 2E — Engine Quality + Observability (2026-05-30, PR #10)

> 11 tasks executed via subagent-driven development. Each task dispatched as a fresh subagent with isolated context, two-stage review (spec compliance + code quality) after each. One critical pre-existing bug caught by the final Opus review.

| Task | What It Builds | Why |
|------|---------------|-----|
| Dual confidence migration | `ocr_confidence FLOAT NOT NULL DEFAULT 1.0` on `document_extractions`. `flag_reason` VARCHAR + `flag_note` TEXT on `documents` | Schema changes land first, before any code uses them. Migration is idempotent — DO $$ blocks guard all ALTER statements so re-running is safe |
| Dual confidence engine | Claude prompt updated to request `ocr_confidence` alongside `confidence`. Both normalized and stored per field. XML direct parse always gets `ocr_confidence: 1.0` | XML bypasses OCR entirely — there's no text recognition uncertainty. Confidence fallback: if Claude returns explicit null, coerce to default rather than propagate null into comparison operations that would silently fail |
| Per-field thresholds | `ai_threshold` + `ocr_threshold` optional keys in `schema_fields` JSON entries. Evaluator reads these and falls back to schema default when absent | High-stakes fields (EIN, sale_amount) need tighter confidence requirements than low-stakes fields (document_notes). One schema-wide threshold treats all fields the same and routes too many documents to human review |
| Field validation service | `field_validator.py` — pure function, no DB. `required`, `min_length`, `max_length`, `pattern` (regex fullmatch). Only required failures escalate to `needs_review`; format violations log warnings | Required field missing = the document is functionally incomplete. Format violations are advisory — the reviewer can still see the extracted value and decide. Escalating all validation errors would flood the review queue for minor formatting differences |
| Pipeline clobber fix | `doc.extraction_status = "complete"` guarded: `if doc.extraction_status == "pending"` | Pre-existing bug caught by final Opus code review. The unconditional assignment ran after both the field validator and the confidence evaluator — any `needs_review` status set by either was silently overwritten back to `complete`. The feature worked in tests (pure function) but had zero runtime effect. One-line fix, one end-to-end test added to prove it |
| Flag endpoint | `PATCH /workspaces/{id}/documents/{id}/flag` — stores `flag_reason` (Literal enum) + `flag_note`. Audit-logged. `flag_reason` is a `Literal` type, not `str` — invalid reasons rejected at the API boundary with 422 before handler runs | Structured rejection feedback turns "reviewer clicked reject" into queryable diagnostic data. The Literal constraint came from CodeRabbit review — a plain `str` field accepts arbitrary values that would make the Classification Details dashboard breakdown meaningless |
| Observability router | 4 endpoints: `/automation-rate`, `/volume` (with off-by-one fix on cutoff), `/classification-details` (5 queries instead of N×4), `/current-processing`. All scoped to caller's workspaces via `created_by` subquery | The off-by-one in volume was caught by CodeRabbit: `timedelta(days=days)` set the cutoff one day before `day_list[0]`, silently dropping the oldest day's data from every response. N×4 query consolidation: for 10 schemas, old code issued 40 DB round trips; new code issues 4 |
| Observability dashboard | `/observability` React page — 4 sections: automation rate stat cards, current processing, 30-day line chart, horizontal bar chart + detail table per schema. `Promise.allSettled` — each section degrades independently if its endpoint fails | Automation rate card is the first thing visible. Operator opens the page, sees whether the engine is working. Each section gated on its own data state so a single failing endpoint doesn't blank the whole page |
| ExtractionTable dual confidence | AI confidence + OCR confidence pills per field. `rowClass` updated to flag yellow on low OCR confidence too — originally only checked AI confidence, so a field with high AI confidence but low OCR rendered no warning | The dual pills surface the diagnosis, not just the score. A reviewer seeing `AI: 91% / OCR: 42%` knows the extraction was confident but the source text was barely legible — rescan the document, not rewrite the schema |
| ExtractionReview flagging UI | Flag button per review queue row. `FlagModal` — 5 structured reasons, optional note, Escape key dismiss, `aria-labelledby` pointing to modal title. Successful flag removes document from queue | Flag reasons are a fixed Literal enum matching the backend — the dropdown can only send values the API accepts. `note || null` converts empty string to null so the backend doesn't store empty strings as non-null flag notes |

**Tests passing:** 160/160 (+19 new: test_field_validator.py, test_observability.py, test_review.py, pipeline end-to-end needs_review regression)

**Migration:** `b2c3d4e5f6a7` — `ocr_confidence FLOAT NOT NULL DEFAULT 1.0` on `document_extractions`. `flag_reason VARCHAR` + `flag_note TEXT` (nullable) on `documents`. Requires `alembic upgrade head` on deploy.

---

## Docs & Planning — Review Pane Design + Commercial Model (2026-05-31)

> Design session using the visual companion (browser-based mockups). Researched Hyland IDP documentation and Alfresco ng2-components to ground the design in industry patterns before writing a line of code.

| Decision | What changed | Why |
|----------|-------------|-----|
| Four field states | Defined auto-extracted / low-confidence / not-extracted / source-obscured as distinct UI states with distinct evidence chains | The Keller Trinity deed (recorder's stamp overlay, nominal $10 consideration) and Vet Center deed (smudge through first paragraph) showed that "source obscured" is legally distinct from "not extracted" — the AG needs to know whether a missing value is a system limitation or physical document damage |
| PDF text layer highlighting | Active form field creates a blue highlight box on the PDF at that field's text location | Recorder's office deeds have no labeled fields — values are buried in narrative prose. The operator can't verify an extraction without seeing WHERE on the document the value came from |
| Evidence capture on corrections | Every operator correction stores a PDF region capture (base64 PNG + page + bounding box + note) alongside the corrected value | Confidence scores prove the machine's certainty. Evidence captures the human's verification. A corrected value with a region capture is as legally defensible as the original extraction |
| OCR 300 DPI | Bumped from 200 to 300 DPI | 300 DPI is the OCR industry standard. Marginal scans from the recorder's office (stamps, smudges, older typewritten text) extract noticeably better at 300 |
| Partial batch retry | Failed extraction batches retried once before routing to human review | Transient API errors caused silent partial extractions — the operator saw "complete" documents with unexplained gaps. The review pane handles genuinely broken documents; the retry handles transient failures automatically |
| Commercial model structure | Pricing tiers defined: extraction in base subscription (predictable cost ~$0.04/deed), chat as add-on (unpredictable, $1.50/session), usage metering from existing `claude_call_logs` | Chat is where costs scale. A large office with 10 investigators doing daily AI chat = $450/month in chat alone vs $40 in extraction. Separating them lets tiers be priced accurately |
| Prompt caching + model routing | Added to Phase 2F as pre-first-customer work | At public API rates, Haiku + prompt caching cuts per-document extraction cost from ~$0.04 to ~$0.01. At 500 docs/month that's $5 vs $20 in AI cost per customer — meaningful margin at subscription pricing |
| Blog post 011 — The Queue | Written about the discovery that the confidence threshold routes documents to review but the review pane only shows extracted fields — missing fields are invisible | The discovery moment: the review queue puts the operator in a room with no equipment. Surfacing a problem without a fix is as bad as not detecting it |

---

## Phase 2E Deferred — Full Document Review Pane (2026-05-31, PR #11)

> 12 tasks executed via subagent-driven development. Final code review by Opus caught two real issues (unbounded evidence JSONB, no field name validation on create_extraction). The visual companion confirmed the design against real recorder's office deeds before implementation started.

| Task | What It Builds | Why |
|------|---------------|-----|
| Migration `d5e6f7a8b9c0` | `evidence JSONB` nullable column on `document_extractions` | Every operator correction needs an evidence trail: type (auto_highlight / manual_draw / manual_entry / obscured), page number, bounding box, and operator note. Capped at 200KB after CodeRabbit flagged the unbounded write |
| Schema field groups | `group` key on all 11 schema seeds via `_group()` helper | The review form renders sections (Parties, Financial, Property, Recording etc.) not a flat alphabetical list. Same key used by the Schema Library page |
| OCR DPI + partial batch retry | `dpi=200 → 300`, retry logic in `extract_fields()` | DPI is a one-line fix with real-world impact on recorder's office deeds. Retry handles transient API failures silently; documents that fail retry route to the review pane |
| `POST .../extractions` | New endpoint creates attempt=3 row for fields the pipeline never extracted | `PATCH /correct` only patches existing rows. Missing fields need an insert path. Validates field_name against schema_fields (CodeRabbit caught the missing validation in review) |
| `GET /schemas/{id}` | Single schema fetch by ID | `DocumentViewer` needs the full schema when in review mode to map over all defined fields — the list endpoint existed but not the single-item fetch |
| `useFieldHighlight` | Text layer search hook — finds field value in pdfjs text items, returns coordinates with match navigation | The highlight can't use fixed positions because recorder's deeds vary in layout by county, era, and type. Text search against the live text layer handles the variance |
| `useRegionCapture` | Canvas capture hook — crops a region from the react-pdf canvas as base64 PNG; also supports drag-to-draw selection | Verified extractions need visual evidence attached. `capture()` automates the screenshot; `startDraw()` is the manual fallback for fields that text search couldn't locate (deferred wiring) |
| `ExtractionField` | Four-state field row component | State 1 (high confidence) = display only. State 2 (low confidence) = editable + verify. State 3 (missing) = empty input + verify. State 4 (obscured) = physical document damage, capture the damaged region. Each state has a distinct evidence type for the audit trail |
| `SchemaReviewPane` | Schema-driven form — maps over `schema.fields`, groups by `group` key, save-all | Maps over the schema definition, not the extractions table. Every defined field is visible whether extracted or not. `pendingChanges` tracks `{value, note}` so Save All preserves operator notes (CodeRabbit caught notes being discarded in first implementation) |
| `PDFHighlightOverlay` | Absolutely-positioned overlay on PDF canvas — blue box at field location, label, match navigation | The overlay uses `pointerEvents: none` so it doesn't block PDF interaction, with `pointerEvents: auto` restored on the label so navigation buttons work |
| `DocumentViewer` wiring | Text layer capture from pdfjs, schema fetch, `SchemaReviewPane` in review mode, PDF highlight | `renderTextLayer={true}` enabled; pdfjs document loaded separately to access `getTextContent()` per page; `SchemaReviewPane` replaces `FieldsPane` when `?review=1` and schema is loaded |
| Evidence size cap | 200KB limit on `evidence` payload in both write endpoints | Inline base64 images in JSONB can be large; no cap would balloon the `document_extractions` table over time |

**Tests passing:** 160 → 171 (+11 new)

**Migration:** `d5e6f7a8b9c0` — adds `evidence JSONB` (nullable) to `document_extractions`. Requires `alembic upgrade head` on deploy.

---

## Phase 2F — Commercial Readiness + Connectors (2026-05-31, PRs #13–14)

| Task | What It Builds | Why |
|------|---------------|-----|
| Prompt caching | Cacheable ephemeral block added to `_extract_batch` — schema field descriptions identical across every document of the same type get served from cache | Field descriptions never change per extraction. Caching them cuts per-extraction input token cost 60–90% at any volume. At 500 docs/month: $20 → $5 in AI costs per customer |
| Model routing | `EXTRACTION_MODEL = "claude-haiku-4-5-20251001"` + `CHAT_MODEL = "claude-sonnet-4-6"` constants in `claude_client.py`. Field extraction on Haiku, type detection + chat on Sonnet | Haiku is 4× cheaper and adequate for structured field extraction on clean documents. Chat requires multi-document reasoning — Sonnet stays. Together with caching, cuts per-document extraction from ~$0.04 to ~$0.01 |
| Usage metering foundation | `metering.py` — `get_workspace_usage()` aggregates token counts and document counts from `claude_call_logs` per workspace per billing period | `claude_call_logs` already tracked every call. This turns it into a billing data layer — not the UI or enforcement, just the query Phase 4A tier enforcement builds on |
| Connector framework | `ConnectorBase` contract: `search()` → `SearchCandidate`s, `list_items()` → `FetchableItem`s, `fetch()` → `FetchResult`. `ConnectorRun` table for pull history. `source_ref` on documents | Connector hands bytes to the pipeline — it never parses or extracts. Provenance is preserved: every document knows which connector run produced it |
| IRS TEOS connector | `IrsTeosConnector` — search by name over IRS index CSVs, EIN-keyed fetch. Wraps `scripts/fetch_990_xml.py` into the connector contract | The fetch_990_xml.py script already existed and worked. The connector wraps it so it participates in the platform's dedup (SHA-256 collision = skipped, no duplicate evidence row) |
| Sources UI | Three-phase connector flow: connector picker + name search → candidate list → filing checklist + pull button. Pull history panel. Deep-link from AI chat via `?connector=&query=` params | Investigators were running the IRS fetch script manually and uploading XML files. Sources UI makes this a one-click operation from inside the workspace |
| DigitalDocumentRenderer + registry | Schema-driven dark-theme renderer for sourced (non-PDF) documents. `rendererRegistry.js` — vertical caps can register faithful per-type templates | Sourced documents don't have a physical file stored — they're reconstructed from extracted fields. The renderer displays them in a way that looks like the source, not a raw field dump |
| `suggest_source` agent tool | 7th agent tool — returns structured suggestion (connector_id, search_query, reason). Read-only, never fetches. `SuggestSourceCard` renders it in AI chat with a deep-link button | AI chat could identify when an EIN is mentioned and suggest pulling the 990, but couldn't act on it (read-only agent design). The suggestion card bridges that: Claude recommends, operator executes |

**Tests passing:** 171 → 187 (186 pass, 1 pre-existing GIN index test)

**Migration:** `b7e72d2` — `connector_runs` table + `source_type`/`source_ref` on `documents`. `50f2b84a06aa` — `document_render_mode` on `workspaces`.

---

## Docs & Planning — Growth Plan + Job Market Alignment (2026-06-01)

> 9 job descriptions analyzed against Verity Prism to identify skill gaps. Brainstormed vertical cap architecture. Decided on additive approach for Phase B additions.

| Decision | What changed | Why |
|----------|-------------|-----|
| 9 JD analysis | Identified consistent gaps: GitHub Actions CI/CD (4+ JDs), vector search/PGVector (3), LangSmith (1 explicit + implied), formal eval datasets, AWS deployment | Building for the investigation use case and the job market simultaneously — every addition needs a working use case, not just a resume keyword. The market speaks RAG and vector search; Prism uses FTS. Adding PGVector alongside FTS (hybrid) closes the gap without losing the structured query power |
| Additive approach vs. rebuild | Kept FTS, added PGVector as a second retrieval path | Replacing FTS with pure vector search would lose the structured field-level query capability signal detection depends on. Hybrid search is the production pattern — keyword for precise queries, semantic for similarity. The interview story under additive is architecturally stronger than "I know how to install PGVector" |
| Catalyst analysis | Catalogued what Catalyst (predecessor platform) already has that Prism needs for Phase C: `signal_rules.py` (88KB), `referral_export.py`, entity pipeline, 3 Ohio connectors, GitHub Actions CI, Railway config | Catalyst's architectural failure was `views.py` at 238KB — all business logic in one Django views file. Prism's thin routers → services → models pattern exists to prevent this. The domain knowledge is good; it just needs porting into the correct layers |
| Growth plan spec | `docs/superpowers/specs/2026-06-01-growth-plan-market-aligned-build.md` — Phase A (foundation), B (market additions), C (vertical cap) | The plan is the bridge: build Prism correctly (vertical cap architecture) and in a way that closes specific skill gaps visible in the JD analysis. Nothing added for keywords alone |
| Phase C deferred | Vertical cap architecture (cap installer, signal engine, fraud cap v1) deferred to next branch | Can't design the cap installer until the engine is validated end-to-end. Phase A+B is the prerequisite — measure reliability first, then build on it |

---

## Phase A + B — Foundation + Market Additions (2026-06-01, PR #15)

> First real end-to-end engine validation run (23 documents). Two evaluator correctness bugs surfaced during the run and fixed before adding market-relevant capabilities. All additions are additive — nothing replaced.

| Task | What It Builds | Why |
|------|---------------|-----|
| CI verification | Secrets documentation added to `.github/workflows/ci.yml` | CI existed but had never been verified against real secrets. Green badge on the repo is visible to every hiring manager before a phone screen |
| Engine validation script | `scripts/validate_engine.py` — authenticates with live API + DB, generates structured Markdown baseline report: automation rate, confidence distribution, low-confidence fields, Claude API usage, NLP search results | The engine had never been driven with a real case. Tests verify individual parts; the validation run shows how the whole system behaves under real documents. This was the prerequisite for knowing what to fix |
| Evaluator: absent fields fix | `extraction_evaluator.py` — skip fields where `field_value` is null before checking confidence | Claude returns ~0.1 confidence for fields not found in a document. Those were being evaluated identically to bad extractions — absence of a field is not the same as extracting it poorly. Effect: automation rate 48% → 57% on the validation set |
| Output format normalization | `_normalize_field_value()` in `extraction_engine.py` — currency → plain decimal (1250000.00), dates → ISO 8601, booleans → true/false, before DB storage | Signal detection compares field values numerically. SR-003 checks `sale_amount > 2 * appraised_value_current`. `"$1,250,000.00"` vs `"625000"` silently fails. Normalization is the prerequisite for any signal rule to work correctly |
| LangSmith tracing | `claude_client.get_client()` wraps with `langsmith.wrappers.wrap_anthropic()` when `LANGSMITH_API_KEY` is set | LangSmith named explicitly in Nephew JD. Wraps the singleton — every Claude call (extraction, chat, search, naming) automatically traced with zero changes to callers. Coexists with `claude_call_logs`: LangSmith is for debugging, call logs are for metering |
| PGVector migration | `documents.embedding vector(1536)` column + ivfflat cosine distance index. DB image switched from `postgres:16` to `pgvector/pgvector:pg16` | Standard postgres:16 doesn't ship `vector.control` — the extension can't be installed. pgvector/pgvector:pg16 is the official drop-in rebuild with the same data directory layout |
| Embedding service | `embedding_service.py` — generates `text-embedding-3-small` vectors from concatenated extracted fields after each document completes. No-op when `OPENAI_API_KEY` absent | One embedding per document, not per field — the use case is "find documents similar to this one," not field-level similarity. Embedding failure wrapped in try/except: never blocks a document's completion |
| Hybrid search | `semantic_search()` in `search_service.py`. `run_search()` gains `mode` parameter (keyword/semantic/hybrid, default hybrid). `SearchRequest.mode` constrained to `Literal` | FTS is better for structured queries (sale_amount > X); vector search is better for similarity (find documents about property transfers near X). Running both routes to the right mechanism per question. Closes the vector search gap visible across 3 JDs |
| 401 interceptor fix | Removed `window.location.href = '/login'` fallback in `client.js` | `_navigate` is null on first render (before NavigatorSetter's useEffect fires). The fallback caused a hard page reload, which remounted the app, which called `me()` again, which got 401, which reloaded again — infinite loop that made the app unloadable |
| Multi-file upload + sidebar button | `DropZone` accepts multiple files. `WorkspaceSidebar` gets an `+ Upload` label button visible from any workspace page | Uploading 17 documents one at a time to validate the engine took too long. Multi-file + sidebar access is QoL for the validation run and for production use. Label wrapper instead of `ref.current?.click()` — programmatic click on `display:none` inputs is blocked by some browsers |
| UI improvements | Overview cards clickable, page controls moved to floating overlay in PDF viewer, SSE stream sends standardized filename so document cards update without a page refresh | All discovered during the validation run. The overview cards were dead space. The page turner in the top-right corner was disorienting on multi-page deeds. The SSE payload sent `detected_doc_type` but not `filename` — the standardized name was generated by the pipeline but never surfaced live |
| SCREENSHOT misclassification | Documented in `docs/build-inventory.md` as Phase 3 loose end | Land record screenshots classified as social-media SCREENSHOT schema — `likes_count`, `comment_1_author` etc. all absent, confidence ~0.1. Evaluator fix mitigates worst effects (absent fields now skipped). Root cause (type detection improvement or schema variant) deferred to Phase 3 schema packaging when fraud cap schemas are designed |

**Tests passing:** 154 → 218 (+64: test_normalization.py × 19, test_embedding_service.py × 4, test_search.py +3, test_claude_client.py +2, test_pipeline.py updated × 3)

**Migration:** `cf7d3b604763` — pgvector extension + `documents.embedding vector(1536)` + ivfflat cosine ops index. Requires `alembic upgrade head` on deploy.

---

## Frontend Polish + Tooling (2026-06-02)

> No backend changes. Full session on core UI design, resizable panes, Storybook, and Claude Code automations. Phase 2 is complete; this session establishes the frontend foundation and dev tooling before Phase 3 vertical cap work starts.

| Task | What It Builds | Why |
|------|---------------|-----|
| Precision instrument design system | Tailwind palette remap (`slate-*` → precision navy `#040810`–`#E4F0FC`), signal red accent (`#DC2626`), Syne+Outfit+JetBrains Mono fonts, CSS component classes (`btn-primary`, `btn-ghost`, `field-input`, `surface-card`, `nav-link`, `nav-link-active`, `mono-val`), entrance animations, scrollbar, precision grid overlay | The "feels right" sensation has a name: perceived affordance. Every element should telegraph its purpose before you click it. User referenced Palantir Gotham — dark, precise, amber accent (later changed to red). Remapping the entire Tailwind `slate` scale updated all 20+ JSX files automatically without touching each one |
| Amber → signal red | Accent color changed from `#E8A000` (amber) to `#DC2626` (red) across all design system files | Red reads as urgency and authority — right for investigative tooling. Amber looked product-generic. User made the call on sight |
| Core vs vertical UI boundary | Explicitly established: the navy+red design is the ENGINE UI only (login, workspaces list, schema library, observability). Vertical caps design their own workspace experience from scratch | Caps are not skins on top of the core — they replace the workspace experience. A fraud UI doesn't look like an insurance UI. This was a key framing correction: stopped treating the core design as "the foundation every cap builds on" |
| Resizable panes | `useResizable` hook (drag-to-resize, direction-aware, cursor locks during drag), `ResizeHandle` component (6px grab zone, red hover indicator). Wired into: WorkspaceSidebar, Documents list pane, DocumentViewer doc list, DocumentViewer PDF/fields split | Working on 34" ultrawide at 2/3 screen — fixed-width panes are unusable. All four resize boundaries now draggable. Cursor locks to `col-resize` across the full window during drag so it doesn't flicker over adjacent pane content |
| ExtractionTable CSS Grid | Replaced `<table>` with CSS Grid (`minmax(0,Nfr)` columns) + `break-words`/`break-all` on text cells | HTML tables have their own layout engine that runs before the browser applies flex constraints from the parent — they resist shrinking. Grid takes its size from the parent first, then distributes to children, so columns genuinely shrink and text wraps instead of overflowing. This fixed text disappearing when the fields pane was resized narrow |
| DocumentList badge fix | Badge row changed to `flex` with `shrink-0` on badge + `truncate min-w-0` on doc type text. Wider default pane (300px) | Badges were rendering outside their card boundary because the flex row had no overflow handling. Type string + badge wider than the card = badge floats right past the border |
| Storybook v10.4.2 | Installed `@storybook/react-vite`, `@storybook/addon-vitest`, `@storybook/addon-a11y`, `@chromatic-com/storybook`, MSW v2 + `msw-storybook-addon`. Dark theme preview with `MemoryRouter` + `ToastProvider` decorators. `vitest.workspace.js` for test runner. 6 story files, 23 passing tests | The "write the story first" discipline forces thinking through all component states before implementing — wide/narrow/empty — which is exactly what catches overflow bugs before they hit the app. Also a legitimate resume line: Storybook, vitest browser testing, MSW API mocking, Chromatic (future). Windows path issue with `pathe` normalizeWindowsPath required extracting workspace config to `vitest.workspace.js` instead of inline in `vite.config.js` |
| Story files (6) | `Badge` (all statuses + fallback), `Buttons` (CssCheck proving design system loaded), `EmptyState`, `LoadingSpinner`, `DocumentList` (empty/single/all statuses/long filename/200px narrow/20 items/API badge), `ExtractionTable` (populated/empty/low confidence/corrected/280px narrow) | Each ⚠ story is a checklist item that would have caught a layout bug before production. The CssCheck play function asserts `rgb(153, 27, 27)` on the btn-primary background — if the design system CSS fails to load, this test turns red immediately |
| Frontend process principle | Established: story-first workflow for every new component. Three mandatory questions before building: (1) what does this look like with long content? (2) what at 200px width? (3) what when empty? Frontend done = verified at three widths, not just tests passing | Backend done = tests pass. Frontend done = you've looked at it at three widths and nothing is broken. Stories are the proof. Without this discipline, big implementation plans lose small visual details — learned directly from badge overflow and table truncation bugs found mid-session |
| Claude Code automations | `new-story` skill (scaffolds story file with correct tags/naming), `gen-migration` skill (Alembic migration in Docker with correctness checklist), `storybook-reviewer` subagent (checks story files against component checklist), Ruff PostToolUse hook (auto-fix Python files on edit), `.env` PreToolUse block hook | Reduces friction on the patterns that happen every session. The storybook-reviewer enforces the checklist without relying on memory. The Ruff hook eliminates the "forgot to run ruff" PR cleanup (50+ files in Phase 2C) |

**Tests passing:** 23 Storybook (Playwright/vitest) — backend tests unchanged at 218

---

## Recruiter-Readiness — CI Repair + Repo Packaging (2026-06-06, PR #17)

> Session opened with one question: "is the repo ready for recruiters?" Answer was no — CI had been red on main for 5 straight runs, and the README claimed "222 tests. All passing" directly above a failing Actions tab. Everything in this session traces back to making the repo survive a technical screener's 30-second skim and a deeper engineer's verification pass.

| Task | What It Builds | Why |
|------|---------------|-----|
| Backend CI: pgvector service image | `ci.yml` Postgres service swapped `postgres:16` → `pgvector/pgvector:pg16` | Hybrid search added `CREATE EXTENSION vector` to conftest, but CI's service image was never updated — stock postgres doesn't ship pgvector, so every run died at DB setup before a single test executed. docker-compose already had the right image; CI just drifted from it |
| Frontend CI: remove storybook-vitest wiring | Deleted `@storybook/addon-vitest` from package.json + `.storybook/main.js`, deleted `vitest.workspace.js`, regenerated lockfile from scratch | The addon requires `@vitest/browser` 3/4; project is on vitest 2 — the integration was scaffolded but never installable. Local dev worked only because `node_modules` predated strict resolution; `npm ci` (what CI runs) correctly rejected the tree. Rejected alternatives: upgrading vitest to 3 (churns the whole test stack for an integration nothing used — unit tests run through the jsdom config in `vite.config.js`) and `--legacy-peer-deps` (papers over the conflict instead of resolving it). Subtle mechanism worth remembering: even after removing the addon from package.json, npm kept resolving it because the package was still on disk and `addon-mcp` lists it as an optional peer — had to remove it from `node_modules` before the tree resolved clean |
| Repair 5 stale frontend tests | Login tests query `getByLabelText` instead of placeholders; labels gained `htmlFor`/`id` association; documents tests assert on parsed display parts ("DEED" badge + entity line) and the real dropzone text | The design-system redesign changed placeholders and replaced raw-filename rendering with parsed parts — tests asserting on presentation details broke silently. Nobody saw it: CI died at install, local `npm test` died at the workspace file's missing import. The label association was a genuine a11y defect (screen readers couldn't name the fields), so the right test fix and a real accessibility fix were the same change — and the new `#email`/`#password` ids made the form scriptable for the Playwright demo later in the session |
| eslint ecmaVersion 2020 → latest | One-line config change | `DigitalDocumentRenderer` uses `\|\|=` (ES2021); parser at 2020 threw a parse error that failed lint. Never caught for the same reason as the tests: lint never got to run in CI |
| Fix CI-only test failure (404) | `test_get_document_file` now patches `process_upload_background` like every sibling upload test | First green-path run exposed it: the pipeline's failure handler deletes the stored file (evidence cleanup), and in CI the pipeline always fails (no tesseract binary, empty API key) — so the file vanished between upload and GET. Locally it passed because Docker has tesseract and a real key. The test covers file serving, not extraction; it was unpatched by oversight, not design |
| README hero: Red Cross 990 | Replaced hero screenshot with the American Red Cross FY2024 Form 990 (from redcross.org, trimmed to 12 pages) run end-to-end through the real pipeline — detected as 990, renamed to standardized format, 235-field schema extracted with AI + OCR confidence per field | Original hero showed Cedar Grove 990 data — public records, but the README would chain *real name → Corvus → named parties in an active investigation* for exactly the audience that knows the real name. Tyler called it: neutral, well-known org with zero connection. Side benefit: the hero is now provably real pipeline output, and the demo workspace persists in the dev DB for live interview demos |
| Remove case-data screenshots | Deleted `docs/documents-fixed.png` (case doc names) and `docs/login-red.png` (real first name typed in the email field) | Both unreferenced by any doc. Removed from tip only — they remain in git history on public main; history rewrite (`git filter-repo`) considered and deferred since the 990s are public records. The login screenshot's name leak is the one to revisit if a scrub is ever wanted |
| Repo packaging | MIT LICENSE (copyright "Corvus" — real name in LICENSE would publicly tie it to the alias), 8 GitHub topics, homepage → Hashnode blog, README test count corrected to verified numbers, `.claude/scheduled_tasks.lock` untracked | README claimed 222 tests; pytest collects and runs 219 backend + vitest runs 18 frontend = 237. The count is now a claim a screener can verify — CodeRabbit's review flagged it using static grep (221 + 0) and was wrong both ways: grep counts defs pytest doesn't collect, and its frontend command errored on `.jsx`. Execution counts are authoritative; documented in the PR thread |

**Tests passing:** 237/237 (219 backend, 18 frontend) — main is green for the first time since PR #16 merged

**Deferred from this session:** `@vitest/browser`, `@vitest/ui`, `playwright` are orphaned devDependencies (only the deleted workspace file used them) — small cleanup PR whenever. CI badge in README now that it would show green. `ci.yml` comment claiming `ANTHROPIC_API_KEY` secret is required is wrong (no secret is set; tests mock Claude) — fix the comment next time the workflow is touched.

---

## Repo Rebuild + Public Relaunch (2026-06-06, evening session)

> Session opened with one question: "is the repo clean of personal information?" The previous session had deferred the history question. This session answered it: a fresh-clone audit of what GitHub actually serves, a full demo-cast sweep at the tip, and a rebuilt repo whose entire history is verifiable by grepping one tree.

| Task | What It Builds | Why |
|------|---------------|-----|
| Demo-cast sweep at the tip | 27 files brought fully onto the fictional demo cast: plan docs, specs, test fixtures, Storybook stories, MSW handlers, schema seeds, the 990 fetch script | The earlier pass covered docs and docstrings; fixtures and plan docs still carried older example values. One test broke in the process (`test_get_entity_case_insensitive`): a lowercase search probe was only half-replaced by the pattern list and no longer matched the entity it was probing for. The fix aligned the probe with the entity name and kept the case-insensitivity semantics. Lesson: blanket string replacement needs a test run behind it, not a grep |
| Sweep committed straight to main, no PR | Two direct commits, then verification | Review tools quote diffs verbatim into PR threads, and PR metadata is not in git: it survives every rewrite. A sweep's before/after does not belong in any permanent public thread. The docs-only main exception was extended deliberately, once, for this |
| History rebuilt: fresh repo seeded from the verified tree | Old repo renamed to a private archive (PR threads and review history preserved, visible to no one else). New repo created under the same name, seeded with a single `git commit-tree` root that reuses the exact verified tree object. PR and issue metadata archived to `private/` before the rename | The deferred question from the last session came due, and the answer was structural: force-pushing a rewritten history does not clean a public GitHub repo. `refs/pull/*` keeps pre-rewrite commits fetchable forever, and review threads live in GitHub's database where git cannot reach. A filtered 550-commit history can never be proven clean; a single seeded commit is verifiable by grepping one tree. Verified by fresh mirror clone + `refs/pull/*` fetch + full-pattern grep: zero hits. Rename-to-archive beat deletion because it loses nothing and exposes nothing |
| Images eyeballed, not grepped | Every PNG and GIF at both repo tips visually reviewed frame by frame | Text scans cannot see pixels. The sibling repo's demo GIF passed every grep while its opening frame showed a stale case list; it was caught only by extracting and reading the frames. Re-recorded against the seeded demo workspace, every frame verified before commit |
| "How This Is Built" README section | New section citing the in-repo harness: `.claude/skills/` codegen, the storybook-reviewer agent, CLAUDE.md conventions, CodeRabbit + CI as merge gates. Test count corrected 237 → 240 | Leaning into AI-assisted development as the differentiator instead of hedging it. The harness is versioned in the tree, so the claim is checkable rather than asserted. The count is an execution count (222 backend + 18 frontend), same standard as PR #17: claims a screener can verify |
| v1.0.0 + roadmap issues + profile README | Release tagged on both repos, 5 issues seeded from docs/roadmap.md under a `roadmap` label, profile README created at corvus-0x/corvus-0x | A one-commit repo with an empty Issues tab reads as a dump. Releases and a labeled roadmap (nothing invented, all drawn from the roadmap doc) read as a live project. The profile README is the first thing a recruiter sees, above the pins |
| Public relaunch | Both repos + profile flipped public the same night, after CI green on every commit and explicit review of each artifact | The window between "verified clean" and "public" was kept short on purpose: nothing accumulates in a private repo except drift |

**Tests passing:** 240/240 (222 backend, 18 frontend)

**Standing rule from this session:** anything that captures a screen gets recorded against the seeded demo workspace only. Text is protected by construction now; pixels are the only door left.

---

## Portfolio Hardening — Merge Completion (2026-06-11, PR #6)

> The session opened mid-air: a previous session had built the portfolio-hardening work (search correctness, RBAC enforcement, extraction fixes, chat prefix caching) but the machine crashed before the PR landed. PR #6 was open, mergeable, and red — two CI blockers stood between the branch and main. This session was about clearing them honestly, not forcing the merge past a failing gate.

| Task | What It Builds | Why |
|------|---------------|-----|
| Ruff whitespace fixes | 9 `W291`/`W293` lints cleared in `deps.py` and `documents.py` via `ruff --fix` | Pure whitespace, the safest auto-fix category — it cannot change behavior. The crash had interrupted the lint cleanup mid-commit. Verified the diff was whitespace-only before pushing rather than trusting the fixer blindly |
| Langsmith client test fix | `test_get_client_wraps_with_langsmith_when_key_set` patched to set `settings.langsmith_api_key` directly instead of `monkeypatch.setenv` | The real bug, and the one worth remembering. The test set the env var *after* import, but `get_client()` reads `settings.langsmith_api_key` — a Pydantic `BaseSettings` object that snapshots env vars once at construction. The patch never reached the code path, the wrap branch never ran, `wrap_anthropic` was called 0 times. The code was correct; the test was lying. Fixed by patching the attribute the code actually reads. Both langsmith tests aligned to the same pattern for consistency. **Standing lesson: never test settings-driven code by patching env vars — patch the settings attribute** |
| Merge + local-main reconciliation | PR #6 squash-merged to main (`b683a9e`), branch deleted; diverged local main rebased onto the merged tip | `gh pr merge` reported a fast-forward error, but that was cosmetic — it only failed to update *local* main; the remote merge succeeded (`state: MERGED`). Local main carried two unpushed docs commits from the crashed session; rebasing onto the merged tip dropped both as already-upstream, after resolving one README post-count conflict (kept "13", the value the merged PR already corrected to). Net: nothing lost, local even with origin. **Lesson: a `gh pr merge` local fast-forward failure does not mean the PR failed — check `state`/`mergedAt` before re-running** |

**Tests passing:** 227 backend (CI-verified on the merge commit)

---

## Inline Code Walkthroughs (2026-06-11, PR #7)

> This one started as a learning conversation, not a build task. The question was "how do I study my own code more easily?" — Jupyter notebooks had never clicked. The answer that did: annotate the code in place. The session became a documentation pass over the whole service layer, plus a README section that surfaces the engineering the annotations reveal.

| Task | What It Builds | Why |
|------|---------------|-----|
| Format decision: inline `# WALKTHROUGH:` comments | Chose inline source comments over companion docs or richer docstrings, knowing it overrides the repo's terse-docstring convention and may draw CodeRabbit | Tyler learns by pulling a file up and talking through it; in-file narration means code and explanation are never out of sync on screen. He saw all three options (companion doc / inline / docstring) before choosing. The override is deliberate — his instruction wins over the convention for a study aid. Notebooks were ruled out: they suit "feed input, watch output" code (extraction prompts, transforms), not control-flow code (RBAC, routing) where reading + tests teach better |
| Walkthroughs across 12 service files | `# WALKTHROUGH:` teaching blocks on the conceptual spine: `document_pipeline`, `extraction_engine`, `ai_engine`, `agent_tools`, `deps`, `search_service`, `audit` + helpers `ocr`, `naming`, `xml_parser`, `field_validator`, `embedding_service` | Blocks explain *why*, not *what*, at each real decision point and cross-reference each other into one map. The `workspace_id` security boundary is now documented on both sides — the caller (`ai_engine`) and the enforcer (`agent_tools`). Density tracks conceptual weight: the spine got 4–8 blocks, the mechanical helpers 1–2. Comments-only, so behavior is provably unchanged — verified per file with `py_compile` + `ruff`, no test run needed |
| Verified a teaching claim at runtime | The `agent_tools.execute()` block claims a smuggled `workspace_id` raises Python's duplicate-keyword `TypeError`; proved it with a 6-line script before committing | A teaching comment that asserts behavior has to be true, not plausible. The runtime check returned the exact error string quoted in the comment. **Discipline: when a comment makes a factual claim about behavior, verify it — don't reason it** |
| max_tokens / TEXT_LIMIT correction | Captured the output-ceiling-vs-coverage distinction as WALKTHROUGH blocks in `ai_engine` (fixed 4096) and `extraction_engine` (scaled 8192) | Surfaced from a misconception Tyler raised — he thought a prior session had Fable bump max_tokens to 8000 "to cover extraction better." No such change existed (grep noise was the API port). The reasoning was misattributed: `max_tokens` is an output ceiling (anti-truncation), not a coverage lever. Coverage is `TEXT_LIMIT` on the input side (raised 4000→200k earlier, the real "cover it better" change). **Symptom map now in-code: misses → input window; cut-off JSON → max_tokens** |
| "Reading the Code" README section | New section advertising `grep -rn WALKTHROUGH backend/app` plus four showcased decisions (workspace_id injection, DB-trigger immutability, fatal-vs-non-fatal failure, hash-first) | Written in the README's understated voice despite Tyler's "amazing engineering" reaction — and he confirmed that was the right call. A recruiter trusts a verifiable mechanism (the `TypeError`) more than an adjective. Placed on the PR branch, not committed to main directly, so the section and the comments it describes merge together and main stays coherent at every commit |
| Throwaway lab-bench notebook (not committed) | `backend/notebooks/prototype_extraction_prompt.ipynb` — runnable demo of the bench workflow against the real `claude_client` / `strip_json_fences`, left untracked | Built to teach the notebook's actual fit: a workbench for prompt tuning, deleted after. Left untracked on purpose — the repo keeps zero committed notebooks, and the notebook's own closing section says so. Verified by JSON-validation + compiling every code cell; deliberately NOT executed (a live billed Claude call is Tyler's call to make) |

**Tests passing:** unchanged — comments/docs-only, so no behavior to test. Each file verified with `py_compile` + `ruff`; CI green on the merge commit (`ced8b49`).

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

### Full Document Review Pane — the core verification experience

**Decision made (2026-05-30):** The confidence threshold is a routing decision — below threshold means a human needs to verify it. The full review pane is the remediation that makes that routing meaningful. Without it, surfacing a low-confidence or missing extraction is as bad as not detecting it: you've told the client there's a problem but given them nothing to fix it with. The current review UI is a patch — it surfaces what failed. The real experience is a schema-driven verification pane: every field the schema defines is visible alongside the PDF, pre-populated where extracted and empty where not. The reviewer reads the source and confirms, corrects, or fills in any field directly. Engine-level: every vertical gets this automatically because every vertical uses the same schema registry and extraction pipeline. The form renders whatever `schema.schema_fields` defines — fraud reviewers see deed fields, insurance reviewers see claim fields, same component.

**Why this resolves partial batch failure:** The pipeline should auto-retry failed batches first (handles transient API errors). If retry also fails, route the document to the full review pane. The reviewer sees empty fields with the PDF open — fills them in from the source document. The same review pane handles all three failure modes uniformly:
- Field never extracted (batch failure) → empty row, reviewer fills in
- Field extracted with low confidence → pre-filled row, reviewer corrects
- Field extracted confidently but wrong → pre-filled row, reviewer corrects

A single unified path. No special cases per failure type.

**What the right pane looks like:**
- Every field in `schema.schema_fields` rendered as a form row (not just fields with extraction rows — the current approach)
- Pre-filled with the latest-attempt extracted value where it exists
- Confidence indicators (AI + OCR pills) on extracted fields; "Not extracted" label on empty ones
- All fields editable inline — saving writes `attempt=3` rows
- Field ordering follows schema definition order (same order as the extraction prompt)

**What it replaces:** `ExtractionTable.jsx` in review mode currently maps over `extractions` (fields that exist in the DB). It needs to map over `schema.schema_fields` instead, joining to extractions for pre-fill values. Empty fields get editable rows with no pre-fill.

**Backend already ready:** `GET /schemas/` returns full field definitions. `PATCH /extractions/{id}/correct` writes `attempt=3`. A new endpoint may be needed for creating attempt=3 rows for fields with no prior extraction (insert rather than patch).

**Phase placement:** Phase 2E (deferred from current pass). Must land before Phase 3 vertical work — signals run against extracted fields and a silent partial extraction produces false negatives on signal detection. This is the remediation path that makes the review queue actionable rather than just diagnostic.

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

### ~~Code Audit Remaining Phases~~ — COMPLETE (2026-05-30)

All 6 phases merged. Phases 1–3 in PRs #4 and #5. Phases 4–6 in PRs #6–9. Full finding details in `docs/code-audit-2026-05-29.md`. Nothing remaining from the 2026-05-29 audit.

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
