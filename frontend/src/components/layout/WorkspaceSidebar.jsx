import { useState } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import { useWorkspace } from '../../context/WorkspaceContext'
import { uploadDocument } from '../../api/documents'
import { useToast } from '../../hooks/useToast'

const ENGINE_SECTIONS = [
  { path: '', label: 'Overview', end: true },
  { path: 'documents', label: 'Documents' },
  { path: 'sources', label: 'Sources' },
  { path: 'search', label: 'Search' },
  { path: 'entities', label: 'Entities' },
  { path: 'chat', label: 'AI Chat' },
  { path: 'review', label: 'Review' },
  { path: 'audit', label: 'Audit Log' },
]

const VERTICAL_SECTIONS = {
  fraud: [
    { path: 'transactions', label: 'Transactions' },
    { path: 'findings', label: 'Findings' },
    { path: 'leads', label: 'Leads' },
  ],
}

export default function WorkspaceSidebar() {
  const { workspaceId } = useParams()
  const workspace = useWorkspace()
  const { toast } = useToast()
  const [uploading, setUploading] = useState(false)
  const capSections = VERTICAL_SECTIONS[workspace?.vertical ?? 'general'] ?? []

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files)
    if (!files.length) return
    e.target.value = ''
    setUploading(true)
    for (const file of files) {
      try {
        await uploadDocument(workspaceId, file)
        toast.info('Uploaded', `${file.name} — extracting`)
      } catch {
        toast.error('Upload failed', file.name)
      }
    }
    setUploading(false)
  }

  const navClass = ({ isActive }) => isActive ? 'nav-link-active' : 'nav-link'

  return (
    <nav
      className="bg-slate-900 flex flex-col gap-0.5 w-full h-full py-3 px-2 overflow-y-auto"
      style={{ borderRight: '1px solid #1A2A3F' }}
    >
      {/* Upload */}
      <label
        className={`btn-primary w-full justify-center mb-3 text-xs ${uploading ? 'opacity-40 pointer-events-none' : ''}`}
        style={{ cursor: uploading ? 'not-allowed' : 'pointer' }}
      >
        <input
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.csv,.txt,.xml"
          onChange={handleUpload}
          disabled={uploading}
        />
        {uploading ? 'Uploading…' : '+ Upload'}
      </label>

      {/* Engine sections */}
      {ENGINE_SECTIONS.map(({ path, label, end }) => (
        <NavLink
          key={label}
          to={`/workspaces/${workspaceId}${path ? `/${path}` : ''}`}
          end={end}
          className={navClass}
        >
          {label}
        </NavLink>
      ))}

      {/* Vertical cap sections */}
      {capSections.length > 0 && (
        <>
          <div className="mt-3 mb-1 mx-1 pt-3" style={{ borderTop: '1px solid #1A2A3F' }}>
            <span
              className="text-xs font-medium uppercase tracking-widest"
              style={{ color: '#3D5570', letterSpacing: '0.14em' }}
            >
              {workspace?.vertical}
            </span>
          </div>
          {capSections.map(({ path, label }) => (
            <NavLink
              key={label}
              to={`/workspaces/${workspaceId}/${path}`}
              className={navClass}
            >
              {label}
            </NavLink>
          ))}
        </>
      )}
    </nav>
  )
}
