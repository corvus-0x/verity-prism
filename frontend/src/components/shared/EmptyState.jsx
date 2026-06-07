export default function EmptyState({ message, action, onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <p className="text-slate-400 text-sm mb-4">{message}</p>
      {action && (
        <button type="button" onClick={onAction} className="btn-primary">
          {action}
        </button>
      )}
    </div>
  )
}
