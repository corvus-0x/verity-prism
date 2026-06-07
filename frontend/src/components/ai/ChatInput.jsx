import { useState } from 'react'

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!value.trim() || disabled) return
    onSend(value)
    setValue('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 p-4 border-t border-slate-700">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about this workspace... (Enter to send, Shift+Enter for new line)"
        rows={2}
        disabled={disabled}
        className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white
                   placeholder-slate-400 focus:outline-none focus:border-blue-500 resize-none text-sm"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4
                   rounded-lg self-end py-2 text-sm"
      >
        Send
      </button>
    </form>
  )
}
