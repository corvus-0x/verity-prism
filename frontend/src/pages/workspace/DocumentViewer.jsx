import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { listDocuments, getDocument, getExtractions, getDocumentFile } from '../../api/documents'
import DocumentList from '../../components/documents/DocumentList'
import ExtractionTable from '../../components/documents/ExtractionTable'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import ResizeHandle from '../../components/shared/ResizeHandle'
import { useResizable } from '../../hooks/useResizable'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import SchemaReviewPane from '../../components/documents/SchemaReviewPane'
import PDFHighlightOverlay from '../../components/documents/PDFHighlightOverlay'
import useFieldHighlight from '../../hooks/useFieldHighlight'
import { useRegionCapture } from '../../hooks/useRegionCapture'
import { getSchema } from '../../api/schemas'
import { getRenderer } from '../../components/documents/rendererRegistry'
import { useWorkspace } from '../../context/WorkspaceContext'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

export default function DocumentViewer() {
  const { workspaceId, documentId } = useParams()
  const workspace = useWorkspace()
  const [docListWidth, startDocListResize] = useResizable(220, { min: 160, max: 420 })
  const [fieldsWidth, startFieldsResize] = useResizable(380, { min: 260, max: 700, direction: 'left' })
  const [searchParams] = useSearchParams()
  const reviewMode = searchParams.get('review') === '1'
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
  const listScrollRef = useRef(null)
  const [schema, setSchema] = useState(null)
  const [pdfProxy, setPdfProxy] = useState(null)
  const [textItems, setTextItems] = useState([])
  const [pageViewport, setPageViewport] = useState(null)
  const [activeFieldName, setActiveFieldName] = useState('')
  const [activeFieldValue, setActiveFieldValue] = useState('')
  const pageContainerRef = useRef(null)

  // Preserve list scroll position across document navigation
  useEffect(() => {
    const el = listScrollRef.current
    if (!el) return
    const saved = el.scrollTop
    return () => { el.scrollTop = saved }
  }, [documentId])

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
      if (docRes.value.data.schema_id) {
        getSchema(docRes.value.data.schema_id)
          .then((r) => setSchema(r.data))
          .catch(() => {})
      }
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

  useEffect(() => {
    if (!fileUrl) return
    const loadingTask = pdfjs.getDocument(fileUrl)
    loadingTask.promise.then((pdf) => setPdfProxy(pdf))
    return () => loadingTask.destroy?.()
  }, [fileUrl])

  useEffect(() => {
    if (!pdfProxy || !currentPage) return
    pdfProxy.getPage(currentPage).then((page) => {
      const viewport = page.getViewport({ scale: 1.0 })
      setPageViewport(viewport)
      page.getTextContent().then((content) => {
        setTextItems(content.items)
      })
    })
  }, [pdfProxy, currentPage])

  const { matches, activeIndex, activeMatch, next, prev } = useFieldHighlight(
    activeFieldValue, textItems, pageViewport
  )

  const { capture } = useRegionCapture(pageContainerRef)

  const captureCurrentHighlight = useCallback((fieldName) => {
    if (!activeMatch || !pageViewport || activeFieldName !== fieldName) return null
    // activeMatch.y is in canvas space (top-left origin) from useFieldHighlight.
    // useRegionCapture.capture() expects PDF space (bottom-left origin) — invert y.
    const pdfY = pageViewport.height - activeMatch.y - activeMatch.height
    const pdfRegion = { x: activeMatch.x, y: pdfY, width: activeMatch.width, height: activeMatch.height }
    const image_b64 = capture(pdfRegion, pageViewport.height, 1.0)
    return {
      page: currentPage,
      region: pdfRegion,
      image_b64,
    }
  }, [activeMatch, pageViewport, currentPage, capture, activeFieldName])

  const handleFieldFocus = useCallback((fieldName, fieldValue) => {
    setActiveFieldName(fieldName)
    setActiveFieldValue(fieldValue || '')
  }, [])

  if (loading) return <LoadingSpinner />

  if (error) {
    return (
      <div className="flex -m-6 h-[calc(100vh-52px)]">
        <div
          className="shrink-0 bg-slate-900 p-3 overflow-y-auto"
          style={{ width: docListWidth, borderRight: '1px solid #1A2A3F' }}
        >
          <DocumentList documents={docList} selectedId={documentId} workspaceId={workspaceId} />
        </div>
        <ResizeHandle onMouseDown={startDocListResize} />
        <div className="flex-1 flex items-center justify-center min-w-0">
          <div className="text-center">
            <p className="text-slate-200 mb-2">Document not found.</p>
            <Link to={`/workspaces/${workspaceId}/documents`} className="text-red-400 text-sm hover:underline">
              ← Back to documents
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex -m-6 h-[calc(100vh-52px)]">
      {/* Document list column */}
      <div
        className="shrink-0 bg-slate-900 flex flex-col overflow-hidden"
        style={{ width: docListWidth, borderRight: '1px solid #1A2A3F' }}
      >
        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider px-3 pt-3 pb-2 shrink-0"
           style={{ letterSpacing: '0.1em' }}>
          Documents
        </p>
        <div ref={listScrollRef} className="flex-1 overflow-y-auto px-3 pb-3">
          <DocumentList documents={docList} selectedId={documentId} workspaceId={workspaceId} />
        </div>
      </div>

      <ResizeHandle onMouseDown={startDocListResize} />

      {/* Viewer area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header bar */}
        <div className="px-4 py-2 shrink-0" style={{ borderBottom: '1px solid #1A2A3F' }}>
          <span className="text-slate-100 text-sm font-medium truncate block">{doc.filename}</span>
          <span className="text-slate-400 text-xs">
            {doc.detected_doc_type || 'Unknown'} · {extractions.length} fields
          </span>
        </div>

        {/* Split pane */}
        <div className="flex flex-1 min-h-0">
          {/* PDF pane — takes remaining space */}
          <div className="flex-1 relative min-w-0">
          <div className="absolute inset-0 bg-slate-950 flex items-start justify-center overflow-auto py-6">
            {!fileError && !fileUrl && schema && doc?.source_type && doc.source_type !== 'upload' ? (
              (() => {
                const Renderer = getRenderer(
                  doc.detected_doc_type,
                  workspace?.document_render_mode || 'schema'
                )
                return <Renderer schema={schema} extractions={extractions} />
              })()
            ) : fileError ? (
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
                <div ref={pageContainerRef} style={{ position: 'relative' }}>
                  <Page
                    pageNumber={currentPage}
                    renderTextLayer={true}
                    renderAnnotationLayer={false}
                    className="shadow-2xl"
                  />
                  {reviewMode && (
                    <PDFHighlightOverlay
                      activeMatch={activeMatch}
                      activeFieldName={activeFieldName}
                      matchCount={matches.length}
                      matchIndex={activeIndex}
                      onNext={next}
                      onPrev={prev}
                    />
                  )}
                </div>
              </Document>
            ) : (
              <LoadingSpinner />
            )}
          </div>
          {/* Page controls — floating overlay at bottom center of PDF pane */}
          {totalPages > 1 && (
            <div className="absolute bottom-4 left-0 right-0 flex justify-center z-10 pointer-events-none">
              <div className="flex items-center gap-3 bg-slate-900/90 backdrop-blur-sm border border-slate-700 rounded-full px-4 py-2 shadow-xl pointer-events-auto">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  className="text-slate-300 hover:text-white disabled:opacity-30 text-sm px-1"
                >
                  ←
                </button>
                <span className="text-slate-400 text-xs min-w-[3.5rem] text-center tabular-nums">
                  {currentPage} / {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="text-slate-300 hover:text-white disabled:opacity-30 text-sm px-1"
                >
                  →
                </button>
              </div>
            </div>
          )}
          </div>

          <ResizeHandle onMouseDown={startFieldsResize} />

          {/* Fields pane — resizable from left */}
          <div
            className="flex flex-col min-h-0 shrink-0"
            style={{ width: fieldsWidth, borderLeft: '1px solid #1A2A3F' }}
          >
            {reviewMode && schema ? (
              <SchemaReviewPane
                schema={schema}
                extractions={extractions}
                workspaceId={workspaceId}
                documentId={documentId}
                onFieldFocus={handleFieldFocus}
                captureCurrentHighlight={captureCurrentHighlight}
                onSaveComplete={() => {
                  getExtractions(workspaceId, documentId).then((r) => setExtractions(r.data))
                }}
              />
            ) : (
              <div className="overflow-y-auto overflow-x-hidden p-4">
                <FieldsPane
                  doc={doc}
                  extractions={extractions}
                  editable={reviewMode}
                  workspaceId={workspaceId}
                  documentId={documentId}
                  onUpdate={(corrected) =>
                    setExtractions((prev) =>
                      prev.map((e) => (e.field_name === corrected.field_name ? corrected : e))
                    )
                  }
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function FieldsPane({ doc, extractions, editable, workspaceId, documentId, onUpdate }) {
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
        {editable ? 'Review Fields' : 'Extracted Fields'}
      </p>
      {editable && (
        <p className="text-slate-400 text-xs mb-3">
          Edit and accept low-confidence fields. Corrected fields are saved immediately.
        </p>
      )}
      <ExtractionTable
        extractions={extractions}
        editable={editable}
        workspaceId={workspaceId}
        documentId={documentId}
        onUpdate={onUpdate}
      />
    </div>
  )
}
