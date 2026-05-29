import { useEffect, useRef, useCallback } from "react";

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 32000;
const MAX_RETRIES = 5;

const TERMINAL_STATUSES = new Set(["complete", "failed", "no_schema", "needs_review"]);

/**
 * Manages an SSE connection to /workspaces/{workspaceId}/documents/{documentId}/status/stream.
 * Retries with exponential backoff on transient errors; stops on terminal status or unmount.
 *
 * @param {Object} params
 * @param {string} params.workspaceId
 * @param {string} params.documentId
 * @param {string} params.initialStatus - current extraction_status from local state
 * @param {Function} params.onStatusUpdate - called with the parsed SSE payload on each message
 * @param {Function} params.onStreamStateChange - called with "connecting"|"connected"|"disconnected"|"failed"
 * @param {Function} params.onFinalFailure - called when all retries are exhausted without terminal status
 */
export function useExtractionStream({
  workspaceId,
  documentId,
  initialStatus,
  onStatusUpdate,
  onStreamStateChange,
  onFinalFailure,
}) {
  const esRef = useRef(null);
  const timerRef = useRef(null);
  const retryCountRef = useRef(0);
  const unmountedRef = useRef(false);
  const terminalRef = useRef(TERMINAL_STATUSES.has(initialStatus));

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (unmountedRef.current || terminalRef.current) return;

    cleanup();

    onStreamStateChange?.("connecting");

    const url = `/api/workspaces/${workspaceId}/documents/${documentId}/status/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      if (unmountedRef.current) { es.close(); return; }
      retryCountRef.current = 0;
      onStreamStateChange?.("connected");
    };

    es.onmessage = (event) => {
      if (unmountedRef.current) { es.close(); return; }

      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }

      onStatusUpdate?.(payload);

      if (TERMINAL_STATUSES.has(payload.extraction_status)) {
        terminalRef.current = true;
        onStreamStateChange?.("disconnected");
        cleanup();
      }
    };

    es.onerror = () => {
      if (unmountedRef.current || terminalRef.current) {
        cleanup();
        return;
      }

      es.close();
      esRef.current = null;
      onStreamStateChange?.("disconnected");

      if (retryCountRef.current >= MAX_RETRIES) {
        onStreamStateChange?.("failed");
        onFinalFailure?.();
        return;
      }

      const delay = Math.min(BASE_DELAY_MS * 2 ** retryCountRef.current, MAX_DELAY_MS);
      retryCountRef.current += 1;

      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        connect();
      }, delay);
    };
  }, [workspaceId, documentId, onStatusUpdate, onStreamStateChange, onFinalFailure, cleanup]);

  useEffect(() => {
    if (TERMINAL_STATUSES.has(initialStatus)) return;

    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      cleanup();
    };
    // connect is stable (useCallback with stable deps); initialStatus intentionally excluded
    // — we only start the stream once on mount, not on every status change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, documentId]);
}
