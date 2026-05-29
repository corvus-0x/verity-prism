import { NavLink, useParams } from 'react-router-dom'
import { useWorkspace } from '../../context/WorkspaceContext'

const ENGINE_SECTIONS = [
  { path: '', label: 'Overview', end: true },
  { path: 'documents', label: 'Documents' },
  { path: 'search', label: 'Search' },
  { path: 'entities', label: 'Entities' },
  { path: 'chat', label: 'AI Chat' },
  { path: 'review', label: 'Review' },
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
  const capSections = VERTICAL_SECTIONS[workspace?.vertical ?? 'general'] ?? []
  const sections = [...ENGINE_SECTIONS, ...capSections]

  return (
    <nav className="w-48 bg-slate-900 border-r border-slate-800 p-3 flex flex-col gap-1 shrink-0">
      {sections.map(({ path, label, end }) => (
        <NavLink
          key={label}
          to={`/workspaces/${workspaceId}${path ? `/${path}` : ''}`}
          end={end}
          className={({ isActive }) =>
            `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors
             ${isActive
               ? 'bg-slate-700 text-white'
               : 'text-slate-400 hover:text-white hover:bg-slate-800'
             }`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
