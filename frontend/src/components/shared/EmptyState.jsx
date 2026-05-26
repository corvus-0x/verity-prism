export default function EmptyState({ message, action, onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <p className="text-slate-400 mb-4">{message}</p>
      {action && (
        <button
          onClick={onAction}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm"
        >
          {action}
        </button>
      )}
    </div>
  )
}
