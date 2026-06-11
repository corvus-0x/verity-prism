import { useState } from 'react'
import { useNavigate, useParams, NavLink } from 'react-router-dom'
import useAuthStore from '../../store/auth'

export default function AppShell({ children }) {
  const [query, setQuery] = useState('')
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const { workspaceId } = useParams()

  const handleSearch = (e) => {
    e.preventDefault()
    if (!query.trim() || !workspaceId) return
    navigate(`/workspaces/${workspaceId}/search?q=${encodeURIComponent(query)}`)
  }

  const navLinkClass = ({ isActive }) =>
    `relative text-sm px-3 py-1.5 rounded transition-all duration-150 shrink-0
     ${isActive
       ? 'text-red-400 bg-red-400/5'
       : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]'
     }`

  return (
    <div className="min-h-screen bg-mesh flex flex-col">
      <header
        className="px-5 py-0 flex items-center gap-4 shrink-0 backdrop-blur-md bg-slate-900/60 z-10"
        style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.06)', height: '52px' }}
      >
        {/* Wordmark */}
        <span
          className="font-display font-bold text-slate-100 shrink-0 tracking-widest uppercase text-sm"
          style={{ letterSpacing: '0.18em' }}
        >
          Verity Prism
        </span>

        {/* Nav links */}
        <div className="flex items-center gap-0.5 border-l border-slate-600 pl-4">
          <NavLink to="/workspaces" className={navLinkClass}>Workspaces</NavLink>
          <NavLink to="/schemas"    className={navLinkClass}>Schemas</NavLink>
          <NavLink to="/observability" className={navLinkClass}>Observability</NavLink>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-xl">
          <input
            type="text"
            aria-label="Search workspace documents in plain English"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search in plain English — e.g. 'find all deeds where consideration was zero'"
            className="field-input py-1.5 text-xs"
          />
        </form>

        {/* Sign out */}
        <button
          onClick={() => { logout(); navigate('/login') }}
          className="text-slate-400 hover:text-slate-200 text-xs ml-auto shrink-0
                     transition-colors duration-150 px-2 py-1 rounded hover:bg-white/[0.03]"
        >
          Sign out
        </button>
      </header>

      <main className="flex-1 flex">
        {children}
      </main>
    </div>
  )
}
