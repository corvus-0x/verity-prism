# Tool-Use Chat Agent — Design Spec

**Date:** 2026-05-26
**Status:** Approved
**Scope:** Replace the single-call `ai_engine.chat()` with a native Anthropic tool-use agentic loop. Read-only. Extensible via vertical tool registry.

---

## 1. Architecture

The current `chat()` function in `backend/app/services/ai_engine.py` is a single Claude call with a static full-workspace context dump as the system prompt. This spec replaces it with an agentic loop using the Anthropic SDK's native tool use (`tool_use` / `tool_result` content blocks).

### What changes
- `ai_engine.chat()` — replaced with agentic loop (same function signature, same return type)
- `ai_engine.build_workspace_context()` — no longer the primary data source; replaced by tool calls. Retained in a lightweight form for system prompt metadata only.
- New file: `backend/app/services/agent_tools.py` — one function per tool, all read-only DB queries
- New file: `backend/app/services/agent_registry.py` — maps verticals to their tool lists

### What does not change
- Router (`/chat` endpoint) — same request/response shape
- Frontend — no changes required
- `AIMessage` persistence — same: only final user message and final assistant response are saved

---

## 2. Agentic Loop

```
POST /chat (workspace_id, conversation_id, message)
    ↓
ai_engine.chat()
    1. Build lightweight system prompt (workspace name, subject, vertical, behavioral instructions)
    2. Load conversation history (last 20 messages — user/assistant text only, no prior tool calls)
    3. Load tools = agent_registry.get_tools_for_vertical(vertical)
    ↓
Round loop (max 10 rounds):
    → call client.messages.create(model, system, messages, tools, max_tokens)
    → stop_reason == "end_turn"  → extract text → save to AIMessage → return
    → stop_reason == "tool_use"  →
          for each tool_use block in response:
              log tool name, params, timestamp
              result = agent_tools.execute(tool_name, workspace_id, db, params)
              log result size, latency
              collect as tool_result block
          append assistant message + all tool_result blocks to in-memory messages
          increment round counter → continue loop
    → round counter >= 10 → synthesis pass (see Section 4)
    ↓
Save final assistant response to AIMessage
Return response string to router
```

---

## 3. Tool Definitions

Six read-only tools. `workspace_id` is **never** a parameter Claude can pass — it is injected by the dispatcher. Every tool function signature is `(workspace_id, db, **params_from_claude)`.

### `search_documents`
**Description:** Search workspace documents by keyword and optionally filter by document type. Returns up to 10 matching documents with filename, type, and top matched fields.

**Parameters:**
- `query` (string, required) — keyword search string
- `doc_type` (string, optional) — filter to a specific document type (DEED, 990, UCC, etc.)

**Returns:** List of up to 10 documents: `{id, filename, doc_type, matched_fields: {field_name: value}}` — matched_fields capped at 5 fields per document.

---

### `get_entity`
**Description:** Look up a specific entity (person, LLC, organization) by name. Returns the entity record and all associated data fields.

**Parameters:**
- `name` (string, required) — entity name to look up (exact or partial match)

**Returns:** If one match: `{id, name, type, status, data: {...}}`. If multiple matches: list of up to 5 entities with `{id, name, type, status}` — no data fields. If no match: `null`.

---

### `query_extractions`
**Description:** Find documents where a specific extracted field matches a value. Use for precise field-level queries like "all deeds where grantor contains Smith" or "documents where consideration_amount is greater than 500000."

**Parameters:**
- `field_name` (string, required) — the extracted field name to filter on
- `operator` (string, required) — one of: `eq`, `contains`, `gt`, `lt`
- `value` (string, required) — value to compare against (always a string, even for numeric comparisons)

**Returns:** List of up to 50 documents matching the filter: `{document_id, filename, doc_type, field_name, field_value}`.

---

### `get_transactions`
**Description:** Filter workspace transactions by amount range and/or transaction type. Returns amount paid, appraised value, overpay percentage, date, and instrument number.

**Parameters:**
- `min_amount` (number, optional)
- `max_amount` (number, optional)
- `transaction_type` (string, optional)

**Returns:** List of matching transactions: `{id, transaction_type, amount_paid, appraised_value, overpay_pct, transaction_date, instrument_number, notes}`.

