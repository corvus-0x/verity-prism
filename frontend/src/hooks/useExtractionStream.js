import { useEffect, useRef } from 'react'
import client from '../api/client'
import useAuthStore from '../store/auth'

const TERMINAL = new Set(['complete', 'failed', 'no_schema', 'needs_review'])
const API_BASE = client.defaults.baseURL || ''
const MAX_RETRIES = 5

export default function useExtractionStream(workspaceId, documentId, status, onUpdate) {
  const onUpdateRef = useRef(onUpdate)
  onUpdateRef.current = onUpdate

  useEffect(() => {
    if (status !== 'pending') return
    if (!workspaceId || !documentId) return

    const url = `${API_BASE}/workspaces/${workspaceId}/documents/${documentId}/status/stream`

    let cancelled = false
    let retries = 0
    let backoffTimer = null
    let reader = null

    async function stream() {
      try {
        const token = useAuthStore.getState().token
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) { scheduleRetry(); return }

        retries = 0
        reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const payload = JSON.parse(line.slice(6))
                onUpdateRef.current(documentId, payload)
                if (TERMINAL.has(payload.extraction_status)) {
                  cancelled = true
                  return
                }
              } catch {}
            }
          }
        }
      } catch (err) {
        if (!cancelled) scheduleRetry()
      }
    }

    function scheduleRetry() {
      if (cancelled || retries >= MAX_RETRIES) return
      const delay = Math.min(1000 * Math.pow(2, retries), 32000)
      retries++
      backoffTimer = setTimeout(() => { if (!cancelled) stream() }, delay)
    }

    stream()
    return () => {
      cancelled = true
      if (backoffTimer) clearTimeout(backoffTimer)
      reader?.cancel()
    }
  }, [workspaceId, documentId, status])
}
