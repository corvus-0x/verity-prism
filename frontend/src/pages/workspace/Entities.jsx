import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listEntities } from '../../api/entities'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

const TYPES = ['person', 'organization', 'property', 'financial_account']

export default function Entities() {
  const { workspaceId } = useParams()
  const [entities, setEntities] = useState([])
  const [activeTab, setActiveTab] = useState('person')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listEntities(workspaceId).then((r) => setEntities(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const filtered = entities.filter((e) => e.type === activeTab)

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <div className="flex gap-2 mb-6">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-2 rounded-lg text-sm capitalize transition-colors ${
              activeTab === t ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            {t}s ({entities.filter((e) => e.type === t).length})
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState message={`No ${activeTab}s added yet.`} />
      ) : (
        <div className="space-y-3">
          {filtered.map((e) => (
            <div key={e.id} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-white font-medium">{e.name}</h3>
                <Badge label={e.status} />
              </div>
              {Object.keys(e.data || {}).length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {Object.entries(e.data).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-slate-500 text-xs">{k.replace(/_/g, ' ')}: </span>
                      <span className="text-slate-300 text-xs">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
