# Phase 2C UI — Design Spec

**Date:** 2026-05-28  
**Status:** Approved  
**Scope:** Engine-level UI completeness — toast notifications, document status badges, real-time extraction status (SSE), data export, audit log UI.

Observability dashboard (originally part of 2C) is a separate planning session — design discussion on layout, colors, and fonts required before build.

---

## Features

### 1. Toast Notification System

**What it is:** Global in-app feedback for actions and async events.

**Design decisions (approved):**
- Position: bottom-right
- Style: title + optional message line (Option A from visual review)
- Four variants: `success` (green), `error` (red), `info` (blue), `warning` (orange)
- Auto-dismisses after 4 seconds; manually dismissable with ×
- Max 3 toasts visible simultaneously — oldest drops when a 4th arrives
- No external library

**Interface:**
```js
const { toast } = useToast()
toast.success("Correction saved", "sale_amount updated to $285,000")
toast.error("Upload failed", "File exceeds 50 MB limit")
toast.info("Download started", "extractions.csv")
toast.warning("3 fields below threshold", "Document flagged for review")
```

**New files:**
- `frontend/src/hooks/useToast.js` — context + hook
- `frontend/src/components/shared/ToastContainer.jsx` — renders the stack

**Modified files:**
- `frontend/src/pages/workspace/WorkspaceLayout.jsx` — mount `<ToastContainer />`

**Consumers in this spec:** SSE fires toast on extraction complete. Export fires toast on download start. All existing silent mutations (correction save, entity create, etc.) gain toasts as a follow-on.

---

### 2. Document Status Badges

**What it is:** Pill badge on every document card showing extraction status at a glance.

**Design decisions (approved):**
- Style: pill badges, right-aligned on each card (Option A from visual review)
- Five states:

| Status | Color |
|---|---|
| `complete` | Green (`bg-green-900 text-green-400`) |
| `pending` | Gray muted, bordered (`bg-slate-800 text-slate-500 border border-slate-700`) |
| `needs_review` | Orange (`bg-orange-950 text-orange-400`) |
| `no_schema` | Indigo (`bg-indigo-950 text-indigo-400`) |
| `failed` | Red (`bg-red-950 text-red-400`) |

**Modified files:**
- `frontend/src/components/documents/DocumentList.jsx` — add `StatusBadge` helper, render badge on each card

**Backend changes:** None. `extraction_status` already included in `DocumentOut`.

---

### 3. Real-Time Extraction Status (SSE)

**What it is:** Document list updates live as the background pipeline runs — no polling, no page refresh.

**Backend:**
- New endpoint: `GET /workspaces/{workspace_id}/documents/{document_id}/status/stream`
- `StreamingResponse` with `media_type="text/event-stream"`
- Polls DB every 2 seconds, pushes: `data: {"status": "complete", "extraction_status": "complete"}\n\n`
- Closes stream when status reaches terminal state: `complete` | `failed` | `no_schema` | `needs_review`
- Hard timeout at 5 minutes — stream closes regardless
- Auth: endpoint uses `get_current_user` dependency. The handler must enforce two checks before opening the stream:
  1. **Workspace membership** — call `get_workspace_or_404(workspace_id, user, db)` to confirm the authenticated user has access to the workspace.
  2. **Document ownership** — query `Document.id == document_id, Document.workspace_id == workspace_id` to confirm the document belongs to that workspace.
  Both checks must pass. A workspace the user cannot access returns 403; a document not in that workspace returns 404. Neither opens a stream.

**SSE message format:**
```
data: {"extraction_status": "complete", "detected_doc_type": "DEED", "field_count": 64}\n\n
data: {"extraction_status": "failed", "extraction_error": "OCR failed: ..."}\n\n
```

