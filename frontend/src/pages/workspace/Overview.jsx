import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getWorkspace } from '../../api/workspaces'
import { listDocuments } from '../../api/documents'
import { listEntities } from '../../api/entities'
import { listFindings } from '../../api/findings'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function Overview() {
  const { workspaceId } = useParams()
  const [workspace, setWorkspace] = useState(null)
  const [stats, setStats] = useState({ documents: 0, entities: 0, findings: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getWorkspace(workspaceId),
      listDocuments(workspaceId),
      listEntities(workspaceId),
      listFindings(workspaceId),
    ]).then(([ws, docs, ents, findings]) => {
      setWorkspace(ws.data)
      setStats({
        documents: docs.data.length,
        entities: ents.data.length,
        findings: findings.data.length,
      })
    }).finally(() => setLoading(false))
  }, [workspaceId])

  if (loading) return <LoadingSpinner />

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">{workspace?.name}</h1>
        {workspace?.subject_name && (
          <p className="text-slate-400 text-sm mt-1">Subject: {workspace.subject_name}</p>
        )}
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Documents', value: stats.documents, color: 'text-blue-400' },
          { label: 'Entities', value: stats.entities, color: 'text-purple-400' },
          { label: 'Findings', value: stats.findings, color: 'text-red-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-800 rounded-xl p-5 text-center">
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
            <p className="text-slate-400 text-sm mt-1">{label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
