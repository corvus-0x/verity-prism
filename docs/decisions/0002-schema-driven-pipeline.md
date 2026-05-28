# ADR 0002 — Schema-driven extraction pipeline

**Status:** Accepted  
**Date:** 2026-05-17

---

## Context

The platform processes 11+ document types. Each type requires different field definitions, different extraction prompts, a different parse strategy (Claude vs. direct XML), and a different confidence threshold.

Two options for managing this:

**Option A — Code-driven**  
Each document type has a handler in code. Adding a new type means writing a new handler, deploying a new version.

**Option B — Schema-driven**  
A `document_schemas` table in the database defines every document type. The pipeline reads the schema at runtime and routes accordingly. Adding a new type is an INSERT — no deployment.

---

## Decision

The `document_schemas` table drives everything. One row per document type:

```
type_key       | parse_strategy | confidence_threshold | vertical | field_definitions (JSON)
-------------- | -------------- | -------------------- | -------- | ------------------------
DEED           | claude         | 0.85                 | general  | [{name, type, description, required}, ...]
990            | xml_direct     | 1.0                  | general  | [{name, xpath, ...}, ...]
OBITUARY       | claude         | 0.80                 | fraud    | [...]
```

`parse_strategy` tells the pipeline whether to send the document to Claude for extraction or parse it directly from XML structure. `vertical` scopes a schema to specific workspace types — a schema tagged `fraud` only activates in fraud workspaces.

The extraction prompt for each field lives in the schema definition. Claude reads it directly. No code knows what fields a DEED has — only the schema does.

---

## Consequences

**What gets easier:**

- Adding a new document type requires no deployment: insert a row with field definitions, set `parse_strategy` and `confidence_threshold`, done. The pipeline picks it up at the next call.
- `detect_document_type()` loads known types from the DB at call time. No hardcoded list to keep in sync.
- `generate_standardized_name()` does the same — standardized filenames work for any schema in the registry.
- Vertical scoping is a column, not a conditional. A schema tagged `general` works everywhere; one tagged `insurance` never appears in a fraud workspace.
- Re-running the seed file safely updates live records (upsert behavior) — schema improvements don't require a database reset.

**What gets harder:**

- Schema quality determines extraction quality. A poorly written field description produces a poorly extracted field. There's no compile-time check on schema correctness — only runtime confidence scores reveal problems.
- Field definitions live in the database, not in version-controlled code files. The seed file (`backend/app/seeds/document_schemas.py`) is the source of truth and must be kept in sync with the live DB.

**What this enables downstream:**

The extraction evaluator (Phase 2A) reads `default_confidence_threshold` from the schema to decide when to retry. Signal detection (Phase 2B) queries `document_extractions` by `field_name` — field names come from the schema. Both depend on the schema being the authoritative definition of what a document type contains.
