import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listDocuments, uploadDocument, getExtractions } from '../../api/documents'
import DropZone from '../../components/documents/DropZone'
import ExtractionTable from '../../components/documents/ExtractionTable'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function Documents() {
  const { workspaceId } = useParams()
  const [documents, setDocuments] = useState([])
  const [selected, setSelected] = useState(null)
  const [extractions, setExtractions] = useState([])
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
      handleSelect(res.data)
    } finally {
      setUploading(false)
    }
  }

  const handleSelect = async (doc) => {
    setSelected(doc)
    const res = await getExtractions(workspaceId, doc.id)
    setExtractions(res.data)
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="flex gap-6 h-full">
      <div className="w-80 shrink-0 space-y-4">
        <DropZone onFile={handleFile} uploading={uploading} />
        <div className="space-y-2">
          {documents.map((doc) => (
            <button
              key={doc.id}
              onClick={() => handleSelect(doc)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                selected?.id === doc.id
                  ? 'border-blue-500 bg-slate-800'
                  : 'border-slate-700 bg-slate-800 hover:border-slate-500'
              }`}
            >
              <p className="text-white text-xs font-mono truncate">{doc.filename}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-slate-500 text-xs">{doc.detected_doc_type || 'Unknown'}</span>
                <Badge label={doc.extraction_status} />
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1">
        {selected ? (
          <div>
            <h2 className="text-white font-semibold mb-1">{selected.filename}</h2>
            <p className="text-slate-500 text-xs mb-4">Original: {selected.original_filename}</p>
            <ExtractionTable extractions={extractions} />
          </div>
        ) : (
          <p className="text-slate-500 text-sm">Select a document to view its extracted fields.</p>
        )}
      </div>
    </div>
  )
}
