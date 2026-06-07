import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { listDocuments, uploadDocument, getExtractionsCSV, getExtractionsJSON, getWorkspaceExtractionsCSV } from '../../api/documents'
import DropZone from '../../components/documents/DropZone'
import DocumentList from '../../components/documents/DocumentList'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import ResizeHandle from '../../components/shared/ResizeHandle'
import { useResizable } from '../../hooks/useResizable'
import { useToast } from '../../hooks/useToast'
import useExtractionStream from '../../hooks/useExtractionStream'

export default function Documents() {
  const { workspaceId } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [exportingWorkspace, setExportingWorkspace] = useState(false)

  useEffect(() => {
    listDocuments(workspaceId).then((r) => setDocuments(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const handleUpdate = useCallback((docId, payload) => {
    setDocuments((prev) =>
      prev.map((d) => {
        if (d.id !== docId) return d
        const updated = { ...d, extraction_status: payload.extraction_status }
        if (payload.detected_doc_type) updated.detected_doc_type = payload.detected_doc_type
        if (payload.filename) updated.filename = payload.filename
        if (payload.extraction_status === 'complete') {
          toast.success('Extraction complete', `${d.filename} · ${payload.field_count ?? ''} fields`)
        } else if (payload.extraction_status === 'failed') {
          toast.error('Extraction failed', payload.extraction_error || d.filename)
        } else if (payload.extraction_status === 'needs_review') {
          toast.warning('Review needed', `${d.filename} has low-confidence fields`)
        }
        return updated
      })
    )
  }, [toast])

  const handleFiles = async (files) => {
    setUploading(true)
    let lastId = null
    for (const file of files) {
      try {
        const res = await uploadDocument(workspaceId, file)
        setDocuments((prev) => [res.data, ...prev])
        toast.info('Uploaded', `${file.name} — extracting`)
        lastId = res.data.id
      } catch {
        toast.error('Upload failed', file.name)
      }
    }
    setUploading(false)
    if (lastId && files.length === 1) {
      navigate(`/workspaces/${workspaceId}/documents/${lastId}`)
    }
  }

  const handleExportCSV = async (doc) => {
    try {
      await getExtractionsCSV(workspaceId, doc.id, doc.filename)
      toast.info('Download started', `${doc.filename}_extractions.csv`)
    } catch {
      toast.error('Export failed', doc.filename)
    }
  }

  const handleExportJSON = async (doc) => {
    try {
      await getExtractionsJSON(workspaceId, doc.id, doc.filename)
      toast.info('Download started', `${doc.filename}_extractions.json`)
    } catch {
      toast.error('Export failed', doc.filename)
    }
  }

  const handleWorkspaceExport = async () => {
    setExportingWorkspace(true)
    try {
      await getWorkspaceExtractionsCSV(workspaceId)
      toast.info('Download started', 'workspace_extractions.csv')
    } catch {
      toast.error('Export failed', 'Could not export workspace extractions')
    } finally {
      setExportingWorkspace(false)
    }
  }

  const [listWidth, startListResize] = useResizable(300, { min: 200, max: 560 })

  if (loading) return <LoadingSpinner />

  const pendingDocs = documents.filter((d) => d.extraction_status === 'pending')
  const exportable = (status) => status === 'complete' || status === 'needs_review'

  return (
    <div className="flex -m-6 h-[calc(100vh-52px)]">
      {/* Document list pane */}
      <div
        className="shrink-0 flex flex-col overflow-hidden"
        style={{ width: listWidth, borderRight: '1px solid #1A2A3F' }}
      >
        <div className="flex items-center justify-between px-4 pt-4 pb-2 shrink-0">
          <span className="text-slate-300 text-sm font-medium">Documents</span>
          <button
            onClick={handleWorkspaceExport}
            disabled={exportingWorkspace}
            className="text-xs text-slate-400 hover:text-white disabled:opacity-40 transition-colors"
          >
            ⬇ Export all
          </button>
        </div>
        <div className="px-4 pb-3 shrink-0">
          <DropZone onFiles={handleFiles} uploading={uploading} />
        </div>
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          <DocumentList
            documents={documents}
            selectedId={null}
            workspaceId={workspaceId}
            renderActions={(doc) => (
              <DocMenu
                doc={doc}
                onCSV={() => handleExportCSV(doc)}
                onJSON={() => handleExportJSON(doc)}
                disabled={!exportable(doc.extraction_status)}
              />
            )}
          />
        </div>
      </div>

      <ResizeHandle onMouseDown={startListResize} />

      {/* Placeholder / content area */}
      <div className="flex-1 flex items-center justify-center min-w-0">
        <p className="text-slate-600 text-sm">Select a document to view it.</p>
      </div>

      {pendingDocs.map((doc) => (
        <StreamWatcher key={doc.id} workspaceId={workspaceId} doc={doc} onUpdate={handleUpdate} />
      ))}
    </div>
  )
}

function StreamWatcher({ workspaceId, doc, onUpdate }) {
  useExtractionStream(workspaceId, doc.id, doc.extraction_status, onUpdate)
  return null
}

function DocMenu({ doc, onCSV, onJSON, disabled }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div ref={ref} className="relative" onClick={(e) => e.preventDefault()}>
      <button
        type="button"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        className="w-6 h-6 flex items-center justify-center rounded text-sm text-slate-500 hover:text-white hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        ⋯
      </button>
      {open && (
        <div className="absolute right-0 top-7 z-10 bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 w-36">
          <button
            onClick={() => { onCSV(); setOpen(false) }}
            disabled={disabled}
            className="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ⬇ Download CSV
          </button>
          <button
            onClick={() => { onJSON(); setOpen(false) }}
            disabled={disabled}
            className="w-full text-left px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ⬇ Download JSON
          </button>
        </div>
      )}
    </div>
  )
}
