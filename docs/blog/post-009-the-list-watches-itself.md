# The List Watches Itself

*By Corvus | From Case to Code*

---

Upload a document. The badge says `pending`. Nothing else happens until you refresh.

That was the state of the platform after Phase 2A. The extraction pipeline was running correctly — hashing the file, running OCR, detecting the document type, pulling fields through Claude, scoring confidence, flagging low-confidence fields for review. The work was happening. The interface didn't know about it.

The gap between what the system was doing and what you could see was a navigational problem. The pipeline runs in a background task after the HTTP response is sent — that's by design, so the upload returns immediately instead of waiting 30 seconds for extraction to finish. But it meant the frontend had no connection to what was happening on the backend. You'd upload a deed, navigate somewhere else, come back, and refresh to find out if it worked. The engine was processing documents continuously. The interface was a snapshot from whenever you last loaded the page.

---

The fix is a stream. One endpoint: `GET /workspaces/{id}/documents/{doc_id}/status/stream`. The backend opens a streaming response, polls the database every two seconds, and pushes one Server-Sent Event per poll. When the extraction status reaches a terminal state — `complete`, `failed`, `no_schema`, `needs_review` — the stream closes. Hard timeout at five minutes so nothing hangs indefinitely.

The frontend opens a fetch connection to that endpoint for each pending document. Not `EventSource`, which is the standard API for server-sent events — because `EventSource` doesn't support custom headers, and the platform uses JWT Bearer tokens for authentication. Putting the token in a URL query parameter would put it in every access log that touches the request. The `fetch + ReadableStream` approach is more code but the token stays in a header where it belongs.

Each status update calls back into the document list. When the pipeline finishes, the badge flips in place — `pending` goes green, or orange for `needs_review`, or red for `failed`. A toast fires. If you're looking at the document viewer when it happens, the notification finds you anyway.

---

The status badges are new too. Before this build, the document list showed a filename and a document type. Whether the extraction had succeeded or failed, whether the document needed review — none of that was visible without opening the document. The badge puts it on the card: five states, five colors. `pending` is gray and muted. `complete` is green. `needs_review` is orange. `no_schema` is indigo. `failed` is red. Not decorative — each color is a different thing that needs a different response from the investigator.

The context menu is new. Three dots in the corner of each card. Download CSV, download JSON — the extracted fields for that document, every field at its latest attempt, ready to take somewhere else. A workspace-level export downloads all extractions across all documents in one flat file. The system can process documents. The data can leave.

---

The audit log UI surfaces something that's been in the database since the beginning. The `audit_log` table has a PostgreSQL trigger that blocks `UPDATE` and `DELETE` at the database level — not at the application level, at the database level, which means even a bug in the application code can't corrupt it. Every upload, every search, every file access, every extraction correction is a permanent record.

Until Phase 2C, that table had no surface. It existed, it was being written to, and the only way to read it was a direct database query. The audit log page is a timeline — colored dots by action type, search, filter by action category, paginated at fifty entries per page. The subtitle reads: "Every action on every document is tamper-proof."

That matters for an investigation tool in a specific way. The platform isn't just organizing documents. It's building a record that might eventually support a referral to a regulatory body. When you hand that referral to the Ohio AG or the IRS, the question you have to be able to answer isn't just what the documents say — it's what you did with them. The audit log answers that question. You can show every query, every correction, every time a file was opened. The trigger means you can also show that the record can't have been altered after the fact.

---

85 tests. The backend gained the streaming status endpoint, four export endpoints, and a paginated audit log endpoint. The frontend gained the toast system, the status badges, the document context menu, the real-time stream hook, and the audit log timeline page.

The build also revealed a pre-existing CI gap: the test suite includes extraction evaluation tests that call the real Claude API. Those tests had never run in CI because the `ANTHROPIC_API_KEY` wasn't available — they passed locally and were invisible to automation. The CI workflow now excludes the `evals/` directory. They run locally against real documents, which is the right place for them.

Phase 2C closes the gap between what the engine does and what the interface shows. The next build picks up the data connectors — public sources that feed directly into the pipeline without a manual upload.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Follow along: `-corvus` on Hashnode.*