**Frontend:**
- `Documents.jsx` — on load, any document with `extraction_status === "pending"` opens an `EventSource` connection to the stream endpoint
- On terminal status event: update document in local state → badge flips live
- On `complete`: fire `toast.success("Extraction complete", "<filename> · <field_count> fields")`
- On `failed`: fire `toast.error("Extraction failed", extraction_error)`
- `EventSource` closes automatically on terminal event or component unmount
- Multiple pending documents = multiple parallel connections (acceptable at single-user scale)

**SSE error handling and reconnect (in `useExtractionStream.js`):**
- Wrap `EventSource` with `onopen`, `onmessage`, and `onerror` handlers.
- On `onerror`: increment retry count and schedule a new `EventSource` with exponential backoff (base 1 s, doubles each attempt, cap 32 s). Max 5 retries total.
- Stop retrying immediately if: (a) the last received message was a terminal status, (b) the component has unmounted.
- After exhausting all retries without a terminal event, surface a final "failed" state.
- Stream connection state exposed from the hook: `"connecting" | "connected" | "disconnected" | "failed"`. `Documents.jsx` reads this to show status and trigger toasts:
  - First connection attempt fails → no toast (transient).
  - All retries exhausted → `toast.error("Extraction stream lost", "<filename> — refresh to check status")`.
- On unmount or terminal event: cancel any pending backoff timer and close the `EventSource`. No dangling connections.

**New files:**
- `frontend/src/hooks/useExtractionStream.js` — manages EventSource lifecycle, exponential-backoff reconnect, and stream connection state for one document

**Modified files:**
- `backend/app/routers/documents.py` — add SSE endpoint
- `frontend/src/pages/workspace/Documents.jsx` — call `useExtractionStream` for pending docs

---

### 4. Data Export

**What it is:** Download extracted fields per document or per workspace as CSV or JSON.

**Backend — per-document:**
- `GET /workspaces/{id}/documents/{doc_id}/extractions.csv`
- `GET /workspaces/{id}/documents/{doc_id}/extractions.json`
- Returns latest-attempt-per-field (same logic as `list_extractions`)
- CSV columns: `field_name, field_value, field_type, confidence, attempt`
- JSON: array of the same objects
- Response header: `Content-Disposition: attachment; filename="<doc_filename>_extractions.csv"`

**Backend — workspace-level:**
- `GET /workspaces/{id}/extractions.csv`
- `GET /workspaces/{id}/extractions.json`
- All extractions across all non-deleted documents in the workspace
- Two prepended columns: `document_filename, document_type`
- Only documents with `extraction_status = "complete"` or `"needs_review"` included

**Frontend:**
- `Documents.jsx` — `⋯` context menu button on each document row (Option C from visual review)
  - "Download CSV" → triggers per-document CSV download
  - "Download JSON" → triggers per-document JSON download
  - Menu items dimmed (non-clickable) if document status is not `complete` or `needs_review`
- "Export workspace" button in the documents page toolbar → workspace CSV download
- On download start: `toast.info("Download started", "<filename>")`
- Downloads triggered via `<a href="..." download>` pattern — no blob fetch needed, browser handles the file

**New files:**
- None — endpoints added to existing `documents.py` router

**Modified files:**
- `backend/app/routers/documents.py` — four new endpoints
- `frontend/src/pages/workspace/Documents.jsx` — context menu + workspace export button
- `frontend/src/api/documents.js` — `getExtractionsCSV`, `getExtractionsJSON`, `getWorkspaceExtractionsCSV`

---

### 5. Audit Log UI

**What it is:** Read-only chronological log per workspace surfacing the existing immutable `audit_log` table.

**Backend:**
- New endpoint: `GET /workspaces/{id}/audit-log?page=1&limit=50`
- Returns: `{ entries: AuditLogEntry[], total: int, page: int, pages: int }`
- Ordered newest-first
- Scoped to `workspace_id` — only entries for this workspace

**`AuditLogOut` schema:**
```python
class AuditLogOut(BaseModel):
    id: str
    action: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    user_id: Optional[str]
    before_state: Optional[dict]
    after_state: Optional[dict]
    timestamp: datetime  # column name is 'timestamp', not 'created_at'
    class Config: from_attributes = True
```

