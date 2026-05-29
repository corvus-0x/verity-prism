import { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import client from '../../api/client'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import { useToast } from '../../hooks/useToast'

const DOT_COLORS = {
  uploaded:               'bg-blue-400',
  extraction_corrected:   'bg-green-400',
  document_file_accessed: 'bg-purple-400',
  searched:               'bg-amber-400',
}

const ACTION_FILTERS = [
  { label: 'All',           match: null },
  { label: 'Uploads',       match: 'uploaded' },
  { label: 'Corrections',   match: 'extraction_corrected' },
  { label: 'Searches',      match: 'searched' },
  { label: 'File accesses', match: 'document_file_accessed' },
]

function dotColor(action) {
  return DOT_COLORS[action] || 'bg-slate-500'
}

function detailLine(entry) {
  const s = entry.after_state || {}
  if (entry.action === 'uploaded') {
    return [s.filename, s.doc_type, s.status].filter(Boolean).join(' · ')
  }
  if (entry.action === 'extraction_corrected') {
    return `${s.field_name || ''} corrected`
  }
  if (entry.action === 'searched') {
    return s.query ? `"${s.query}"` : ''
  }
  if (entry.action === 'document_file_accessed') {
    return entry.entity_id || ''
  }
  return entry.entity_type ? `${entry.entity_type} ${entry.entity_id || ''}` : ''
}

function formatTime(ts) {
  const d = new Date(ts)
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function AuditLog() {
  const { workspaceId } = useParams()
  const { toast } = useToast()
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [actionFilter, setActionFilter] = useState(null)

  useEffect(() => {
    setLoading(true)
    client
      .get(`/workspaces/${workspaceId}/audit-log?page=${page}&limit=50`)
      .then((r) => setData(r.data))
      .catch((err) => toast.error('Failed to load audit log', err?.message))
      .finally(() => setLoading(false))
  }, [workspaceId, page])

  const filtered = useMemo(() => {
    if (!data) return []
    let entries = data.entries
    if (actionFilter) {
      entries = entries.filter((e) => e.action === actionFilter)
    }
    if (search.trim()) {
      const q = search.toLowerCase()
      entries = entries.filter(
        (e) =>
          e.action.includes(q) ||
          (e.entity_type || '').includes(q) ||
          detailLine(e).toLowerCase().includes(q)
      )
    }
    return entries
  }, [data, search, actionFilter])

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-white text-lg font-semibold">Audit Log</h1>
        <p className="text-slate-500 text-sm mt-0.5">Every action on every document is tamper-proof</p>
      </div>

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="Search actions…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
        <select
          value={actionFilter || ''}
          onChange={(e) => setActionFilter(e.target.value || null)}
          className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
        >
          {ACTION_FILTERS.map((f) => (
            <option key={f.label} value={f.match || ''}>
              {f.label}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : (
        <>
          <div className="relative pl-5">
            <div className="absolute left-[7px] top-0 bottom-0 w-px bg-slate-800" />
            {filtered.length === 0 && (
              <p className="text-slate-500 text-sm pl-4">No entries match your filter.</p>
            )}
            {filtered.map((entry) => (
              <div key={entry.id} className="relative mb-5">
                <div className={`absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-slate-900 ${dotColor(entry.action)}`} />
                <div className="pl-4">
                  <p className="text-slate-500 text-xs">{formatTime(entry.timestamp)}</p>
                  <p className="text-white text-sm font-medium mt-0.5">{entry.action}</p>
                  <p className="text-slate-400 text-xs mt-0.5">{detailLine(entry)}</p>
                  {entry.user_id && (
                    <p className="text-slate-600 text-xs mt-0.5">{entry.user_id}</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {data && data.pages > 1 && (
            <div className="flex items-center justify-between mt-8 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-xs bg-slate-800 border border-slate-700 text-slate-300 rounded disabled:opacity-40"
              >
                ← Previous
              </button>
              <span className="text-slate-500 text-xs">
                Page {data.page} of {data.pages}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
                className="px-3 py-1.5 text-xs bg-slate-800 border border-slate-700 text-slate-300 rounded disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
