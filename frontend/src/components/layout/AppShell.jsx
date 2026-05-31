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

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-3 flex items-center gap-4">
        <span className="text-white font-bold text-lg shrink-0 mr-2">Verity Prism</span>
        <div className="flex items-center gap-1 border-l border-slate-700 pl-4">
          <NavLink
            to="/workspaces"
            className={({ isActive }) =>
              `text-sm px-3 py-1.5 rounded shrink-0 transition-colors ${isActive ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'}`
            }
          >
            Workspaces
          </NavLink>
          <NavLink
            to="/schemas"
            className={({ isActive }) =>
              `text-sm px-3 py-1.5 rounded shrink-0 transition-colors ${isActive ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'}`
            }
          >
            Schemas
          </NavLink>
          <NavLink
            to="/observability"
            className={({ isActive }) =>
              `text-sm px-3 py-1.5 rounded shrink-0 transition-colors ${isActive ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'}`
            }
          >
            Observability
          </NavLink>
        </div>
        <form onSubmit={handleSearch} className="flex-1 max-w-2xl">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search in plain English — e.g. 'find all deeds where consideration was zero'"
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-sm
                       text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
        </form>
        <button
          onClick={() => { logout(); navigate('/login') }}
          className="text-slate-400 hover:text-white text-sm ml-auto shrink-0"
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
