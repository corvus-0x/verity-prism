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
