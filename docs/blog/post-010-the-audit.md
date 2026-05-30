# The Audit

*By Corvus | From Case to Code*

---

There's a point in a build where you've made enough decisions that you can't fully trust your own review of them anymore. You know what you meant to build better than you know what you built. The distinction matters when what you're building is supposed to handle evidence.

The platform was approaching Phase 3 — fraud signals, signal detection rules, the full fraud vertical cap. Before that layer went on, I needed to know if the layer under it held. Not a gut check. An actual audit. I'm a new developer, and I know what that means: there are things I've missed that I don't know I've missed. So I wrote a detailed prompt that walked through every service file, every router, every migration, every test — and ran Opus 4.8 against it at max effort.

The output came back as a 20-finding document. Two were marked Critical.

---

The first Critical finding: the immutable audit log didn't exist.

CLAUDE.md documented it as a PostgreSQL trigger — `BEFORE UPDATE OR DELETE ON audit_log` — enforced at the database level. Not at the application level. Database level, which means even a bug in the application code can't corrupt it. That's the claim. The audit log UI uses the word "tamper-proof." That's what I'd built, as far as I knew.

The trigger was not in any migration. The auditor searched the entire backend for `CREATE TRIGGER` — nothing. Searched for `audit_log_immutable`, `BEFORE DELETE`, `CREATE FUNCTION` — nothing. No `.sql` files anywhere in the repository. The docker-compose database service mounted no initialization scripts.

The trigger had been specified in the original plan. It had been written into CLAUDE.md as a confirmed design invariant. It had never been implemented.

What that meant: every audit row ever written was deleteable. An UPDATE would succeed. A DELETE would succeed. An accidental cascade from a poorly-written migration would succeed. The record that an investigator would eventually hand to the Ohio AG or the IRS — the one showing every document access, every extraction correction, every search query — could have been altered. There was nothing at the database level that would have stopped it.

The trigger had been documented as done. The documentation was wrong.

---

The second Critical finding was quieter, which made it worse.

When the Claude API is unavailable — rate-limited, network interruption, API down — the extraction pipeline didn't fail. It succeeded. The document would come back marked `complete`. Zero fields extracted. No error message. Nothing to indicate anything had gone wrong.

The path: `_extract_batch` catches all exceptions and returns an empty list. `extract_fields` merges the empty batches and returns empty. `save_extractions` writes nothing to the database. The extraction evaluator runs over the empty list, finds no low-confidence fields because there are no fields at all, and reports `needs_review = False`. The pipeline marks the document complete and writes an audit log entry.

A deed with 64 fields to extract — grantor name, grantee name, sale amount, parcel ID, legal description, conveyance fee — processed during an API outage, would look identical to a deed that had been fully extracted. The investigator would see a green badge. The AI assistant would find nothing when asked about the document. No one would know.

A visible failure is honest. You can act on it — retry the pipeline, fix the error, flag the document for review. A false complete tells you everything is fine when nothing was done. On an evidence platform, that's the worse outcome.

---

Eighteen more findings below the two Critical ones. A weak JWT default that would let anyone forge a valid token if the `SECRET_KEY` environment variable was left unset — the docker-compose file supplied a fallback of `dev-secret-key-change-in-production`, a publicly known string, so any deployed instance missing an explicit key was fully open. CSV exports had no injection protection, so a field value like `=CMD()` extracted from an uploaded document would execute as a formula when opened in Excel. The upload endpoint had no file type allowlist.

And one finding that wasn't a security issue but contradicted the platform's core premise: the extraction engine was sending only the first 4,000 characters of OCR text to Claude on every batch, regardless of the document's length. The batching splits the field list across multiple Claude calls so large schemas don't hit the output token limit. But every batch was looking at the same truncated first page. A 370-field parcel record, a 235-field 990, a multi-page deed — any value that appeared after character 4,000 had never been extracted. The platform was built on the premise that it could pull every data point from any document. That premise had never been true.

---

The fixes came in phases. Security hardening first — JWT fallback removed, CSV injection protection, upload allowlist, correct response headers. Then the test infrastructure: the test suite had been building the database schema from ORM models, not from migrations, which meant every migration-only guarantee was invisible to the tests. The audit trigger couldn't have been caught by any existing test. It was structurally untestable given how the suite was built.

Then the trigger itself — a new migration, a test that connects to the migrated database and runs `UPDATE audit_log` and confirms it raises an exception. Then the false-complete fix: `_extract_batch` now raises `ExtractionBatchError` instead of swallowing failures and returning an empty list. The pipeline catches it and marks the document failed with an error message. Then the text cap: 4,000 characters raised to 200,000. The full document now reaches Claude.

118 tests. The two Critical findings are closed. The High findings are queued.

---

Before the fraud vertical goes on, the search layer needs the same scrutiny the pipeline just got. Soft-deleted documents are still surfacing in search results and in the AI assistant's answers — a document an investigator marked deleted can still be quoted back to them. That's the next pass.

The audit didn't find that the platform was broken. It found that some of the guarantees the platform was making weren't guaranteed by anything. Those are different problems with different weights, but on a platform built to handle evidence in fraud investigations, a guarantee backed by nothing is worth less than no guarantee at all.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Posts 1 through 9 cover the origin, the data model, the extraction pipeline, the agentic chat engine, the expansion architecture, and the UI layer.*

*Follow along: `-corvus` on Hashnode.*
