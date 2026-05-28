import { Link } from 'react-router-dom'
import Badge from '../shared/Badge'

export default function DocumentList({ documents, selectedId, workspaceId }) {
  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <Link
          key={doc.id}
          to={`/workspaces/${workspaceId}/documents/${doc.id}`}
          className={`block p-3 rounded-lg border transition-colors ${
            selectedId === doc.id
              ? 'border-blue-500 bg-slate-800'
              : 'border-slate-700 bg-slate-800 hover:border-slate-500'
          }`}
        >
          <p className="text-white text-xs font-mono truncate">{doc.filename}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-slate-500 text-xs">{doc.detected_doc_type || 'Unknown'}</span>
            <Badge label={doc.extraction_status} />
          </div>
        </Link>
      ))}
    </div>
  )
}
