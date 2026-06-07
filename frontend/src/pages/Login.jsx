import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import useAuthStore from '../store/auth'

function PrismMark({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polygon
        points="20,4 36,34 4,34"
        stroke="#DC2626"
        strokeWidth="1.5"
        strokeLinejoin="round"
        opacity="0.85"
      />
      {/* Refraction lines — suggest light splitting */}
      <line x1="20" y1="4" x2="28.5" y2="34" stroke="#DC2626" strokeWidth="0.75" opacity="0.45" />
      <line x1="20" y1="4" x2="24"   y2="34" stroke="#EF4444" strokeWidth="0.5"  opacity="0.25" />
    </svg>
  )
}

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setUser = useAuthStore((s) => s.setUser)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await login(email, password)
      setUser(res.data.user)
      navigate('/workspaces')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 bg-precision-grid flex items-center justify-center px-4 relative">
      {/* Ambient glow behind the form */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 700px 500px at 50% 46%, rgba(220,38,38,0.04) 0%, transparent 70%)',
        }}
      />

      <div className="relative w-full max-w-sm animate-fade-up">
        {/* Brand */}
        <div className="flex flex-col items-center mb-10">
          <PrismMark />
          <h1
            className="mt-5 font-display font-bold text-slate-100 uppercase"
            style={{ fontSize: '1.35rem', letterSpacing: '0.22em' }}
          >
            Verity Prism
          </h1>
          <p
            className="mt-1.5 text-slate-400 uppercase"
            style={{ fontSize: '0.65rem', letterSpacing: '0.2em' }}
          >
            Intelligent Document Processing
          </p>
        </div>

        {/* Form card */}
        <div
          className="rounded-xl p-8"
          style={{ background: '#0C1424', border: '1px solid #1A2A3F' }}
        >
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="block text-slate-400 font-medium uppercase mb-2"
                style={{ fontSize: '0.65rem', letterSpacing: '0.12em' }}
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@agency.gov"
                className="field-input"
                required
                autoFocus
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-slate-400 font-medium uppercase mb-2"
                style={{ fontSize: '0.65rem', letterSpacing: '0.12em' }}
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="field-input"
                required
              />
            </div>

            {error && (
              <p className="text-red-400 text-xs bg-red-950/50 border border-red-900/50 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full mt-1"
            >
              {loading ? 'Authenticating…' : 'Sign In'}
            </button>
          </form>
        </div>

        {/* Footer label */}
        <p
          className="text-center mt-5 text-slate-400"
          style={{ fontSize: '0.6rem', letterSpacing: '0.1em' }}
        >
          Secure access — all actions are audit-logged
        </p>
      </div>
    </div>
  )
}
