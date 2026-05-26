const colors = {
  critical: 'bg-red-900 text-red-300',
  high: 'bg-orange-900 text-orange-300',
  medium: 'bg-yellow-900 text-yellow-300',
  low: 'bg-slate-700 text-slate-300',
  active: 'bg-green-900 text-green-300',
  open: 'bg-blue-900 text-blue-300',
  confirmed: 'bg-red-900 text-red-300',
  pending: 'bg-slate-700 text-slate-300',
  complete: 'bg-green-900 text-green-300',
  closed: 'bg-slate-700 text-slate-400',
}

export default function Badge({ label }) {
  const key = label?.toLowerCase()
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[key] || 'bg-slate-700 text-slate-300'}`}>
      {label}
    </span>
  )
}
