const COLORS = {
  // severity
  critical:     'bg-red-950/80 text-red-400 ring-1 ring-red-900/60',
  high:         'bg-orange-950/80 text-orange-400 ring-1 ring-orange-900/60',
  medium:       'bg-yellow-950/80 text-yellow-500 ring-1 ring-yellow-900/60',
  low:          'bg-slate-700/60 text-slate-300 ring-1 ring-slate-600/60',
  // finding status
  open:         'bg-blue-950/80 text-blue-400 ring-1 ring-blue-900/60',
  confirmed:    'bg-red-950/80 text-red-400 ring-1 ring-red-900/60',
  closed:       'bg-slate-700/40 text-slate-400 ring-1 ring-slate-600/40',
  // extraction status
  complete:     'bg-emerald-950/80 text-emerald-400 ring-1 ring-emerald-900/60',
  pending:      'bg-slate-700/40 text-slate-400 ring-1 ring-slate-600/40',
  needs_review: 'bg-amber-950/80 text-amber-400 ring-1 ring-amber-900/60',
  no_schema:    'bg-indigo-950/80 text-indigo-400 ring-1 ring-indigo-900/60',
  failed:       'bg-red-950/80 text-red-400 ring-1 ring-red-900/60',
  // generic
  active:       'bg-emerald-950/80 text-emerald-400 ring-1 ring-emerald-900/60',
}

export default function Badge({ label }) {
  const key = label?.toLowerCase().replaceAll(' ', '_')
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${COLORS[key] || 'bg-slate-700/60 text-slate-300 ring-1 ring-slate-600/60'}`}>
      {label}
    </span>
  )
}