---

### `get_findings`
**Description:** List all findings in the workspace with title, severity, and status. Check this before making new observations to avoid duplicating what is already recorded.

**Parameters:** None.

**Returns:** List of findings: `{id, title, severity, status, description}`.

---

### `get_leads`
**Description:** List investigation leads filtered by status. Check this before suggesting new leads to avoid duplicating what is already being tracked.

**Parameters:**
- `status` (string, optional) — one of: `pending`, `in_progress`, `all`. Defaults to `pending`.

**Returns:** List of leads: `{id, question, status, source}`.

---

## 4. Error Handling

### Tool execution failure
Return a `tool_result` block with `is_error: true` and a plain English description of what failed. Do not raise. Claude sees the error and decides whether to try a different tool or answer from what it already has. No retries — empty or failed results are information.

### Max rounds hit (synthesis pass)
After 10 rounds, make one final Claude call with `tools=[]` (disabled). System prompt for this call:

> "You've gathered the following tool results. Provide your final answer to the user's question using only this data. No further tool calls are available."

The accumulated tool results from all prior rounds are included in the messages. This guarantees a coherent response regardless of how the loop terminated.

### Claude API error
Let the exception propagate to the router, which returns HTTP 500. No change from current behavior.

---

## 5. Constraints & Guarantees

### Workspace scoping (security)
`workspace_id` is never in any tool's JSON schema. Claude cannot request it as a parameter. The dispatcher always injects it from the authenticated request context. A tool can only return data belonging to the workspace it was called with.

### Tool result size limits
Without limits, 10 rounds of tool calls will overflow the context window. Hard ceilings:
- `search_documents` — ≤10 documents, ≤5 matched fields per document
- `query_extractions` — ≤50 rows
- `get_transactions` — ≤50 rows
- `get_findings` — no limit (findings lists are bounded by workspace size)
- `get_leads` — no limit (same)
- `get_entity` — single record, no limit

### Tool descriptions are a design artifact
The descriptions in Section 3 are the prompt surface inside the loop. They must be precise — Claude selects tools by description. Changes to descriptions require spec review, not just code review.

### System prompt behavioral instructions
The system prompt retains these instructions from the current implementation:
- Answer accurately from data only — do not speculate beyond what the tools return
- Be precise with numbers, dates, names, and document references
- When identifying something not yet investigated, end with: `"Next lead to consider: [question]"`
- Reference documents by filename, not by ID

### Ephemeral tool calls per turn (intentional)
Tool results are not persisted to `AIMessage`. Only the final user message and final assistant response are saved. Turn 2 of a conversation re-fetches data via tools — Claude does not carry what it learned from turn 1's tool calls into turn 2's tool resolution. This is a deliberate Phase 1 simplification.

---

## 6. Vertical Tool Registry

`agent_registry.py` owns a mapping of vertical names to their tool lists. The loop calls `get_tools_for_vertical(vertical)` before each session and receives the full tool set — core tools plus any vertical-specific additions.

```python
# Conceptual structure — implementation detail
CORE_TOOLS = [search_documents, get_entity, query_extractions,
              get_transactions, get_findings, get_leads]

VERTICAL_TOOLS = {
    "fraud":     CORE_TOOLS + [...],   # fraud-specific tools added here
    "insurance": CORE_TOOLS + [...],   # insurance-specific tools added here
    "general":   CORE_TOOLS,
}
```

Each vertical's additional tools follow the same pattern: defined in `agent_tools_<vertical>.py`, registered in `VERTICAL_TOOLS`. The core loop in `ai_engine.py` does not change when a new vertical is added.

---

## 7. File Structure

```
backend/app/services/
├── ai_engine.py          — agentic loop, synthesis pass, AIMessage persistence
├── agent_tools.py        — core tool implementations (one function per tool)
├── agent_registry.py     — vertical → tool list mapping, tool JSON schema builders
└── (future) agent_tools_fraud.py
    (future) agent_tools_insurance.py
```

---

## Out of Scope (Phase 1)

- Write tools (add_finding, add_lead) — Phase 2
- Persisting tool call chains to the database — covered by Observability spec (build #3)
- Turn-to-turn tool result memory — future consideration
- Streaming responses — future consideration
