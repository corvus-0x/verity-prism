# Full Document Review Pane Design

**Date:** 2026-05-30  
**Phase:** 2E (deferred) — must land before Phase 3 vertical work starts  
**Status:** Approved for implementation

---

## Purpose

The confidence threshold routes documents to the review queue. This spec is the remediation that makes that routing meaningful. Without a review pane that shows every schema field — not just ones that extracted — the operator has no path to fix what the machine couldn't read. Surfacing a problem without a fix is as bad as not detecting it.

The review pane is the fallback. The primary path is AI extraction. When Claude extracts confidently, the operator never touches this screen. When it doesn't — low confidence, batch failure, physical document damage — this pane is where the case gets completed.

Engine-level feature. Every vertical uses it automatically because every vertical uses the same schema registry and extraction pipeline. The form renders whatever `schema.schema_fields` defines.

---

## What Changes

### Existing system (before this spec)
- `ExtractionTable.jsx` in review mode maps over `extractions` (DB rows)
- Missing fields — never extracted — are invisible
- `PATCH /extractions/{id}/correct` patches an existing row; no path for fields with no prior extraction
- OCR runs at 200 DPI; full text sent to Claude (up to 200,000 chars)

### After this spec
- `SchemaReviewPane.jsx` maps over `schema.schema_fields` — all defined fields visible
- Extracted fields pre-populated; unextracted fields shown as empty editable inputs
- New endpoint for creating attempt=3 rows for fields with no prior extraction (insert, not patch)
- PDF highlighting: active field creates a highlight box on the PDF at that field's location
- Verification captures the highlighted PDF region as evidence alongside the correction
- `group` key on schema_fields entries renders the form in document-logical sections
- OCR bumped to 300 DPI
- Partial batch retry: failed batches retried once before routing to human review

---

## Schema Changes

### 1. `group` key on schema_fields entries

Add `group: str` to each field entry in `schema_fields` JSON. Fields with the same group value are rendered together in the review form under a section header.

Standard group names for DEED schema:
```
"Parties" — grantor_name, grantor_vesting, grantee_name, grantee_type
"Financial" — sale_amount, conveyance_fee_exempt, consideration_type
"Property" — parcel_id, legal_description, property_address, acreage
"Recording" — recording_date, instrument_number, book_page, deed_type
"Liens" — lien_amount, lien_holder, lien_release_date
```

Fields without a `group` key fall into an "Other" section at the bottom. Missing `group` does not crash the form.

Schema seeds and DB: update all 11 schema seeds to add `group` to every field. Run an upsert on deploy — seeds already do this pattern.

The extraction prompt ignores `group` — `_extract_batch` already only reads `name`, `type`, `description` from each field entry.

### 2. `evidence` column on `document_extractions`

New nullable JSONB column. Populated only on attempt=3 rows that go through the review pane verify flow.

```json
{
  "type": "auto_highlight" | "manual_draw" | "obscured",
  "page": 1,
  "region": { "x": 120, "y": 340, "width": 180, "height": 28 },
  "image_b64": "data:image/png;base64,...",
  "note": "Nominal consideration — actual value not stated in deed"
}
```

- `type`: how the location was determined
- `page`: 1-indexed page number where the field was located
- `region`: bounding box on the page in PDF coordinate space (pixels at 96dpi)
- `image_b64`: small cropped PNG of the highlighted region (~200×50px typical). Stored inline — individual captures are small enough for JSONB.
- `note`: operator-entered context. Optional except for `obscured` type.

Migration: add `evidence JSONB` to `document_extractions`. Nullable, default null. Existing rows unaffected.

Update `ExtractionOut` and `ExtractionCorrectionOut` Pydantic schemas to include `evidence: dict | None`.

---

## Backend Changes

### 3. New endpoint: create field extraction from scratch

```
POST /workspaces/{workspace_id}/documents/{document_id}/extractions
Body: { field_name, field_value, field_type, schema_id, evidence? }
```

Creates a new `DocumentExtraction` row with `attempt=3`, `confidence=1.0`, and optional `evidence`. Used when the operator enters a value for a field that has no prior extraction row. Returns the created row as `ExtractionCorrectionOut`.

Auth: `get_current_user`, `get_workspace_or_404`. Document must belong to workspace.

