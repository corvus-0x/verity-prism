# ADR 0001 — Row-per-field extraction storage

**Status:** Accepted  
**Date:** 2026-05-17

---

## Context

The extraction engine pulls structured fields out of documents — a deed has grantor, grantee, sale amount, recording date, and 60+ others. Those fields need to land somewhere in the database.

Two options:

**Option A — JSON blob per document**  
One row in `document_extractions` per document. All fields stored as a JSON object in a single column.

**Option B — One row per field per document**  
One row in `document_extractions` per extracted field. A deed with 64 fields = 64 rows.

The platform's core promise is that every data point is individually queryable via plain English. That requirement drove the decision.

---

## Decision

One row per extracted field per document.

```
document_id | field_name          | field_value        | field_type | confidence
----------- | ------------------- | ------------------ | ---------- | ----------
abc123      | sale_amount         | 285000             | number     | 0.94
abc123      | grantor_name        | John Smith         | string     | 0.98
abc123      | recording_date      | 2021-03-15         | date       | 0.99
```

Each field gets its own `confidence` score, its own `field_type`, and its own row that can be queried, filtered, or flagged independently.

---

## Consequences

**What gets easier:**

- NLP search and signal detection query `document_extractions` with standard SQL — `WHERE field_name = 'sale_amount' AND field_value::numeric > 250000`. No JSON path syntax, no JSON operators, no parsing at query time.
- Confidence scores are first-class columns. The extraction evaluator (Phase 2A) can find all fields below threshold with a single indexed query.
- Adding a new field to a schema adds rows, not new JSON keys. The table structure never changes — no migrations for new document types.
- Cross-document queries work naturally. "Find all deeds where sale_amount > 2x appraised_value for the same parcel" is a join on `field_name`, not a JSON comparison.

**What gets harder:**

- More rows. A workspace with 500 documents averaging 50 fields each = 25,000 rows in `document_extractions`. At the scale this platform targets, that's not a problem, but it's a different shape than a document store.
- Retrieving all fields for a document requires selecting multiple rows, not reading one JSON object. Acceptable — the document viewer does this once per page load.

**What this rules out:**

- Storing nested or list-valued fields as structured data. A field like `officers` (a list of names) is stored as a delimited string or split into multiple rows. Complex nesting would push toward JSONB. The current document types don't require it.
