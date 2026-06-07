import { useEffect, useRef, useCallback } from 'react'

const TERMINAL = new Set(['complete', 'failed', 'no_schema', 'needs_review'])
const MAX_CONCURRENT = 3

/**
 * Pools SSE connections for all pending documents in a workspace.
 * Opens at most MAX_CONCURRENT connections at once; queues the rest and
 * promotes queued docs as slots free when connections reach terminal status.
 *
 * @param {string} workspaceId
 * @param {Function} onUpdate - called as onUpdate(documentId, payload) on each SSE message
 * @returns {{ trackDoc: (docId: string) => void }}
 */
export function useWorkspaceExtractionStream(workspaceId, onUpdate) {
  const poolRef = useRef(null)
  const onUpdateRef = useRef(onUpdate)
  onUpdateRef.current = onUpdate

  useEffect(() => {
    const queue = []
    const active = new Map()
    let destroyed = false

    function startNext() {
      while (!destroyed && active.size < MAX_CONCURRENT && queue.length > 0) {
        openStream(queue.shift())
      }
    }

    function openStream(docId) {
      const url = `/api/workspaces/${workspaceId}/documents/${docId}/status/stream`
      const es = new EventSource(url)
      active.set(docId, es)

      es.onmessage = (event) => {
        if (destroyed) { es.close(); return }
        try {
          const payload = JSON.parse(event.data)
          onUpdateRef.current(docId, payload)
          if (TERMINAL.has(payload.extraction_status)) {
            es.close()
            active.delete(docId)
            startNext()
          }
        } catch {}
      }

      es.onerror = () => {
        if (destroyed) { es.close(); return }
        es.close()
        active.delete(docId)
        startNext()
      }
    }

    poolRef.current = {
      trackDoc(docId) {
        if (!destroyed) {
          queue.push(docId)
          startNext()
        }
      },
    }

    return () => {
      destroyed = true
      for (const es of active.values()) es.close()
      active.clear()
      poolRef.current = null
    }
  }, [workspaceId])

  const trackDoc = useCallback((docId) => {
    poolRef.current?.trackDoc(docId)
  }, [])

  return { trackDoc }
}
