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
| Four field states | Defined auto-extracted / low-confidence / not-extracted / source-obscured as distinct UI states with distinct evidence chains | The Mescher Trinity deed (recorder's stamp overlay, nominal $10 consideration) and Vet Center deed (smudge through first paragraph) showed that "source obscured" is legally distinct from "not extracted" — the AG needs to know whether a missing value is a system limitation or physical document damage |
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
