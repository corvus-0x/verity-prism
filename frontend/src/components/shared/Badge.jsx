const COLORS = {
  // severity
  critical: 'bg-red-900 text-red-300',
  high:     'bg-orange-900 text-orange-300',
  medium:   'bg-yellow-900 text-yellow-300',
  low:      'bg-slate-700 text-slate-300',
  // finding status
  open:      'bg-blue-900 text-blue-300',
  confirmed: 'bg-red-900 text-red-300',
  closed:    'bg-slate-700 text-slate-400',
  // extraction status
  complete:     'bg-green-900 text-green-400',
  pending:      'bg-slate-800 text-slate-500 border border-slate-700',
  needs_review: 'bg-orange-950 text-orange-400',
  no_schema:    'bg-indigo-950 text-indigo-400',
  failed:       'bg-red-950 text-red-400',
  // generic
  active: 'bg-green-900 text-green-300',
}

export default function Badge({ label }) {
  const key = label?.toLowerCase().replace(' ', '_')
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${COLORS[key] || 'bg-slate-700 text-slate-300'}`}>
      {label}
    </span>
  )
}
