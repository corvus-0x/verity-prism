import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import {
  listConversations, createConversation,
  listMessages, sendMessage
} from '../../api/ai'
import ChatMessage from '../../components/ai/ChatMessage'
import ChatInput from '../../components/ai/ChatInput'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import { useToast } from '../../hooks/useToast'
import SuggestSourceCard from '../../components/sources/SuggestSourceCard'

function parseSuggestion(content) {
  if (typeof content !== 'string') return null
  try {
    const parsed = JSON.parse(content)
    if (parsed?.action === 'suggest_source') return parsed
  } catch { /* not JSON */ }
  return null
}

export default function AIChat() {
  const { workspaceId } = useParams()
  const { toast } = useToast()
  const [conversations, setConversations] = useState([])
  const [activeConv, setActiveConv] = useState(null)
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const bottomRef = useRef(null)

  useEffect(() => {
    listConversations(workspaceId).then((r) => {
      setConversations(r.data)
      if (r.data.length > 0) loadConversation(r.data[0])
    }).finally(() => setLoading(false))
  }, [workspaceId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadConversation = async (conv) => {
    setActiveConv(conv)
    const res = await listMessages(workspaceId, conv.id)
    setMessages(res.data)
  }

  const handleNew = async () => {
    const res = await createConversation(workspaceId)
    setConversations((prev) => [res.data, ...prev])
    setActiveConv(res.data)
    setMessages([])
  }

  const handleSend = async (content) => {
    if (!activeConv) return
    const tempMsg = { id: 'temp', role: 'user', content }
    setMessages((prev) => [...prev, tempMsg])
    setSending(true)
    try {
      await sendMessage(workspaceId, activeConv.id, content)
      const msgs = await listMessages(workspaceId, activeConv.id)
      setMessages(msgs.data)
      if (!activeConv.title) {
        const convs = await listConversations(workspaceId)
        setConversations(convs.data)
        const updated = convs.data.find((c) => c.id === activeConv.id)
        if (updated) setActiveConv(updated)
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== 'temp'))
      toast.error('Send failed', 'Your message could not be delivered. Try again.')
    } finally {
      setSending(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      <div className="w-56 shrink-0 space-y-2">
        <button
          onClick={handleNew}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm py-2 rounded-lg"
        >
          + New Conversation
        </button>
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => loadConversation(c)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors ${
              activeConv?.id === c.id
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            {c.title || 'New conversation'}
          </button>
        ))}
      </div>

      <div className="flex-1 flex flex-col bg-slate-800 rounded-xl overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="text-slate-500 text-sm text-center mt-8">
              Ask a question about this workspace. Claude has access to all entities,
              transactions, documents, and findings.
            </p>
          )}
          {messages.map((m) => {
            const suggestion = m.role === 'assistant' ? parseSuggestion(m.content) : null
            if (suggestion) {
              return (
                <SuggestSourceCard
                  key={m.id}
                  workspaceId={workspaceId}
                  suggestion={suggestion}
                  onDismiss={() => setMessages((prev) => prev.filter((msg) => msg.id !== m.id))}
                />
              )
            }
            return <ChatMessage key={m.id} role={m.role} content={m.content} />
          })}
          {sending && (
            <div className="flex justify-start mb-4">
              <div className="bg-slate-700 rounded-xl px-4 py-3 text-slate-400 text-sm">
                Thinking...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <ChatInput onSend={handleSend} disabled={sending || !activeConv} />
      </div>
    </div>
  )
}
