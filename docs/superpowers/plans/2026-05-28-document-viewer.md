# Document Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a split-pane document viewer that renders source PDFs (65%) alongside extracted fields (35%), accessible via `/workspaces/:workspaceId/documents/:documentId`.

**Architecture:** New `GET /documents/{id}/file` endpoint streams stored files from disk using `doc.file_path`. Frontend fetches the file as a blob (auth handled by existing axios interceptor), renders it with react-pdf, and shows extraction fields alongside. `DocumentList` is extracted from `Documents.jsx` so both the list page and viewer share identical list behavior.

**Tech Stack:** react-pdf (bundles pdf.js — no external viewer needed), FastAPI FileResponse, axios blob responseType

---

## Files Changed

| File | Action |
|---|---|
| `backend/app/routers/documents.py` | Add `GET /documents/{id}/file` endpoint |
| `backend/tests/test_documents.py` | Add 2 tests for the file endpoint |
| `frontend/src/api/documents.js` | Add `getDocumentFile()` |
| `frontend/src/App.jsx` | Add `documents/:documentId` route |
| `frontend/src/components/documents/DocumentList.jsx` | **New** — extracted from Documents.jsx |
| `frontend/src/pages/workspace/Documents.jsx` | Use DocumentList, navigate to viewer after upload |
| `frontend/src/pages/workspace/DocumentViewer.jsx` | **New** — full viewer page |
| `docs/build-inventory.md` | Mark viewer + file endpoint as complete |

---

## Task 1: Backend — file serve endpoint (TDD)

**Files:**
- Modify: `backend/app/routers/documents.py`
- Test: `backend/tests/test_documents.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `backend/tests/test_documents.py`:

```python
def test_get_document_file(client, auth_headers, workspace_id):
    content = b"%PDF-1.4 test content"
    upload_response = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("test.pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_headers,
    )
    doc_id = upload_response.json()["id"]

    response = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/file",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    assert response.content == content


