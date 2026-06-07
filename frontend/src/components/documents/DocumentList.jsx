import { Link } from 'react-router-dom'
import Badge from '../shared/Badge'

// Parse YYYY-MM-DD_DOC-TYPE_ENTITY_DESCRIPTION.ext into display parts.
// Returns null if the filename doesn't match the standardized format.
function parseFilename(filename) {
  const base = filename.replace(/\.[^.]+$/, '')
  const parts = base.split('_')
  if (parts.length < 3) return null

  const date = parts[0]
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) && date !== 'UNKNOWN-DATE') return null

  const docType = parts[1]
  const entity = parts[2]
  const description = parts.slice(3).join(' ').replace(/-/g, ' ')

  let displayDate = date
  if (date !== 'UNKNOWN-DATE') {
    const d = new Date(date + 'T00:00:00')
    displayDate = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  return { docType, entity, description, displayDate }
}

export default function DocumentList({ documents, selectedId, workspaceId, renderActions }) {
  if (documents.length === 0) {
    return (
      <p className="text-slate-500 text-xs text-center py-6">
        No documents yet. Upload one to get started.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div key={doc.id} className="relative group">
          <Link
            to={`/workspaces/${workspaceId}/documents/${doc.id}`}
            className={`block p-3 rounded-lg border transition-all duration-150 ${selectedId === doc.id
                ? 'bg-slate-800'
                : 'bg-slate-800 hover:border-slate-500'
              }`}
            style={selectedId === doc.id
              ? { borderColor: '#DC2626' }
              : { borderColor: '#1A2A3F' }
            }
          >
            {(() => {
              const parsed = parseFilename(doc.filename)
              if (parsed) {
                return (
                  <>
                    <div className="flex items-center justify-between pr-6 min-w-0">
                      <span className="text-red-400 text-[10px] font-semibold uppercase tracking-wider shrink-0">
                        {parsed.docType}
                      </span>
                      <span className="text-slate-500 text-[10px] shrink-0 ml-2">
                        {parsed.displayDate}
                      </span>
                    </div>
                    <p className="text-slate-100 text-xs font-medium truncate leading-snug mt-0.5">
                      {parsed.entity.replace(/-/g, ' ')}
                    </p>
                    {parsed.description && (
                      <p className="text-slate-500 text-[10px] truncate leading-snug">
                        {parsed.description}
                      </p>
                    )}
                  </>
                )
              }
              // Fallback for non-standardized filenames
              return (
                <p className="text-slate-100 text-xs font-mono truncate pr-6 leading-snug">
                  {doc.filename}
                </p>
              )
            })()}
            <div className="flex items-center gap-2 mt-1.5 min-w-0">
              <span className="shrink-0">
                <Badge label={doc.extraction_status} />
              </span>
              {doc.source_type && doc.source_type !== 'upload' && (
                <span className="shrink-0 text-[9px] bg-sky-900 text-sky-300 px-1.5 py-0.5 rounded font-semibold">
                  {doc.source_type.toUpperCase()}
                </span>
              )}
            </div>
          </Link>
          {renderActions && (
            <div className="absolute top-2 right-2">
              {renderActions(doc)}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
