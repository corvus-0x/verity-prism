import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listWorkspaces, createWorkspace } from '../api/workspaces'
import AppShell from '../components/layout/AppShell'
import Badge from '../components/shared/Badge'
import LoadingSpinner from '../components/shared/LoadingSpinner'

const VERTICALS = [
  { value: 'general', label: 'General', description: 'Documents, search, AI — no vertical-specific tools' },
  { value: 'fraud', label: 'Fraud Investigation', description: 'Adds transactions, findings, leads' },
  { value: 'insurance', label: 'Insurance', description: 'Coming soon' },
]

function NewWorkspaceModal({ onClose, onCreate }) {
  const [name, setName] = useState('')
  const [vertical, setVertical] = useState('general')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    try {
      await onCreate({ name: name.trim(), vertical })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-md">
        <h2 className="text-white font-semibold text-lg mb-5">New Workspace</h2>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-slate-400 text-sm mb-1.5">Name</label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Smith Estate Review"
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm
                         text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1.5">Vertical</label>
            <div className="space-y-2">
              {VERTICALS.map(({ value, label, description }) => (
                <button
                  key={String(value)}
                  type="button"
                  onClick={() => setVertical(value)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg border text-sm transition-colors
                    ${vertical === value
                      ? 'border-blue-500 bg-blue-500/10 text-white'
                      : 'border-slate-600 bg-slate-700/50 text-slate-300 hover:border-slate-500'
                    }`}
                >
                  <span className="font-medium">{label}</span>
                  <span className="text-slate-500 ml-2 text-xs">{description}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 rounded-lg border border-slate-600 text-slate-400
                         hover:text-white hover:border-slate-500 text-sm transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || saving}
              className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50
                         text-white text-sm transition-colors"
            >
              {saving ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function WorkspacesHome() {
  const [workspaces, setWorkspaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    listWorkspaces()
      .then((res) => setWorkspaces(res.data))
      .finally(() => setLoading(false))
  }, [])

  const handleCreate = async ({ name, vertical }) => {
    const res = await createWorkspace({ name, vertical })
    navigate(`/workspaces/${res.data.id}`)
  }

  return (
    <AppShell>
      <div className="flex-1 p-8 max-w-4xl mx-auto w-full">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-white">Workspaces</h1>
          <button
            onClick={() => setShowModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm"
          >
            + New Workspace
          </button>
        </div>
        {loading ? <LoadingSpinner /> : (
          <div className="space-y-3">
            {workspaces.map((ws) => (
              <Link
                key={ws.id}
                to={`/workspaces/${ws.id}`}
                className="block bg-slate-800 border border-slate-700 hover:border-slate-500
                           rounded-xl p-5 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-white font-semibold">{ws.name}</h2>
                    {ws.subject_name && (
                      <p className="text-slate-400 text-sm mt-1">Subject: {ws.subject_name}</p>
                    )}
                    {ws.jurisdiction && (
                      <p className="text-slate-500 text-xs mt-0.5">{ws.jurisdiction}</p>
                    )}
                  </div>
                  <Badge label={ws.status} />
                </div>
              </Link>
            ))}
            {workspaces.length === 0 && (
              <p className="text-slate-400 text-center py-12">
                No workspaces yet. Create one to get started.
              </p>
            )}
          </div>
        )}
      </div>
      {showModal && (
        <NewWorkspaceModal
          onClose={() => setShowModal(false)}
          onCreate={handleCreate}
        />
      )}
    </AppShell>
  )
}