**Frontend — `AuditLog.jsx` at `/workspaces/:id/audit`:**

Layout: timeline with colored dot per action type (Option A from visual review).

Action dot colors:
| Action pattern | Color |
|---|---|
| `uploaded` | Blue |
| `extraction_corrected` | Green |
| `document_file_accessed` | Purple |
| `searched` | Amber |
| all others | Slate |

Controls above timeline:
- **Search input** — client-side free-text filter on `action` + `entity_type` + detail derived from `after_state`. Filters current page only.
- **Action filter dropdown** — All / Uploads / Corrections / Searches / File accesses. Client-side, maps to action name patterns.

Pagination:
- Previous / Next buttons at bottom
- "Page 2 of 7" indicator
- Fetches fresh page from backend on navigate
- Search and filter reset on page change

Detail line per entry: derived from `action` + `entity_type` + `after_state`. Full mapping:

| `action` | Detail string |
|---|---|
| `uploaded` | `{after_state.filename} · {entity_type} · {after_state.field_count} fields` |
| `extraction_corrected` | `{after_state.field_name} corrected on {after_state.filename}` |
| `document_file_accessed` | `{after_state.filename} accessed` |
| `searched` | `"{after_state.query}"` (quoted) |
| anything else | `{action} on {entity_type}` |

**Null / missing field handling:**
- Any field referenced above that is absent from `after_state` is omitted from the string (not replaced with a placeholder). If all optional parts are missing, fall back to `{action} on {entity_type}`.
- If `entity_type` itself is null, use `{action}` alone.
- `after_state` null entirely → use `{action}` alone.
- `after_state.field_count` missing on `uploaded` → render `{filename} · {entity_type}` (drop the fields segment).

**Future actions:** Any `action` not listed above uses the generic fallback `{action} on {entity_type}`. Implementers adding new action types should extend this table in both the spec and the audit detail builder.

Subtitle on page: "Every action on every document is tamper-proof."

**New files:**
- `frontend/src/pages/workspace/AuditLog.jsx`
- `backend/app/schemas/audit.py`
- `backend/app/routers/audit.py`

**Modified files:**
- `backend/app/main.py` — register `audit.router`
- `frontend/src/App.jsx` — add `audit` route
- `frontend/src/components/layout/WorkspaceSidebar.jsx` — `Audit Log` already planned in ENGINE_SECTIONS, just needs path wired

---

## Build Sequence

1. **Toast system** — foundation, everything else uses it
2. **Status badges** — no backend, fast win
3. **SSE** — backend endpoint + frontend hook + toast integration
4. **Data export** — backend endpoints + frontend context menu + toast integration
5. **Audit log** — backend endpoint + frontend page + pagination + search/filter

---

## Files Summary

| File | Change |
|---|---|
| `frontend/src/hooks/useToast.js` | CREATE |
| `frontend/src/components/shared/ToastContainer.jsx` | CREATE |
| `frontend/src/hooks/useExtractionStream.js` | CREATE |
| `frontend/src/pages/workspace/AuditLog.jsx` | CREATE |
| `backend/app/schemas/audit.py` | CREATE |
| `backend/app/routers/audit.py` | CREATE |
| `frontend/src/pages/workspace/WorkspaceLayout.jsx` | MODIFY — mount ToastContainer |
| `frontend/src/components/documents/DocumentList.jsx` | MODIFY — status badges |
| `frontend/src/pages/workspace/Documents.jsx` | MODIFY — SSE hook, context menu, export button |
| `frontend/src/api/documents.js` | MODIFY — export API functions |
| `backend/app/routers/documents.py` | MODIFY — SSE endpoint + 4 export endpoints |
| `backend/app/main.py` | MODIFY — register audit router |
| `frontend/src/App.jsx` | MODIFY — audit route |
| `frontend/src/components/layout/WorkspaceSidebar.jsx` | MODIFY — wire audit path |
