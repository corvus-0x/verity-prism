import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listWorkspaces, createWorkspace } from '../api/workspaces'
import AppShell from '../components/layout/AppShell'
import Badge from '../components/shared/Badge'
import LoadingSpinner from '../components/shared/LoadingSpinner'

const VERTICALS = [
  { value: 'general', label: 'General', description: 'Documents, search, AI — no vertical-specific tools' },
  { value: 'fraud', label: 'Fraud Investigation', description: 'Adds transactions, findings, leads' },
  { value: 'insurance', label: 'Insurance', disabled: true, description: 'Coming soon' },
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
    <div
      className="fixed inset-0 flex items-center justify-center z-50 animate-fade-in"
      style={{ background: 'rgba(2,5,9,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-workspace-title"
    >
      <div
        className="w-full max-w-md rounded-xl p-6 animate-scale-in"
        style={{ background: '#0C1424', border: '1px solid #1A2A3F' }}
      >
        <h2 id="new-workspace-title" className="font-display text-slate-100 font-semibold text-base mb-5 tracking-wide">
          New Workspace
        </h2>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label
              className="block text-slate-400 font-medium uppercase mb-2"
              style={{ fontSize: '0.65rem', letterSpacing: '0.12em' }}
            >
              Name
            </label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Smith Estate Review"
              className="field-input text-sm"
            />
          </div>

          <div>
            <label
              className="block text-slate-400 font-medium uppercase mb-2"
              style={{ fontSize: '0.65rem', letterSpacing: '0.12em' }}
            >
              Vertical
            </label>
            <div className="space-y-2">
              {VERTICALS.map(({ value, label, description, disabled }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => !disabled && setVertical(value)}
                  disabled={disabled}
                  className={`disabled:cursor-not-allowed disabled:opacity-50 w-full text-left p-3 rounded-md border transition-colors
                    ${vertical === value
                      ? 'text-slate-100'
                      : 'text-slate-300 hover:text-slate-100'
                    }`}
                  style={vertical === value
                    ? { background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.25)' }
                    : { background: '#111E30', border: '1px solid #1A2A3F' }
                  }
                >
                  <span className="font-medium">{label}</span>
                  <span className="text-slate-400 ml-2 text-xs">{description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn-ghost flex-1">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || saving}
              className="btn-primary flex-1"
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
          <h1 className="font-display text-slate-100 font-semibold text-lg tracking-wide">
            Workspaces
          </h1>
          <button onClick={() => setShowModal(true)} className="btn-primary">
            + New Workspace
          </button>
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : (
          <div className="space-y-3">
            {workspaces.map((ws, i) => (
              <Link
                key={ws.id}
                to={`/workspaces/${ws.id}`}
                className="block surface-card p-5 animate-fade-up"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-slate-100 font-medium">{ws.name}</h2>
                    {ws.subject_name && (
                      <p className="text-slate-400 text-sm mt-0.5">Subject: {ws.subject_name}</p>
                    )}
                    {ws.jurisdiction && (
                      <p className="text-slate-400 text-xs mt-0.5">{ws.jurisdiction}</p>
                    )}
                  </div>
                  <Badge label={ws.status} />
                </div>
              </Link>
            ))}

            {workspaces.length === 0 && (
              <div className="text-center py-16">
                <p className="text-slate-400 text-sm">No workspaces yet.</p>
                <button
                  onClick={() => setShowModal(true)}
                  className="btn-primary mt-4"
                >
                  Create your first workspace
                </button>
              </div>
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
