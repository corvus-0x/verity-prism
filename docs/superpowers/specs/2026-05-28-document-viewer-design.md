# Document Viewer — Design Spec

**Date:** 2026-05-28  
**Phase:** 2A  
**Status:** Approved — ready for implementation plan

---

## What This Is

A split-pane document viewer that renders the source PDF alongside its extracted fields. This is the human interface for trusting extraction output — seeing the document and its structured data side by side is the moment the platform clicks for a new user and the primary demo surface.

Field-level linking (clicking a field to highlight its location in the PDF) is explicitly out of scope for this pass. The viewer ships first; linking follows as a separate build.

---

## Navigation Pattern

Clicking a document in the Documents list navigates to `/workspaces/:workspaceId/documents/:documentId`. The document list stays visible on the left column with the selected document highlighted in blue. The right side switches to the full viewer.

- Each document has a shareable, bookmarkable URL
- Browser back returns to the list with nothing selected
- The upload DropZone remains on the Documents list page — the viewer is read-only

---

## Layout

```
WorkspaceLayout (sidebar + AppShell)
└── left column: DocumentList (200px, scrollable)
│     └── document cards — <Link> to /documents/:id, selected card highlighted
└── right area: ViewerHeader + split pane
      ├── ViewerHeader: filename, doc type, field count, page nav (Prev / Page X of Y / Next)
      ├── PdfPane (65% width): react-pdf <Document> + <Page>
      └── FieldsPane (35% width): ExtractionTable, scrollable, with status states
```

Split is 65% PDF / 35% fields. The fields panel is narrow but readable — field names are consistent length, values are short, confidence is a percentage badge. No wasted space on either side.

---

## Components

### New: `pages/workspace/DocumentViewer.jsx`
The full viewer page. Mounted at `/workspaces/:workspaceId/documents/:documentId`.

On mount, fires three requests in parallel:
- `getDocument(workspaceId, documentId)` — metadata (filename, doc type, extraction status, extraction_error)
- `getExtractions(workspaceId, documentId)` — extracted fields array
- `getDocumentFile(workspaceId, documentId)` — file blob

Manages state: `{ doc, extractions, fileUrl, currentPage, totalPages, loading, error }`.

Creates a blob URL from the file response via `URL.createObjectURL()`. Revokes it on unmount to avoid memory leaks.

### Extracted: `components/documents/DocumentList.jsx`
Pulled out of `Documents.jsx` so both the list page and the viewer share identical list behavior. Accepts `documents`, `selectedId`, `workspaceId` as props. Renders document cards as `<Link>` elements to `/workspaces/:workspaceId/documents/:id`. Selected card gets a blue border highlight.

### Modified: `pages/workspace/Documents.jsx`
Uses `DocumentList` instead of its inline list. Clicking a document now navigates to the viewer route rather than loading an inline extraction table. The inline extraction panel is removed — that responsibility moves to the viewer.

### Unmodified: `components/documents/ExtractionTable.jsx`
Reused as-is in the FieldsPane. No changes needed.

---

## Backend — New Endpoint

```
GET /workspaces/{workspace_id}/documents/{document_id}/file
```

Added to `backend/app/routers/documents.py`.

- Authenticates via `get_current_user` (same as all document endpoints)
- Calls `get_workspace_or_404` to verify workspace membership
- Looks up the Document record; raises 404 if not found or soft-deleted
- Reads the file from `UPLOAD_DIR / doc.filename`
- Returns `FileResponse` with `media_type` inferred from the filename extension (pdf → `application/pdf`, jpg/png → `image/jpeg` / `image/png`)
- Returns 404 with detail `"File not found on disk"` if the file is missing from storage
- Logs the file access to `audit_log` via `audit.log()`
- Logs file-not-found errors to `audit_log` so they are not silent

No new service needed. The router handles this directly.

---

## Frontend — API Client

New function added to `frontend/src/api/documents.js`:

```js
export const getDocumentFile = (workspaceId, documentId) =>
  client.get(`/workspaces/${workspaceId}/documents/${documentId}/file`, {
    responseType: 'blob',
  })
```

