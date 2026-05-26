import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listFindings, updateFinding } from '../../api/findings'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

export default function Findings() {
  const { workspaceId } = useParams()
  const [findings, setFindings] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listFindings(workspaceId).then((r) => setFindings(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const handleStatus = async (id, status) => {
    const res = await updateFinding(workspaceId, id, { status })
    setFindings((prev) => prev.map((f) => f.id === id ? res.data : f))
  }

  if (loading) return <LoadingSpinner />
  if (!findings.length) return <EmptyState message="No findings recorded yet." />

  return (
    <div className="space-y-3">
      {findings.map((f) => (
        <div key={f.id} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Badge label={f.severity} />
                <Badge label={f.status} />
              </div>
              <h3 className="text-white font-medium">{f.title}</h3>
              {f.description && <p className="text-slate-400 text-sm mt-1">{f.description}</p>}
            </div>
            {f.status === 'open' && (
              <div className="flex gap-2 shrink-0">
                <button onClick={() => handleStatus(f.id, 'confirmed')}
                  className="text-xs bg-green-800 hover:bg-green-700 text-green-200 px-3 py-1 rounded">
                  Confirm
                </button>
                <button onClick={() => handleStatus(f.id, 'dismissed')}
                  className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1 rounded">
                  Dismiss
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
