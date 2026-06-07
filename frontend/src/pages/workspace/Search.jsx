import { useState, useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { search } from '../../api/search'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function Search() {
  const { workspaceId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) { setQuery(q); runSearch(q) }
  }, [])

  const runSearch = async (q) => {
    if (!q.trim()) return
    setLoading(true)
    try {
      const res = await search(workspaceId, q)
      setResults(res.data)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setSearchParams({ q: query })
    runSearch(query)
  }

  return (
    <div className="max-w-3xl">
      <form onSubmit={handleSubmit} className="flex gap-3 mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search in plain English — e.g. 'find all deeds where consideration was zero'"
          className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-3
                     text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
        />
        <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-3 rounded-lg">
          Search
        </button>
      </form>

      {loading && <LoadingSpinner />}

      {results && !loading && (
        <div>
          <p className="text-slate-400 text-sm mb-4">
            {results.result_count} result{results.result_count !== 1 ? 's' : ''} for "{results.query}"
          </p>
          <div className="space-y-3">
            {results.results.map((r) => (
              <div key={r.document_id} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-slate-500 text-xs bg-slate-700 px-2 py-0.5 rounded">
                    {r.detected_doc_type || 'Unknown'}
                  </span>
                  <p className="text-white text-sm font-mono">{r.filename}</p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(r.matched_fields || {}).map(([field, value]) => (
                    <div key={field} className="bg-slate-700 rounded p-2">
                      <p className="text-slate-400 text-xs">{field.replace(/_/g, ' ')}</p>
                      <p className="text-white text-sm mt-0.5">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {results.result_count === 0 && (
              <p className="text-slate-500 text-center py-8">No documents matched that search.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