def test_get_document_file_not_found(client, auth_headers, workspace_id):
    response = client.get(
        f"/workspaces/{workspace_id}/documents/nonexistent-id/file",
        headers=auth_headers,
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_documents.py::test_get_document_file tests/test_documents.py::test_get_document_file_not_found -v
```

Expected: FAIL — 404 or 405 (route does not exist yet)

- [ ] **Step 3: Update imports in `backend/app/routers/documents.py`**

Replace the existing import block at the top of the file:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.schemas.document import DocumentOut, ExtractionOut
from app.services.auth import get_current_user
from app.services.document_pipeline import create_pending_document, process_upload_background
from app.services import audit
from app.routers.workspaces import get_workspace_or_404
```

- [ ] **Step 4: Add the endpoint to `backend/app/routers/documents.py`**

Add after the `list_extractions` function at the bottom of the file:

```python
_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".xml": "application/xml",
}


@router.get("/documents/{document_id}/file")
def get_document_file(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve the raw source file for a document."""
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        audit.log(
            db,
            action="document_file_missing",
            workspace_id=workspace_id,
            entity_type="document",
            entity_id=document_id,
        )
        raise HTTPException(status_code=404, detail="File not found on disk")

    audit.log(
        db,
        action="document_file_accessed",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
    )

    media_type = _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(str(file_path), media_type=media_type)
```

- [ ] **Step 5: Run all document tests to confirm they pass**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_documents.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/documents.py backend/tests/test_documents.py
git commit -m "feat: add GET /documents/{id}/file endpoint with audit logging"
```

---

## Task 2: Frontend API client + route setup

**Files:**
- Modify: `frontend/src/api/documents.js`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/pages/workspace/DocumentViewer.jsx` (placeholder)

- [ ] **Step 1: Add `getDocumentFile` to `frontend/src/api/documents.js`**

Add after `getExtractions`:

```js
export const getDocumentFile = (workspaceId, documentId) =>
  client.get(`/workspaces/${workspaceId}/documents/${documentId}/file`, {
    responseType: 'blob',
  })
```

- [ ] **Step 2: Create a placeholder `DocumentViewer.jsx` to unblock the route import**

Create `frontend/src/pages/workspace/DocumentViewer.jsx`:

```jsx
export default function DocumentViewer() {
  return <div className="text-white p-4">Viewer coming soon</div>
}
```

- [ ] **Step 3: Add the viewer route to `frontend/src/App.jsx`**

Add the import at the top with the other workspace page imports:

```jsx
import DocumentViewer from './pages/workspace/DocumentViewer'
```

Inside the workspace `<Route>` block, add the viewer route after the `documents` route:

```jsx
<Route path="/workspaces/:workspaceId" element={
  <ProtectedRoute><WorkspaceLayout /></ProtectedRoute>
}>
  <Route index element={<Overview />} />
  <Route path="documents" element={<Documents />} />
  <Route path="documents/:documentId" element={<DocumentViewer />} />
  <Route path="search" element={<Search />} />
  <Route path="entities" element={<Entities />} />
  <Route path="transactions" element={<Transactions />} />
  <Route path="findings" element={<Findings />} />
  <Route path="leads" element={<Leads />} />
  <Route path="chat" element={<AIChat />} />
</Route>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/documents.js frontend/src/App.jsx frontend/src/pages/workspace/DocumentViewer.jsx
git commit -m "feat: getDocumentFile API client, viewer route wired"
```

---

## Task 3: Extract DocumentList component + update Documents page

**Files:**
- Create: `frontend/src/components/documents/DocumentList.jsx`
- Modify: `frontend/src/pages/workspace/Documents.jsx`

- [ ] **Step 1: Create `frontend/src/components/documents/DocumentList.jsx`**

```jsx
import { Link } from 'react-router-dom'
import Badge from '../shared/Badge'

export default function DocumentList({ documents, selectedId, workspaceId }) {
  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <Link
          key={doc.id}
          to={`/workspaces/${workspaceId}/documents/${doc.id}`}
          className={`block p-3 rounded-lg border transition-colors ${
            selectedId === doc.id
              ? 'border-blue-500 bg-slate-800'
              : 'border-slate-700 bg-slate-800 hover:border-slate-500'
          }`}
        >
          <p className="text-white text-xs font-mono truncate">{doc.filename}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-slate-500 text-xs">{doc.detected_doc_type || 'Unknown'}</span>
            <Badge label={doc.extraction_status} />
          </div>
        </Link>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Replace `frontend/src/pages/workspace/Documents.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { listDocuments, uploadDocument } from '../../api/documents'
import DropZone from '../../components/documents/DropZone'
import DocumentList from '../../components/documents/DocumentList'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function Documents() {
  const { workspaceId } = useParams()
  const navigate = useNavigate()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    listDocuments(workspaceId).then((r) => setDocuments(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const handleFile = async (file) => {
    setUploading(true)
    try {
      const res = await uploadDocument(workspaceId, file)
      setDocuments((prev) => [res.data, ...prev])
      navigate(`/workspaces/${workspaceId}/documents/${res.data.id}`)
    } finally {
      setUploading(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="flex gap-6 h-full">
      <div className="w-80 shrink-0 space-y-4">
        <DropZone onFile={handleFile} uploading={uploading} />
        <DocumentList documents={documents} selectedId={null} workspaceId={workspaceId} />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <p className="text-slate-600 text-sm">Select a document to view it.</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify in the running app**

```bash
docker-compose up --build
```

Open `http://localhost:5173`, navigate to a workspace's Documents page. Verify:
- Document list renders with correct filenames and status badges
- Clicking a document navigates to `/workspaces/:id/documents/:docId` (shows "Viewer coming soon" placeholder)
- Upload still works — navigates to the viewer route after upload

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/documents/DocumentList.jsx frontend/src/pages/workspace/Documents.jsx
git commit -m "feat: extract DocumentList component, Documents navigates to viewer on upload"
```

---

## Task 4: DocumentViewer — data loading, layout, and status states

**Files:**
- Modify: `frontend/src/pages/workspace/DocumentViewer.jsx`

- [ ] **Step 1: Replace the placeholder with the full viewer skeleton**

Replace the entire contents of `frontend/src/pages/workspace/DocumentViewer.jsx`:

```jsx
import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { listDocuments, getDocument, getExtractions, getDocumentFile } from '../../api/documents'
import DocumentList from '../../components/documents/DocumentList'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function DocumentViewer() {
  const { workspaceId, documentId } = useParams()
  const [docList, setDocList] = useState([])
  const [doc, setDoc] = useState(null)
  const [extractions, setExtractions] = useState([])
  const [fileUrl, setFileUrl] = useState(null)
  const [fileError, setFileError] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const fileUrlRef = useRef(null)

  // Fetch the doc list independently — doesn't change when documentId changes
  useEffect(() => {
    listDocuments(workspaceId).then((r) => setDocList(r.data))
  }, [workspaceId])

  // Fetch doc metadata, extractions, and file in parallel when documentId changes
  useEffect(() => {
    setLoading(true)
    setError(null)
    setFileError(false)
    setCurrentPage(1)
    setTotalPages(0)

    // Revoke previous blob URL to free memory
    if (fileUrlRef.current) {
      URL.revokeObjectURL(fileUrlRef.current)
      fileUrlRef.current = null
      setFileUrl(null)
    }

    Promise.allSettled([
      getDocument(workspaceId, documentId),
      getExtractions(workspaceId, documentId),
      getDocumentFile(workspaceId, documentId),
    ]).then(([docRes, extRes, fileRes]) => {
      if (docRes.status === 'rejected') {
        setError('Document not found.')
        return
      }
      setDoc(docRes.value.data)
      setExtractions(extRes.status === 'fulfilled' ? extRes.value.data : [])

      if (fileRes.status === 'fulfilled') {
        const url = URL.createObjectURL(fileRes.value.data)
        fileUrlRef.current = url
        setFileUrl(url)
      } else {
        setFileError(true)
      }
    }).finally(() => setLoading(false))

    return () => {
      if (fileUrlRef.current) {
        URL.revokeObjectURL(fileUrlRef.current)
        fileUrlRef.current = null
      }
    }
  }, [workspaceId, documentId])

  if (loading) return <LoadingSpinner />

  if (error) {
    return (
      <div className="flex gap-6 h-full">
        <div className="w-52 shrink-0 space-y-2 overflow-y-auto">
          <DocumentList documents={docList} selectedId={documentId} workspaceId={workspaceId} />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-white mb-2">Document not found.</p>
            <Link
              to={`/workspaces/${workspaceId}/documents`}
              className="text-blue-400 text-sm hover:underline"
            >
              ← Back to documents
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex -m-6 h-[calc(100vh-4rem)]">
      {/* Document list column */}
      <div className="w-52 shrink-0 bg-slate-900 border-r border-slate-700 p-3 overflow-y-auto">
        <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider mb-3">
          Documents
        </p>
        <DocumentList documents={docList} selectedId={documentId} workspaceId={workspaceId} />
      </div>

      {/* Viewer area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700 shrink-0">
          <div className="min-w-0">
            <span className="text-white text-sm font-medium truncate block">{doc.filename}</span>
            <span className="text-slate-500 text-xs">
              {doc.detected_doc_type || 'Unknown'} · {extractions.length} fields
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-4">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="px-2 py-1 text-xs bg-slate-800 border border-slate-600 text-slate-300 rounded disabled:opacity-40"
            >
              ← Prev
            </button>
            <span className="text-slate-400 text-xs w-16 text-center">
              {totalPages > 0 ? `${currentPage} / ${totalPages}` : '—'}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages || totalPages === 0}
              className="px-2 py-1 text-xs bg-slate-800 border border-slate-600 text-slate-300 rounded disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>

        {/* Split pane */}
        <div className="flex flex-1 min-h-0">
          {/* PDF pane — 65% */}
          <div className="flex-[65] bg-slate-950 flex items-start justify-center border-r border-slate-700 overflow-auto py-6">
            {fileError ? (
              <div className="text-center p-6 max-w-sm">
                <p className="text-slate-300 mb-2 font-medium">Source file unavailable</p>
                <p className="text-slate-500 text-sm mb-4">
                  The stored file could not be found. Re-upload the document to restore the source view.
                </p>
                <Link
                  to={`/workspaces/${workspaceId}/documents`}
                  className="text-blue-400 text-sm hover:underline"
                >
                  ← Back to documents
                </Link>
              </div>
            ) : (
              <p className="text-slate-600 text-sm">PDF renders here — wired in Task 5</p>
            )}
          </div>

          {/* Fields pane — 35% */}
          <div className="flex-[35] overflow-y-auto p-4">
            <FieldsPane doc={doc} extractions={extractions} />
          </div>
        </div>
      </div>
    </div>
  )
}

function FieldsPane({ doc, extractions }) {
  if (doc.extraction_status === 'pending') {
    return <p className="text-slate-400 text-sm">Extraction in progress…</p>
  }
  if (doc.extraction_status === 'failed') {
    return (
      <div>
        <p className="text-red-400 text-sm font-medium mb-2">Extraction failed</p>
        <p className="text-slate-400 text-xs font-mono bg-slate-800 p-3 rounded">
          {doc.extraction_error || 'No details available.'}
        </p>
      </div>
    )
  }
  if (doc.extraction_status === 'no_schema') {
    return (
      <p className="text-slate-400 text-sm">
        No schema found for this document type. An investigation lead was created.
      </p>
    )
  }
  return <p className="text-slate-600 text-sm">Fields table — wired in Task 6</p>
}
```

- [ ] **Step 2: Verify in the running app**

Navigate to a document's viewer URL. Check:
- Document list renders on the left, selected doc is highlighted in blue
- Header shows filename, doc type, field count
- Page nav buttons render (disabled until PDF loads in Task 5)
- For a failed document: `extraction_error` text is shown in a monospace box
- For a pending document: "Extraction in progress…" renders
- For a no_schema document: informative message renders
- File-missing state: try navigating to a doc whose file was deleted — shows "Source file unavailable"

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/workspace/DocumentViewer.jsx
git commit -m "feat: DocumentViewer layout — list column, header, status states, split pane skeleton"
```

---

## Task 5: Install react-pdf + wire PDF rendering

**Files:**
- Modify: `frontend/src/pages/workspace/DocumentViewer.jsx`
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Install react-pdf**

```bash
cd frontend && npm install react-pdf
```

- [ ] **Step 2: Verify install**

```bash
npm list react-pdf
```

Expected: `react-pdf@9.x.x` (any 9.x version)

- [ ] **Step 3: Add react-pdf imports to DocumentViewer.jsx**

Add these lines at the top of `frontend/src/pages/workspace/DocumentViewer.jsx`, after the existing imports:

```jsx
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()
```

- [ ] **Step 4: Replace the PDF pane placeholder with react-pdf rendering**

In the DocumentViewer return, replace the `{/* PDF pane — 65% */}` div's inner content (keep the outer div):

```jsx
{/* PDF pane — 65% */}
<div className="flex-[65] bg-slate-950 flex items-start justify-center border-r border-slate-700 overflow-auto py-6">
  {fileError ? (
    <div className="text-center p-6 max-w-sm">
      <p className="text-slate-300 mb-2 font-medium">Source file unavailable</p>
      <p className="text-slate-500 text-sm mb-4">
        The stored file could not be found. Re-upload the document to restore the source view.
      </p>
      <Link
        to={`/workspaces/${workspaceId}/documents`}
        className="text-blue-400 text-sm hover:underline"
      >
        ← Back to documents
      </Link>
    </div>
  ) : fileUrl ? (
    <Document
      file={fileUrl}
      onLoadSuccess={({ numPages }) => {
        setTotalPages(numPages)
        setCurrentPage(1)
      }}
      loading={<LoadingSpinner />}
      error={<p className="text-slate-400 text-sm p-4">Could not load PDF.</p>}
    >
      <Page
        pageNumber={currentPage}
        renderTextLayer={false}
        renderAnnotationLayer={false}
        className="shadow-2xl"
      />
    </Document>
  ) : (
    <LoadingSpinner />
  )}
</div>
```

- [ ] **Step 5: Rebuild and verify in the app**

```bash
docker-compose up --build
```

Open a workspace, click a document. Verify:
- PDF renders in the left pane
- Page navigation works — Prev/Next enabled/disabled at bounds, page count shows correctly
- Different pages render when navigating
- Clicking a different document in the list loads that document's PDF

If the worker fails to load (console error about `pdf.worker.min.mjs`), try this alternative worker setup instead:

```jsx
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/workspace/DocumentViewer.jsx frontend/package.json frontend/package-lock.json
git commit -m "feat: wire react-pdf PDF rendering in DocumentViewer"
```

---

## Task 6: Wire ExtractionTable + update build inventory

**Files:**
- Modify: `frontend/src/pages/workspace/DocumentViewer.jsx`
- Modify: `docs/build-inventory.md`

- [ ] **Step 1: Add ExtractionTable import to DocumentViewer.jsx**

Add to the imports at the top of the file:

```jsx
import ExtractionTable from '../../components/documents/ExtractionTable'
```

- [ ] **Step 2: Replace the FieldsPane placeholder return with ExtractionTable**

Replace the `FieldsPane` function entirely:

```jsx
function FieldsPane({ doc, extractions }) {
  if (doc.extraction_status === 'pending') {
    return <p className="text-slate-400 text-sm">Extraction in progress…</p>
  }
  if (doc.extraction_status === 'failed') {
    return (
      <div>
        <p className="text-red-400 text-sm font-medium mb-2">Extraction failed</p>
        <p className="text-slate-400 text-xs font-mono bg-slate-800 p-3 rounded">
          {doc.extraction_error || 'No details available.'}
        </p>
      </div>
    )
  }
  if (doc.extraction_status === 'no_schema') {
    return (
      <p className="text-slate-400 text-sm">
        No schema found for this document type. An investigation lead was created.
      </p>
    )
  }
  return (
    <div>
      <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider mb-3">
        Extracted Fields
      </p>
      <ExtractionTable extractions={extractions} />
    </div>
  )
}
```

- [ ] **Step 3: End-to-end verification in the running app**

Run through the golden path:
1. Upload a PDF — navigates to viewer, PDF renders, extracted fields appear on the right
2. Page navigation — Prev/Next moves through pages
3. Click a different document in the list — viewer loads that document, highlight moves
4. Navigate back to Documents page — list shows, clicking a doc goes to viewer
5. Find (or force) a failed document — `extraction_error` text shows in monospace box
6. Find (or force) a pending document — "Extraction in progress…" message shows

- [ ] **Step 4: Update `docs/build-inventory.md`**

In the **Pages — Workspace Level** table, change the DocumentViewer row:

```
| `pages/workspace/DocumentViewer.jsx` | `.../documents/:id` | Split-pane PDF viewer + extracted fields panel. PDF served from `GET /documents/{id}/file`, rendered with react-pdf. 65% PDF / 35% fields. Status-aware field panel surfaces extraction_error on failure. | ✅ |
```

In the **Pages — Workspace Level** table, also add DocumentList under the components section:

```
| `components/documents/DocumentList.jsx` | — | Shared document list used by both Documents and DocumentViewer. Cards are links; selected card highlighted. | ✅ |
```

In the **API Routers** table, change the file endpoint row:

```
| `documents.py` (Phase 2) | GET /documents/{id}/file — serve raw file for viewer | Engine | ✅ |
```

In the **API Clients** table, add:

```
| `documents.js` | POST + GET /documents, GET /file | ✅ |
```

In the **Update Log**, add a new row:

```
| 2026-05-28 | Document viewer complete. GET /documents/{id}/file endpoint. DocumentList extracted. DocumentViewer with react-pdf, 65/35 split, status-aware fields panel. 77/77 tests. |
```

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: 77/77 pass (75 existing + 2 new file endpoint tests)

- [ ] **Step 6: Final commit**

```bash
git add frontend/src/pages/workspace/DocumentViewer.jsx docs/build-inventory.md
git commit -m "feat: complete document viewer — PDF + extraction fields side by side"
```
