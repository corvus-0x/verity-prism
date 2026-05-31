import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getReviewQueue, flagDocument } from '../../api/documents'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

const FLAG_REASONS = [
  { value: 'low_quality_scan', label: 'Low quality scan (illegible)' },
  { value: 'missing_pages', label: 'Document missing pages' },
  { value: 'unknown_type', label: 'Unknown document type' },
  { value: 'wrong_schema', label: 'Wrong schema applied' },
  { value: 'other', label: 'Other' },
]

function FlagModal({ item, workspaceId, onClose, onFlagged }) {
  const [reason, setReason] = useState(FLAG_REASONS[0].value)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async () => {
    setSaving(true)
    try {
      await flagDocument(workspaceId, item.document_id, reason, note || null)
      onFlagged(item.document_id)
      onClose()
    } catch {
      // leave modal open on error
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl">
        <h2 className="text-white font-semibold mb-1">Flag Document</h2>
        <p className="text-slate-400 text-sm mb-4 truncate">{item.filename}</p>

        <label className="block text-slate-400 text-xs font-medium mb-1">Reason</label>
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="w-full bg-slate-800 border border-slate-600 text-white text-sm rounded px-3 py-2 mb-3 focus:outline-none focus:border-blue-500"
        >
          {FLAG_REASONS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>

        <label className="block text-slate-400 text-xs font-medium mb-1">Note (optional)</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Additional details for the reviewer…"
          className="w-full bg-slate-800 border border-slate-600 text-white text-sm rounded px-3 py-2 mb-4 focus:outline-none focus:border-blue-500 resize-none"
        />

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="px-4 py-1.5 text-sm bg-orange-600 hover:bg-orange-500 text-white rounded transition-colors disabled:opacity-50"
          >
            {saving ? 'Flagging…' : 'Flag Document'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ExtractionReview() {
  const { workspaceId } = useParams()
  const navigate = useNavigate()
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [flagging, setFlagging] = useState(null)

  useEffect(() => {
    getReviewQueue(workspaceId)
      .then((r) => setQueue(r.data))
      .finally(() => setLoading(false))
  }, [workspaceId])

  const handleFlagged = (documentId) => {
    setQueue((q) => q.filter((item) => item.document_id !== documentId))
  }

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
      {flagging && (
        <FlagModal
          item={flagging}
          workspaceId={workspaceId}
          onClose={() => setFlagging(null)}
          onFlagged={handleFlagged}
        />
      )}

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
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => setFlagging(item)}
                      className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-orange-600 text-slate-300 hover:text-white rounded transition-colors"
                    >
                      Flag
                    </button>
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
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