---

## Routing

New nested route added to `App.jsx` under the workspace layout:

```jsx
<Route path="documents/:documentId" element={<DocumentViewer />} />
```

Sits alongside the existing `documents` route. The list page and viewer coexist — the list is the index, the viewer is the detail.

---

## Error States

The viewer surfaces informative states rather than generic red banners.

| Condition | PDF Pane | Fields Pane |
|---|---|---|
| Loading | Spinner | Spinner |
| Document not found (404) | "Document not found" + link back to list | — |
| File missing from disk | "Source file unavailable — the stored file could not be found. Re-upload the document to restore the source view." + link to list | Extractions still render if available |
| Extraction pending | PDF renders normally | "Extraction in progress…" |
| Extraction failed | PDF renders normally | "Extraction failed: `<extraction_error text>`" |
| No schema | PDF renders normally | "No schema found for this document type. An investigation lead was created." |
| Network error fetching file | "Could not load file — check your connection." + Retry button | Extractions still render if available |

The `extraction_error` column on the Document model already stores the pipeline's failure reason. Surfacing it directly gives the developer or analyst actionable information without digging into logs.

Extraction failures are already written to the immutable `audit_log` by the pipeline's `_fail()` function. File-serve errors are logged by the new endpoint. The full audit trail becomes readable in the UI when the Audit Log page ships in Phase 2C.

---

## PDF Library

**`react-pdf`** (`react-pdf` npm package, which bundles `pdfjs-dist` internally).

- Renders PDF entirely in-browser via pdf.js — no external viewer, no plugin required
- Works identically across Chrome, Firefox, Edge, Safari
- PDF bytes are fetched as a blob by the frontend and passed to react-pdf via a blob URL — no CORS issues, auth headers handled by the existing axios client
- Uses pdf.js text layer internally — the foundation is in place for field-level highlighting in a future pass without a library swap

Worker setup: `react-pdf` requires a pdf.js worker file. Set `pdfjs.GlobalWorkerOptions.workerSrc` once at app initialization pointing to the bundled worker.

---

## Page Navigation

`currentPage` is React state, initialized to 1. `totalPages` is set from `react-pdf`'s `onDocumentLoadSuccess` callback. Prev/Next buttons in the ViewerHeader update `currentPage`. Buttons disable at bounds (page 1 and page N).

---

## Testing

**Backend:** Expand `tests/test_documents.py`:
- `test_get_document_file_success` — upload a document, hit the file endpoint, assert 200 and correct content-type
- `test_get_document_file_not_found` — hit the endpoint with a nonexistent document ID, assert 404

**Frontend:** Manual verification against the running app. Confirmed working when:
- A real PDF renders in the left pane with page navigation working
- Extractions load in the right pane with confidence coloring
- Selecting a different document from the list navigates correctly
- Error states render correctly for pending and failed documents

Frontend Vitest coverage is deferred to Phase 3 per the roadmap.

---

## What Is Explicitly Out of Scope

- Field-level linking (clicking a field highlights its location in the PDF) — deferred, separate build
- Extraction editing or correction — that belongs to the Extraction Review UI (Phase 2A follow-up)
- Export from the viewer — belongs to Data Export (Phase 2C)
- Real-time extraction status (SSE) — belongs to Phase 2C

---

## Files Changed

| File | Change |
|---|---|
| `backend/app/routers/documents.py` | Add `GET /documents/{id}/file` endpoint |
| `backend/tests/test_documents.py` | Add 2 tests for the file endpoint |
| `frontend/src/api/documents.js` | Add `getDocumentFile()` |
| `frontend/src/App.jsx` | Add `documents/:documentId` route |
| `frontend/src/pages/workspace/Documents.jsx` | Use `DocumentList` component, remove inline extraction panel |
| `frontend/src/components/documents/DocumentList.jsx` | New — extracted from Documents.jsx |
| `frontend/src/pages/workspace/DocumentViewer.jsx` | New — full viewer page |
