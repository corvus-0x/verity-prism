import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getReviewQueue } from '../../api/documents'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

export default function ExtractionReview() {
  const { workspaceId } = useParams()
  const navigate = useNavigate()
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getReviewQueue(workspaceId)
      .then((r) => setQueue(r.data))
      .finally(() => setLoading(false))
  }, [workspaceId])

  if (loading) return <LoadingSpinner />

  if (!queue.length) {
    return (
      <EmptyState
        title="Review queue is clear"
        description="All extractions meet the confidence threshold."
      />
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-white text-lg font-semibold">Review Queue</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {queue.length} document{queue.length !== 1 ? 's' : ''} with low-confidence fields
          </p>
        </div>
      </div>

      <div className="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-700">
              <th className="px-4 py-3 font-medium">Document</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium text-center">Low-confidence fields</th>
              <th className="px-4 py-3 font-medium">Uploaded</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {queue.map((item) => (
              <tr key={item.document_id} className="hover:bg-slate-800 transition-colors">
                <td className="px-4 py-3 text-white font-medium truncate max-w-xs">
                  {item.filename}
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {item.detected_doc_type || '—'}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-900 text-yellow-300">
                    {item.low_confidence_count}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {new Date(item.uploaded_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() =>
                      navigate(
                        `/workspaces/${workspaceId}/documents/${item.document_id}?review=1`
                      )
                    }
                    className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
                  >
                    Review
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
