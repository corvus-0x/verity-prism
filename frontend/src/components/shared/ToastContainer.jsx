const VARIANT_STYLES = {
  success: 'bg-green-950 border-l-4 border-green-500',
  error:   'bg-red-950 border-l-4 border-red-500',
  info:    'bg-blue-950 border-l-4 border-blue-500',
  warning: 'bg-orange-950 border-l-4 border-orange-500',
}
const ICON = { success: '✓', error: '✕', info: '◎', warning: '⚠' }
const ICON_COLOR = {
  success: 'text-green-400',
  error:   'text-red-400',
  info:    'text-blue-400',
  warning: 'text-orange-400',
}

export default function ToastContainer({ toasts, onDismiss }) {
  if (!toasts.length) return null
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="false"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-3 p-3 rounded-lg shadow-2xl ${VARIANT_STYLES[t.variant]}`}
        >
          <span className={`mt-0.5 text-sm font-bold flex-shrink-0 ${ICON_COLOR[t.variant]}`}>
            {ICON[t.variant]}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-medium">{t.title}</p>
            {t.message && <p className="text-slate-400 text-xs mt-0.5">{t.message}</p>}
          </div>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={() => onDismiss(t.id)}
            className="text-slate-500 hover:text-slate-300 text-lg leading-none flex-shrink-0"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