After inserting, check if any fields still need review (same logic as existing `correct_extraction` endpoint). If none remain, flip document status to `complete`.

Audit log: `action="field_created"`, before_state `null`, after_state with field_name, field_value, evidence type.

### 4. Update existing correct_extraction endpoint

`PATCH /workspaces/{id}/documents/{doc_id}/extractions/{id}/correct`

Add optional `evidence: dict | None` to `ExtractionCorrectionIn`. When provided, store on the created attempt=3 row. No breaking change — evidence is optional.

### 5. OCR DPI upgrade

`backend/app/services/ocr.py` line 20: change `dpi=200` to `dpi=300`.

One-line change. Meaningfully better quality on marginal scans (recorder's office deeds, older documents, documents with stamp overlays). No other changes to the OCR pipeline.

### 6. Partial batch retry

`backend/app/services/extraction_engine.py` — in `extract_fields()`:

Current behavior: if `0 < batch_errors < len(batches)`, log a warning and return partial results. The document eventually completes with missing fields.

New behavior: after all batches run, if `batch_errors > 0` (but not all batches failed):
1. Collect the field lists from failed batches
2. Build a single retry batch from those fields
3. Call `_extract_batch` once more with `call_type="batch_retry_partial"`
4. Merge retry results into `all_extractions`
5. If retry also fails: log and continue — the evaluator and review pane handle the rest

This resolves transient API errors (rate limits, timeouts) silently. Documents that still have missing fields after retry land in the review queue where the operator sees the empty fields and fills them in.

---

## Frontend Changes

### 7. `SchemaReviewPane.jsx` — replaces ExtractionTable in review mode

New component at `frontend/src/components/documents/SchemaReviewPane.jsx`.

**Props:**
```jsx
SchemaReviewPane({
  schema,          // DocumentSchema object with schema_fields
  extractions,     // list of DocumentExtraction rows (latest attempt per field)
  workspaceId,
  documentId,
  activePage,      // current PDF page number (from DocumentViewer)
  textLayer,       // text items from react-pdf onGetTextSuccess for activePage
  onFieldFocus,    // callback(fieldName, matchCoords) — tells DocumentViewer where to draw highlight
  onUpdate,        // callback after save — refreshes extractions list
})
```

**Rendering logic:**
1. Build a lookup: `extractedByName = { [field_name]: extraction_row }` from the `extractions` prop
2. Group `schema.schema_fields` by `field.group` (or "Other" if missing)
3. Render one section header per group, then one `ExtractionField` per field in that group
4. Pass `extractedByName[field.name]` (or null) to each `ExtractionField`

**Save behavior:**
Changes accumulate in local state. A "Save all" button at the bottom commits all dirty fields in a single async batch — one API call per changed field (parallel `Promise.all`). On success, call `onUpdate()` to refresh. On partial failure, show which fields failed and allow retry.

### 8. `ExtractionField.jsx` — single field row

New component at `frontend/src/components/documents/ExtractionField.jsx`.

Handles all four field states based on the `extraction` prop (null = not extracted):

**State 1 — Auto-extracted, high confidence (above threshold)**
- Display mode: field name label + value + AI/OCR confidence pills
- No action required; optional "Verify" button available
- Row background: default (no highlight)

**State 2 — Low confidence (below threshold)**
- Display mode: field name label + editable input pre-filled with extracted value + AI/OCR confidence pills in warning colors
- "Verify against PDF" button prominent
- Row background: `bg-yellow-950`
- Verify required before save accepts the value

**State 3 — Not extracted (null extraction row)**
- Empty editable input with italic "enter value from document..." placeholder
- "Mark location" button to enter manual draw mode on the PDF
- Row background: `bg-slate-900` with dashed border
- Verify optional but recommended; save without verify creates attempt=3 without evidence

**State 4 — Source obscured (operator selects this)**
- Toggle: operator can switch any field to "obscured" state
- Input disabled; note field required
- "Capture obscured region" button — triggers manual draw to capture the damaged area
- Row background: `bg-purple-950`
- Audit log records `type="obscured"` in evidence

**Note field:** Every state except auto-extracted has an optional note input. Shown below the value field as a small secondary input. Note stored in `evidence.note` on save.

### 9. `useFieldHighlight.js` — text layer search hook

`frontend/src/hooks/useFieldHighlight.js`

```js
useFieldHighlight(fieldValue, textLayer)
// Returns: { matches: [{page, region}], activeIndex, next(), prev() }
```

**Logic:**
1. If `fieldValue` is null or empty: return empty matches
2. Search `textLayer` items for `fieldValue` (case-insensitive, strip whitespace)
3. Fuzzy match: also try removing currency symbols, punctuation, normalizing whitespace
4. Each match returns `{ page, region: {x, y, width, height} }` in PDF coordinate space
5. If 0 matches: return empty (field goes to manual draw mode)
6. If 1 match: return it as the active match
7. If 2+ matches: default active to index 0; `next()` / `prev()` cycle through

Used by `SchemaReviewPane` — when the operator tabs to or clicks a field, `onFieldFocus` fires with the active match coordinates. `DocumentViewer` renders the highlight overlay at those coordinates.

**Match navigation UI in SchemaReviewPane:** When `matches.length > 1`, show "← 1 of N →" badge on the active field. Clicking cycles to the next match and scrolls the PDF to that page.

### 10. `PDFHighlightOverlay.jsx` — overlay on PDF canvas

New component rendered inside the PDF pane in `DocumentViewer.jsx`.

Positioned absolutely over the `<Page>` component from react-pdf. Renders:
- One blue highlight box at the active field's `region` coordinates
- A small label above the box showing the field name
- Outline only (semi-transparent fill) so the PDF text remains readable

Coordinates from `useFieldHighlight` are in PDF space. The overlay converts to screen pixels using the current PDF scale (tracked by DocumentViewer).

**Manual draw mode:** When the operator clicks "Mark location" or "Capture obscured region", the overlay switches to draw mode:
- Cursor changes to crosshair
- Operator drags to draw a rectangle
- On mouseup: the selected region is captured as base64 via canvas `getImageData`, passed back to the field as its evidence region
- Overlay returns to highlight mode

### 11. `useRegionCapture.js` — canvas capture hook

`frontend/src/hooks/useRegionCapture.js`

```js
useRegionCapture(pdfCanvasRef)
// Returns: { capture(region) → base64_png, startDraw(onComplete) }
```

`capture(region)` uses the react-pdf canvas ref to call `getImageData` at the given coordinates and returns a base64 PNG string. Small output — typical field region is ~200×50px.

`startDraw(onComplete)` enters draw mode: attaches mouse event listeners to the canvas, tracks drag coordinates, on mouseup calls `capture()` on the drawn region and passes result to `onComplete(region, image_b64)`.

### 12. `DocumentViewer.jsx` — wiring

`DocumentViewer.jsx` already has the PDF pane and fields panel. Changes:

1. When `?review=1`, render `SchemaReviewPane` instead of `ExtractionTable`
2. Fetch `schema` data alongside extractions: `GET /schemas/{schema_id}` (or from the document's schema_id)
3. Capture `textLayer` from react-pdf's `onGetTextSuccess` callback, keyed by page number
4. Maintain `highlightCoords` state — updated by `onFieldFocus` from `SchemaReviewPane`
5. Render `PDFHighlightOverlay` inside the PDF pane with `highlightCoords`
6. Pass `pdfCanvasRef` to enable region capture

The `GET /schemas/{schema_id}` endpoint: add a single-schema endpoint to `backend/app/routers/schemas.py`. Currently only `GET /schemas/` (list all) exists. Add `GET /schemas/{schema_id}` returning a single schema with full `schema_fields`.

---

## Field State Decision Logic

```
extraction row exists?
  YES → confidence >= field's ai_threshold (or schema default)?
    YES → State 1: auto-extracted (no action required)
    NO  → State 2: low confidence (requires verify before save)
  NO  → State 3: not extracted (empty, enter manually)

At any point, operator can:
  → click "Mark as obscured" to switch to State 4
```

State 4 is always operator-initiated — the system never auto-classifies a field as obscured. The operator sees the PDF, recognizes the damage, and makes that call.

---

## Evidence Chain by Field State

| State | Evidence on attempt=3 row | Referral status |
|---|---|---|
| Auto-extracted, high confidence | None (model confidence is evidence) | ✓ Ready |
| Low confidence → verified | `type: auto_highlight`, region, image, optional note | ✓ Ready |
| Not extracted → entered + verified | `type: manual_draw`, region, image, optional note | ✓ Ready |
| Not extracted → entered, no verify | No evidence, just value | ⚠ Weak |
| Source obscured | `type: obscured`, region of damage, required note | ⚠ Documented gap |

---

## OCR Upgrade (one-line change)

`backend/app/services/ocr.py` line 20:
```python
# Before
pix = page.get_pixmap(dpi=200)
# After
pix = page.get_pixmap(dpi=300)
```

300 DPI is the OCR industry standard for document scanning. Improves accuracy on:
- Recorder's office deeds (scanned, often lower quality)
- Documents with stamp overlays
- Older typewritten documents

Note: 300 DPI images are larger (~2.25x pixel count vs 200 DPI). pytesseract processing time increases modestly. For a typical 3-page deed this adds ~1-2 seconds. Acceptable given the quality gain.

Deferred — **Vision fallback:** For documents where OCR confidence remains critically low across ≥50% of fields after retry, consider a deep extraction mode that sends page images directly to Claude's vision API. Claude vision reads stamps, smudges, and complex layouts better than pytesseract. Cost: ~10x higher token cost vs text. Build this in Phase 2F after the review pane is live — the review pane reduces the urgency by giving operators a fix path, and real usage data will show how often vision would actually help.

---

## Migration

Two new columns, one new endpoint:

**Migration** `c3d4e5f6a7b8_review_pane_evidence_and_group`:
- Add `evidence JSONB` to `document_extractions` (nullable, default null)
- No data migration needed; existing rows keep null

**Seed update:** Add `group` key to all fields in all 11 schema seeds. Seeds use upsert — re-running updates existing rows.

**New endpoint:** `POST /workspaces/{id}/documents/{doc_id}/extractions` — create field from scratch.

**Schema API:** `GET /schemas/{schema_id}` — single schema lookup.

---

## Testing

**Backend:**
- `test_review.py`: add tests for new `POST .../extractions` endpoint — creates attempt=3 row, flips document status when all fields covered, audit log entry
- `test_pipeline.py`: add partial batch retry test — one batch fails, retry succeeds, document completes; one batch fails, retry also fails, document routes to review
- `test_extractions.py`: add test that `GET .../extractions` returns `evidence` field on attempt=3 rows

**Frontend:**
- `SchemaReviewPane` renders schema fields when extractions list is empty (not extracted state)
- `SchemaReviewPane` renders correct state for each field based on confidence threshold
- `useFieldHighlight` returns correct match coordinates for known text
- `useFieldHighlight` returns empty matches for null/empty value
- `useFieldHighlight` cycles through multiple matches correctly

---

## What This Spec Does Not Cover

- **Output format normalization** (remove_chars, find_replace, date_format) — separate Phase 2E follow-on
- **Extraction type enum** (text/table/reasoning) on schema_fields — separate Phase 2E follow-on
- **Vision fallback** for critical OCR failures — Phase 2F, after review pane is live
- **Field-to-location highlighting for table fields** — table cells require different coordinate math; defer until table extraction is built
- **Multi-user concurrent review** — Phase 4A; two operators editing the same document simultaneously is not handled

---

## File Map

**Create:**
- `backend/alembic/versions/c3d4e5f6a7b8_review_pane_evidence_and_group.py`
- `frontend/src/components/documents/SchemaReviewPane.jsx`
- `frontend/src/components/documents/ExtractionField.jsx`
- `frontend/src/components/documents/PDFHighlightOverlay.jsx`
- `frontend/src/hooks/useFieldHighlight.js`
- `frontend/src/hooks/useRegionCapture.js`
- `backend/tests/test_schema_review.py`

**Modify:**
- `backend/app/seeds/document_schemas.py` — add `group` to all field entries
- `backend/app/routers/review.py` — add new extraction create endpoint
- `backend/app/routers/schemas.py` — add GET /schemas/{schema_id}
- `backend/app/schemas/document.py` — add `evidence` to ExtractionOut
- `backend/app/schemas/review.py` — add `evidence` to ExtractionCorrectionIn/Out
- `backend/app/services/extraction_engine.py` — partial batch retry
- `backend/app/services/ocr.py` — DPI 200 → 300
- `frontend/src/pages/workspace/DocumentViewer.jsx` — wire SchemaReviewPane, highlight overlay, text layer capture
- `frontend/src/api/documents.js` — add createExtraction() function
