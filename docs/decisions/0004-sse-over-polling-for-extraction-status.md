# ADR 0004 — SSE over polling for real-time extraction status

**Status:** Accepted  
**Date:** 2026-05-29

---

## Context

Document extraction runs as a background task after upload. The pipeline takes anywhere from a few seconds to a minute depending on document size and schema field count. The frontend needed a way to update the document list without requiring a page refresh.

Two options:

**Option A — Client polling**  
Frontend calls `GET /documents/{id}` every N seconds until `extraction_status` reaches a terminal value. Simple to implement, works everywhere, no persistent connection.

**Option B — Server-Sent Events (SSE)**  
Backend streams status updates as a persistent `text/event-stream` response. Frontend opens the connection once, receives events as they happen, closes when done.

A third consideration shaped the implementation regardless of which approach was chosen: the Anthropic API token. The SSE stream endpoint is behind JWT auth like every other endpoint. Native `EventSource` does not support custom headers — it sends a GET request with no way to attach `Authorization: Bearer <token>`. This would require either a query-parameter token (poor practice, tokens in logs) or a different auth mechanism entirely.

---

## Decision

SSE via `fetch + ReadableStream`, not native `EventSource`.

The backend exposes `GET /workspaces/{id}/documents/{doc_id}/status/stream` returning a FastAPI `StreamingResponse` with `media_type="text/event-stream"`. The generator polls the database every 2 seconds, yields one SSE event per poll, and closes on terminal status (`complete`, `failed`, `no_schema`, `needs_review`) or after a 5-minute hard timeout.

The frontend uses `fetch()` instead of `EventSource` to send the Bearer token as a header. A custom hook (`useExtractionStream`) reads the response body as a `ReadableStream`, decodes chunks, parses `data:` lines, and calls an `onUpdate` callback on each event. If the stream fails, the hook schedules a reconnect with exponential backoff (base 1s, doubles each attempt, cap 32s, max 5 retries).

---

## Consequences

**What gets easier:**

- The document list updates in real time without user action. Upload a document, watch the badge flip from `pending` to `complete` as the pipeline finishes.
- A toast fires automatically when extraction completes — the user doesn't need to be watching the list. If they've navigated to the document viewer, the notification finds them.
- The backend generator uses its own `SessionLocal` session (not the request-scoped dependency-injected session) so it can poll across the full 5-minute window without holding a connection to the HTTP layer open.

**What gets harder:**

- `fetch + ReadableStream` requires more code than `new EventSource(url)`. The reconnect logic (exponential backoff, cancellation on unmount, backoff timer cleanup) is non-trivial.
- Browser support for streaming `fetch` bodies is solid in modern browsers but required verification. The approach also assumes the browser can hold a persistent HTTP connection for up to 5 minutes without terminating it — this works in practice but is not guaranteed in all proxy configurations.
- Multiple pending documents in the same workspace open multiple parallel connections. At single-user scale this is acceptable; at higher concurrency, connection pressure would warrant switching to a workspace-level stream or WebSocket.

**What this rules out:**

- Polling. Not because polling is wrong — at the scale this platform targets, polling every 3 seconds would work fine. SSE was chosen because it's the correct mental model for the interaction: the server has something to tell the client, and the client should receive it when it's ready, not guess when to ask.

**Why `fetch` instead of `EventSource`:**

`EventSource` is the right API when auth is not a concern (public endpoints, cookie-based auth). It is the wrong API when the application uses Bearer tokens in headers. The `fetch + ReadableStream` approach is more code but produces the same result without putting the auth token in a URL query parameter.
