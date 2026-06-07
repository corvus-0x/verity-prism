import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listLeads, updateLead } from '../../api/leads'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

const COLUMNS = [
  { status: 'in_progress', label: 'In Progress' },
  { status: 'pending', label: 'Pending' },
  { status: 'complete', label: 'Complete' },
  { status: 'dead_end', label: 'Dead End' },
]

export default function Leads() {
  const { workspaceId } = useParams()
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listLeads(workspaceId).then((r) => setLeads(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const handleStatus = async (id, status) => {
    const res = await updateLead(workspaceId, id, { status })
    setLeads((prev) => prev.map((l) => l.id === id ? res.data : l))
  }

  if (loading) return <LoadingSpinner />
  if (!leads.length) return <EmptyState message="No investigation leads yet." />

  return (
    <div className="space-y-6">
      {COLUMNS.map(({ status, label }) => {
        const group = leads.filter((l) => l.status === status)
        if (!group.length) return null
        return (
          <div key={status}>
            <h3 className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-3">
              {label} ({group.length})
            </h3>
            <div className="space-y-2">
              {group.map((l) => (
                <div key={l.id} className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-white text-sm">{l.question}</p>
                      {l.source && <p className="text-slate-500 text-xs mt-1">Source: {l.source}</p>}
                      {l.result_summary && <p className="text-slate-300 text-xs mt-2 italic">{l.result_summary}</p>}
                    </div>
                    {status === 'pending' && (
                      <button onClick={() => handleStatus(l.id, 'in_progress')}
                        className="text-xs bg-blue-800 hover:bg-blue-700 text-blue-200 px-3 py-1 rounded shrink-0">
                        Start
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
