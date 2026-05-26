import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listWorkspaces, createWorkspace } from '../api/workspaces'
import AppShell from '../components/layout/AppShell'
import Badge from '../components/shared/Badge'
import LoadingSpinner from '../components/shared/LoadingSpinner'

export default function WorkspacesHome() {
  const [workspaces, setWorkspaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    listWorkspaces()
      .then((res) => setWorkspaces(res.data))
      .finally(() => setLoading(false))
  }, [])

  const handleCreate = async () => {
    const name = prompt('Workspace name:')
    if (!name) return
    setCreating(true)
    try {
      const res = await createWorkspace({ name, vertical: 'fraud' })
      navigate(`/workspaces/${res.data.id}`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <AppShell>
      <div className="flex-1 p-8 max-w-4xl mx-auto w-full">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-white">Workspaces</h1>
          <button
            onClick={handleCreate}
            disabled={creating}
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
    </AppShell>
  )
}
