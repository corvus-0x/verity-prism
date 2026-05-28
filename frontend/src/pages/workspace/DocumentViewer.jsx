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
      <div className="flex -m-6 h-[calc(100vh-4rem)]">
        <div className="w-52 shrink-0 bg-slate-900 border-r border-slate-700 p-3 overflow-y-auto">
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
