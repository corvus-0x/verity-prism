# Phase 2F Plan 3 — Sources UI + Digital Viewer + AI Suggestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the connector backend a home in the UI — a Sources page that works like a search engine (search → pick → select → pull), a digital document viewer for sourced files with no PDF, and an AI suggestion path where Claude recommends a source and the operator pulls it.

**Architecture:** A new `Sources` workspace page drives the three-phase connector flow against Plan 2's API. The DocumentViewer's left pane becomes a pluggable renderer: PDF as today, or a schema-driven `DigitalDocumentRenderer` for structured docs, selected via a renderer registry + per-workspace render-mode preference. One new read-only agent tool, `suggest_source`, returns a structured suggestion the chat renders as an action card that deep-links into Sources.

**Tech Stack:** React + Vite, Vitest + React Testing Library (frontend). Python/FastAPI/pytest for the `suggest_source` tool. Tailwind (slate theme, sky-600 accents — match existing components).

**Spec:** `docs/superpowers/specs/2026-05-31-phase2f-connectors-design.md` (Parts D, E, F)

**Dependencies:** **Plan 2 must be complete** (connector API + provenance). Plan 1 is independent of this.

**Key existing patterns to follow:**
- `frontend/src/components/layout/WorkspaceSidebar.jsx` — `VERTICAL_SECTIONS`; engine items array. Add "Sources" here.
- `frontend/src/pages/workspace/ExtractionReview.jsx` — page + polling patterns.
- `frontend/src/pages/workspace/DocumentViewer.jsx` — split-pane shell; left PDF pane to make pluggable.
- `frontend/src/api/schemas.js`, `documents.js` — API client style (axios, `withCredentials`).
- `frontend/src/hooks/useToast.jsx` — toasts for errors.
- `frontend/src/pages/WorkspacesHome.jsx` — workspace creation modal (add render-mode toggle).
- Backend: `app/services/agent_tools.py`, `app/services/agent_registry.py` — add `suggest_source`.

**Run frontend tests:**
```bash
cd frontend && npm run test
```

---

## File Structure

**Create — frontend:**
- `frontend/src/api/connectors.js` — API client for connector endpoints
- `frontend/src/pages/workspace/Sources.jsx` — the Sources page
- `frontend/src/components/documents/DigitalDocumentRenderer.jsx` — schema-driven dark-theme renderer
- `frontend/src/components/documents/rendererRegistry.js` — renderer selection
- `frontend/src/components/sources/SuggestSourceCard.jsx` — chat action card
- tests: `frontend/src/__tests__/test_sources.jsx`, `test_digital_renderer.jsx`

**Modify — frontend:**
- `frontend/src/components/layout/WorkspaceSidebar.jsx` — Sources nav item
- `frontend/src/pages/workspace/DocumentViewer.jsx` — pluggable left renderer
- `frontend/src/pages/workspace/AIChat.jsx` — render `suggest_source` action card
- `frontend/src/pages/WorkspacesHome.jsx` — render-mode toggle in create modal
- `frontend/src/components/documents/DocumentList.jsx` — source badge
- router config (wherever workspace routes are declared) — add `.../sources`

**Modify — backend:**
- `backend/app/services/agent_tools.py` — `suggest_source` function
- `backend/app/services/agent_registry.py` — register the tool schema
- `backend/app/models/workspace.py` + migration — `document_render_mode` column
- `backend/app/schemas/workspace.py` — expose/accept `document_render_mode`

---

## Task 1: Workspace render-mode column

**Files:**
- Modify: `backend/app/models/workspace.py`
- Modify: `backend/app/schemas/workspace.py`
- Create: migration
- Test: `backend/tests/test_workspaces.py` (add one)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_workspaces.py`:

```python
def test_create_workspace_accepts_render_mode(client, auth_headers):
    r = client.post("/workspaces", json={
        "name": "Render Mode WS", "vertical": "general",
        "document_render_mode": "faithful",
    }, headers=auth_headers)
    assert r.status_code in (200, 201)
    assert r.json()["document_render_mode"] == "faithful"


def test_create_workspace_defaults_render_mode_schema(client, auth_headers):
    r = client.post("/workspaces", json={"name": "Default WS", "vertical": "general"},
                    headers=auth_headers)
    assert r.status_code in (200, 201)
    assert r.json()["document_render_mode"] == "schema"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_workspaces.py::test_create_workspace_accepts_render_mode -v
```
Expected: FAIL — column/field doesn't exist.

- [ ] **Step 3: Add the column, schema field, and migration**

1. In `backend/app/models/workspace.py`:

```python
    document_render_mode = Column(String, nullable=False, server_default="schema")
```

2. In `backend/app/schemas/workspace.py`, add to the create-in and out schemas:

```python
    document_render_mode: str = "schema"  # "schema" | "faithful"
```

3. Generate + verify + apply:

```bash
docker-compose run --rm backend alembic revision --autogenerate -m "phase2f workspace render mode"
docker-compose run --rm backend alembic upgrade head
docker-compose run --rm backend alembic downgrade -1
docker-compose run --rm backend alembic upgrade head
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_workspaces.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/workspace.py backend/app/schemas/workspace.py backend/alembic/versions/ backend/tests/test_workspaces.py
git commit -m "feat: workspace document_render_mode preference

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Connector API client

**Files:**
- Create: `frontend/src/api/connectors.js`

- [ ] **Step 1: Implement the client (no separate test — exercised via Sources tests in Task 3)**

Create `frontend/src/api/connectors.js`, matching the axios style of `frontend/src/api/schemas.js` (same base instance, `withCredentials`):

```js
import api from "./client";  // match the shared axios instance used by other api/*.js

export const listConnectors = (workspaceId) =>
  api.get(`/workspaces/${workspaceId}/connectors`).then((r) => r.data);

export const searchConnector = (workspaceId, connectorId, params) =>
  api.post(`/workspaces/${workspaceId}/connectors/${connectorId}/search`, { params })
     .then((r) => r.data);

export const listConnectorItems = (workspaceId, connectorId, candidateRef) =>
  api.post(`/workspaces/${workspaceId}/connectors/${connectorId}/list`,
           { candidate_ref: candidateRef }).then((r) => r.data);

export const fetchConnector = (workspaceId, connectorId, body) =>
  api.post(`/workspaces/${workspaceId}/connectors/${connectorId}/fetch`, body)
     .then((r) => r.data);

export const listRuns = (workspaceId) =>
  api.get(`/workspaces/${workspaceId}/connector-runs`).then((r) => r.data);

export const getRun = (workspaceId, runId) =>
  api.get(`/workspaces/${workspaceId}/connector-runs/${runId}`).then((r) => r.data);
```

> Match the import — if other clients do `import { api } from "./client"` or use a different
> filename, follow that exactly.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/connectors.js
git commit -m "feat: connector API client

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Sources page

**Files:**
- Create: `frontend/src/pages/workspace/Sources.jsx`
- Modify: `frontend/src/components/layout/WorkspaceSidebar.jsx`
- Modify: router config (workspace routes)
- Test: `frontend/src/__tests__/test_sources.jsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/test_sources.jsx`:

```jsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Sources from "../pages/workspace/Sources";
import * as connectorsApi from "../api/connectors";

vi.mock("../api/connectors");

const ws = { id: "ws-1", vertical: "general" };
vi.mock("../context/WorkspaceContext", () => ({
  useWorkspace: () => ({ workspace: ws }),
}));

beforeEach(() => {
  connectorsApi.listConnectors.mockResolvedValue([
    { id: "irs-teos", name: "IRS TEOS — 990 Filings",
      description: "Fetch 990s by name", verticals: ["general"], search_schema: {} },
  ]);
  connectorsApi.listRuns.mockResolvedValue([]);
});

test("operator searches by name and sees candidates with EIN", async () => {
  connectorsApi.searchConnector.mockResolvedValue([
    { ref: "123456789", display_name: "Bright Future Ministries Inc",
      identifier: "12-3456789", location: "Marysville, OH" },
  ]);

  render(<Sources />);
  await screen.findByText("IRS TEOS — 990 Filings");

  fireEvent.change(screen.getByPlaceholderText(/search by organization name/i),
                   { target: { value: "Bright Future" } });
  fireEvent.click(screen.getByRole("button", { name: /search/i }));

  await waitFor(() => {
    expect(screen.getByText("Bright Future Ministries Inc")).toBeInTheDocument();
    expect(screen.getByText(/12-3456789/)).toBeInTheDocument();
  });
});

test("selecting a candidate lists filings with checkboxes", async () => {
  connectorsApi.searchConnector.mockResolvedValue([
    { ref: "123456789", display_name: "Bright Future Ministries Inc",
      identifier: "12-3456789", location: "Marysville, OH" },
  ]);
  connectorsApi.listConnectorItems.mockResolvedValue([
    { item_ref: "123456789:2023:o", label: "Form 990", year: 2023,
      item_type: "990", filed_date: "2024-05-12" },
  ]);

  render(<Sources />);
  await screen.findByText("IRS TEOS — 990 Filings");
  fireEvent.change(screen.getByPlaceholderText(/search by organization name/i),
                   { target: { value: "Bright Future" } });
  fireEvent.click(screen.getByRole("button", { name: /search/i }));
  fireEvent.click(await screen.findByText("Bright Future Ministries Inc"));

  await waitFor(() => expect(screen.getByText(/Form 990/)).toBeInTheDocument());
  expect(screen.getByText(/2023/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm run test -- test_sources
```
Expected: FAIL — `Sources` component does not exist.

- [ ] **Step 3: Implement the Sources page**

Create `frontend/src/pages/workspace/Sources.jsx`. Match the slate/sky styling of `ExtractionReview.jsx`. Structure: two columns — left workflow (connector pick + search → candidates → filings), right pull history.

```jsx
import { useEffect, useState } from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import {
  listConnectors, searchConnector, listConnectorItems, fetchConnector, listRuns,
} from "../../api/connectors";
import { useToast } from "../../hooks/useToast";

export default function Sources() {
  const { workspace } = useWorkspace();
  const toast = useToast();
  const [connectors, setConnectors] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [picked, setPicked] = useState(null);     // SearchCandidate
  const [items, setItems] = useState([]);
  const [checked, setChecked] = useState({});     // item_ref -> bool
  const [runs, setRuns] = useState([]);

  useEffect(() => {
    listConnectors(workspace.id).then((c) => {
      setConnectors(c);
      if (c.length) setActiveId(c[0].id);
    });
    listRuns(workspace.id).then(setRuns);
  }, [workspace.id]);

  const doSearch = async () => {
    setPicked(null); setItems([]); setChecked({});
    const res = await searchConnector(workspace.id, activeId, { query });
    setCandidates(res);
  };

  const pick = async (cand) => {
    setPicked(cand);
    const its = await listConnectorItems(workspace.id, activeId, cand.ref);
    setItems(its);
    setChecked(Object.fromEntries(its.map((i) => [i.item_ref, true])));
  };

  const pull = async () => {
    const item_refs = items.filter((i) => checked[i.item_ref]).map((i) => i.item_ref);
    if (!item_refs.length) return;
    try {
      await fetchConnector(workspace.id, activeId, {
        candidate_ref: picked.ref, candidate_label: `${picked.display_name} · ${picked.identifier}`,
        search_query: query, item_refs,
      });
      toast.success(`Pulling ${item_refs.length} into workspace`);
      setRuns(await listRuns(workspace.id));
    } catch {
      toast.error("Pull failed");
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-slate-100">Sources</h1>
      <p className="text-sm text-slate-500 mb-5">
        Pull documents from public data sources directly into this workspace.
      </p>
      <div className="grid grid-cols-2 gap-5">
        {/* LEFT: workflow */}
        <div>
          <div className="flex gap-2 mb-3">
            <select value={activeId || ""} onChange={(e) => setActiveId(e.target.value)}
                    className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200">
              {connectors.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <input value={query} onChange={(e) => setQuery(e.target.value)}
                   placeholder="Search by organization name…"
                   className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200" />
            <button onClick={doSearch}
                    className="bg-sky-600 text-white rounded-lg px-4 py-2 text-sm font-semibold">
              Search
            </button>
          </div>

          {!picked && candidates.map((c) => (
            <button key={c.ref} onClick={() => pick(c)}
                    className="w-full text-left bg-slate-900 border border-slate-800 rounded-lg p-3 mb-2 hover:border-cyan-700">
              <div className="font-semibold text-slate-100">{c.display_name}</div>
              <div className="text-xs text-slate-400">{c.location} · EIN {c.identifier}</div>
            </button>
          ))}

          {picked && (
            <div>
              <div className="bg-cyan-950/40 border border-cyan-800 rounded-lg p-3 mb-3">
                <div className="font-bold text-slate-100">{picked.display_name}</div>
                <div className="text-xs text-cyan-300">EIN {picked.identifier} · {picked.location}</div>
              </div>
              {items.map((i) => (
                <label key={i.item_ref}
                       className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg p-3 mb-2 cursor-pointer">
                  <input type="checkbox" checked={!!checked[i.item_ref]}
                         onChange={(e) => setChecked({ ...checked, [i.item_ref]: e.target.checked })} />
                  <span className="font-semibold text-slate-100 w-14">{i.year}</span>
                  <span className="text-sm text-slate-400 flex-1">{i.label} · filed {i.filed_date}</span>
                </label>
              ))}
              <button onClick={pull}
                      className="bg-cyan-600 text-white rounded-lg px-4 py-2 text-sm font-semibold mt-2">
                Pull {items.filter((i) => checked[i.item_ref]).length} into workspace →
              </button>
            </div>
          )}
        </div>

        {/* RIGHT: history */}
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-3">Pull History</div>
          {runs.map((r) => (
            <div key={r.id} className="bg-slate-900 border border-slate-800 rounded-lg p-3 mb-2">
              <div className="flex justify-between items-center">
                <div className="font-semibold text-slate-100 text-sm">{r.candidate_label || r.connector_id}</div>
                <span className="text-xs px-2 py-0.5 rounded-full text-white"
                      style={{ background: r.status === "complete" ? "#16a34a" : r.status === "failed" ? "#dc2626" : "#0284c7" }}>
                  {r.status}
                </span>
              </div>
              <div className="text-xs text-slate-500 mt-1 font-mono">{r.search_query}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add the nav item + route**

In `frontend/src/components/layout/WorkspaceSidebar.jsx`, add a "Sources" engine nav item between Documents and Search (match the existing engine-items array shape, path `sources`). In the workspace router config, add a route `path="sources"` rendering `<Sources />`.

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
cd frontend && npm run test -- test_sources
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/workspace/Sources.jsx frontend/src/components/layout/WorkspaceSidebar.jsx frontend/src/__tests__/test_sources.jsx
git commit -m "feat: Sources page — search, pick org, select filings, pull

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

> Polling note: live-run polling (re-fetch `getRun` every 3s for `running` rows) is wired
> in Task 7 Step "polish" if desired — the page is functional with manual history refresh.
> Keep it out of the unit test to avoid fake-timer complexity.

---

## Task 4: Renderer registry + digital document renderer

**Files:**
- Create: `frontend/src/components/documents/rendererRegistry.js`
- Create: `frontend/src/components/documents/DigitalDocumentRenderer.jsx`
- Test: `frontend/src/__tests__/test_digital_renderer.jsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/test_digital_renderer.jsx`:

```jsx
import { render, screen } from "@testing-library/react";
import DigitalDocumentRenderer from "../components/documents/DigitalDocumentRenderer";
import { getRenderer } from "../components/documents/rendererRegistry";

const schema = {
  schema_fields: [
    { name: "total_revenue_cy", type: "number", group: "Revenue" },
    { name: "total_expenses", type: "number", group: "Expenses" },
    { name: "ein", type: "string", group: "Identity" },
  ],
};
const extractions = [
  { field_name: "total_revenue_cy", field_value: "1291200" },
  { field_name: "ein", field_value: "12-3456789" },
];

test("generic renderer groups fields by group key and shows values", () => {
  render(<DigitalDocumentRenderer schema={schema} extractions={extractions} />);
  expect(screen.getByText("Revenue")).toBeInTheDocument();
  expect(screen.getByText("Expenses")).toBeInTheDocument();
  expect(screen.getByText("1291200")).toBeInTheDocument();
  expect(screen.getByText("12-3456789")).toBeInTheDocument();
});

test("registry falls back to generic when no faithful template registered", () => {
  const R = getRenderer("990", "faithful");  // none registered in engine
  expect(R).toBe(DigitalDocumentRenderer);
});

test("registry returns generic for schema mode regardless of type", () => {
  const R = getRenderer("990", "schema");
  expect(R).toBe(DigitalDocumentRenderer);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm run test -- test_digital_renderer
```
Expected: FAIL — components don't exist.

- [ ] **Step 3: Implement the registry**

Create `frontend/src/components/documents/rendererRegistry.js`:

```js
import DigitalDocumentRenderer from "./DigitalDocumentRenderer";

// Engine ships only the generic renderer. Caps register faithful per-type templates
// in Phase 3 by calling registerRenderer(docType, Component).
const _faithful = {};

export function registerRenderer(docType, component) {
  _faithful[docType] = component;
}

export function getRenderer(docType, renderMode) {
  if (renderMode === "faithful" && _faithful[docType]) return _faithful[docType];
  return DigitalDocumentRenderer;
}
```

- [ ] **Step 4: Implement the generic renderer**

Create `frontend/src/components/documents/DigitalDocumentRenderer.jsx`:

```jsx
export default function DigitalDocumentRenderer({ schema, extractions }) {
  const byName = Object.fromEntries(
    (extractions || []).map((e) => [e.field_name, e.field_value])
  );

  // Group fields by their `group` key (added in the review-pane work); "Other" fallback.
  const groups = {};
  for (const f of schema?.schema_fields || []) {
    const g = f.group || "Other";
    (groups[g] ||= []).push(f);
  }

  return (
    <div className="max-w-2xl mx-auto bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      {Object.entries(groups).map(([group, fields]) => (
        <div key={group} className="border-b border-slate-800 last:border-0">
          <div className="bg-slate-800/60 px-5 py-2 text-xs font-bold uppercase tracking-wide text-cyan-300">
            {group}
          </div>
          {fields.map((f) => (
            <div key={f.name} className="flex justify-between px-5 py-2 text-sm border-b border-slate-800/50 last:border-0">
              <span className="text-slate-300">{f.name}</span>
              <span className="text-slate-100 font-mono">{byName[f.name] ?? "—"}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
cd frontend && npm run test -- test_digital_renderer
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents/rendererRegistry.js frontend/src/components/documents/DigitalDocumentRenderer.jsx frontend/src/__tests__/test_digital_renderer.jsx
git commit -m "feat: schema-driven digital document renderer + registry

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Wire the pluggable renderer into DocumentViewer

**Files:**
- Modify: `frontend/src/pages/workspace/DocumentViewer.jsx`
- Modify: `frontend/src/components/documents/DocumentList.jsx`

- [ ] **Step 1: Select the left renderer by document source/type**

In `DocumentViewer.jsx`, where the left pane currently always renders the PDF:

```jsx
import { getRenderer } from "../../components/documents/rendererRegistry";
import { useWorkspace } from "../../context/WorkspaceContext";
// ...
const { workspace } = useWorkspace();
const hasFile = document.file_type === "pdf" || document.file_type?.startsWith("image");

// left pane:
{hasFile ? (
  <PdfPane /* existing react-pdf rendering, unchanged */ />
) : (
  (() => {
    const Renderer = getRenderer(document.detected_doc_type, workspace.document_render_mode);
    return <Renderer schema={schema} extractions={extractions} />;
  })()
)}
```

> `schema` and `extractions` are already fetched by DocumentViewer for the right pane (the
> review-pane work added schema fetching). Reuse those — don't add new fetches. If `schema`
> isn't currently fetched in non-review mode, add a `GET /schemas/{id}` call using the
> document's `schema_id` (endpoint exists from the review-pane work).

- [ ] **Step 2: Add the source badge to the document list**

In `DocumentList.jsx`, where each document card renders, add a small badge when the document
came from a connector (`source_type` is the provenance field; `"upload"` means a manual upload):

```jsx
{doc.source_type && doc.source_type !== "upload" && (
  <span className="text-[9px] bg-sky-900 text-sky-300 px-1.5 py-0.5 rounded font-semibold ml-2">
    {doc.source_type.toUpperCase()}
  </span>
)}
```

- [ ] **Step 3: Manual verification**

```bash
docker-compose up -d
```
With a sourced 990 in a workspace (pull one via the Sources page), open it in the viewer. Confirm the left pane shows the grouped digital document (not an empty PDF pane), and the Documents list shows the source badge.

- [ ] **Step 4: Run frontend suite (regression)**

Run:
```bash
cd frontend && npm run test
```
Expected: all green (existing DocumentViewer tests still pass — PDF path unchanged).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/workspace/DocumentViewer.jsx frontend/src/components/documents/DocumentList.jsx
git commit -m "feat: pluggable left renderer + source badge in document list

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: `suggest_source` agent tool + chat action card

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/app/services/agent_registry.py`
- Create: `frontend/src/components/sources/SuggestSourceCard.jsx`
- Modify: `frontend/src/pages/workspace/AIChat.jsx`
- Test: `backend/tests/test_agent_tools.py` (add)

- [ ] **Step 1: Write the failing backend test**

Add to `backend/tests/test_agent_tools.py`:

```python
def test_suggest_source_returns_structured_suggestion():
    from app.services import agent_tools
    result = agent_tools.suggest_source(
        workspace_id="ws-1", db=None,
        connector_id="irs-teos", search_query="Bright Future",
        reason="A 990 would show related-party disclosures.",
    )
    assert result["connector_id"] == "irs-teos"
    assert result["search_query"] == "Bright Future"
    assert "reason" in result
    assert result["action"] == "suggest_source"   # marks it for the frontend to render a card
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_agent_tools.py::test_suggest_source_returns_structured_suggestion -v
```
Expected: FAIL — function doesn't exist.

- [ ] **Step 3: Implement the tool (read-only — returns a suggestion, never fetches)**

Add to `backend/app/services/agent_tools.py`:

```python
def suggest_source(
    workspace_id: str, db, connector_id: str, search_query: str, reason: str
) -> dict:
    """Recommend a public data source worth pulling — does NOT fetch.

    Returns a structured suggestion the chat renders as an action card. The operator
    decides whether to pull. Keeps the agent within the read-only trust boundary:
    Claude proposes a search (a name/query), never a pre-filled identifier it might
    get wrong, and never writes to the case record.
    """
    return {
        "action": "suggest_source",
        "connector_id": connector_id,
        "search_query": search_query,
        "reason": reason,
    }
```

Ensure `execute()`'s dispatch maps `"suggest_source"` to this function (add to the dispatch table the same way the other six tools are wired). `workspace_id` is injected by `execute()` as with all tools.

- [ ] **Step 4: Register the tool schema**

`agent_registry.py` exposes tools via `build_tool_schemas()` which RETURNS a list of 6 tool
dicts (there is no `TOOL_SCHEMAS` constant). Add the `suggest_source` dict to the list
returned by `build_tool_schemas()` — append it inside the `return [ ... ]`. Because
`VERTICAL_TOOLS` for fraud/insurance/general all call `build_tool_schemas()`, adding it here
makes it available to every vertical automatically.

```python
        {
            "name": "suggest_source",
            "description": (
                "Recommend a public data source the operator should pull into the workspace "
                "when the investigation would benefit from a document not yet present (e.g. a "
                "990 filing, a UCC record). Does not fetch — returns a suggestion the operator "
                "confirms. Use when you notice a gap in the evidence."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "connector_id": {"type": "string", "description": "e.g. 'irs-teos'"},
                    "search_query": {"type": "string", "description": "Name/term to search, e.g. an org name"},
                    "reason": {"type": "string", "description": "Why this source helps the investigation"},
                },
                "required": ["connector_id", "search_query", "reason"],
            },
        },
```

> Update the `build_tool_schemas` docstring ("all 6 core tools") to 7. The `execute()`
> dispatcher in `agent_tools.py` also needs `"suggest_source"` mapped to the function —
> check how the existing 6 are dispatched and add the same wiring.

- [ ] **Step 5: Run backend test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_agent_tools.py -v
```
Expected: PASS (all agent-tools tests, including the existing 27).

- [ ] **Step 6: Implement the chat action card**

Create `frontend/src/components/sources/SuggestSourceCard.jsx`:

```jsx
import { useNavigate } from "react-router-dom";

export default function SuggestSourceCard({ workspaceId, suggestion, onDismiss }) {
  const navigate = useNavigate();
  const runSearch = () => {
    // Deep-link to Sources with connector + query prefilled (Sources reads these params).
    const q = new URLSearchParams({
      connector: suggestion.connector_id, query: suggestion.search_query,
    });
    navigate(`/workspaces/${workspaceId}/sources?${q.toString()}`);
  };
  return (
    <div className="bg-gradient-to-br from-cyan-950 to-slate-900 border border-cyan-800 rounded-xl p-4 my-2">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">📡</span>
        <div>
          <div className="text-sm font-bold text-slate-100">
            Suggested source: {suggestion.connector_id}
          </div>
          <div className="text-xs text-cyan-300 font-mono">search: “{suggestion.search_query}”</div>
        </div>
      </div>
      <div className="text-sm text-slate-300 border-l-2 border-cyan-800 pl-3 my-2">
        {suggestion.reason}
      </div>
      <div className="flex gap-2">
        <button onClick={runSearch}
                className="bg-cyan-600 text-white rounded-lg px-3 py-1.5 text-sm font-semibold">
          Run this search
        </button>
        <button onClick={onDismiss}
                className="bg-slate-700 text-slate-200 rounded-lg px-3 py-1.5 text-sm">
          Dismiss
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Render the card in the chat thread**

In `AIChat.jsx`, when a message's tool result carries `action === "suggest_source"`, render `<SuggestSourceCard workspaceId={workspace.id} suggestion={...} onDismiss={...} />` instead of plain text. Match how AIChat currently surfaces tool activity; if tool results aren't currently shown inline, detect the suggestion in the assistant message payload and render the card after that message.

- [ ] **Step 8: Make Sources read the deep-link params**

In `Sources.jsx`, on mount, read `connector` and `query` from `useSearchParams()`; if present, preselect the connector, set the query, and auto-run `doSearch()` so the operator lands on the results step.

- [ ] **Step 9: Run frontend suite**

Run:
```bash
cd frontend && npm run test
```
Expected: all green.

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/agent_tools.py backend/app/services/agent_registry.py backend/tests/test_agent_tools.py frontend/src/components/sources/SuggestSourceCard.jsx frontend/src/pages/workspace/AIChat.jsx frontend/src/pages/workspace/Sources.jsx
git commit -m "feat: suggest_source agent tool + chat action card with deep-link

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Full suites + inventory

- [ ] **Step 1: Backend + frontend suites**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
cd frontend && npm run test
```
Expected: all green.

- [ ] **Step 2: Update build inventory + roadmap**

In `docs/build-inventory.md`: add `Sources.jsx`, `DigitalDocumentRenderer.jsx`, `rendererRegistry.js`, `SuggestSourceCard.jsx`, `connectors.js` API client; note `suggest_source` as the 7th agent tool; note `document_render_mode` on workspaces; Update Log row. In `docs/roadmap.md`, mark 2F Sources UI / digital viewer / AI suggestion complete.

- [ ] **Step 3: Commit**

```bash
git add docs/build-inventory.md docs/roadmap.md
git commit -m "docs: build inventory + roadmap — Sources UI, digital viewer, suggest_source

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** D1 nav (T3), D2 Sources page search→pick→select→pull (T3), D3 render-mode (T1 + WorkspacesHome toggle — see note), D4 API client (T2), E1 pluggable renderer (T5), E2 generic renderer + registry (T4), F1 suggest_source (T6), F2 action card + deep-link (T6). All covered.
- **WorkspacesHome render-mode toggle:** spec D3 says the toggle is set at workspace creation. The backend accepts it (T1); add the toggle control to `WorkspacesHome.jsx`'s create modal as part of T1 Step 3 or a follow-up commit — flagged here so it isn't missed. (Default "schema" works without it.)
- **Type consistency:** `getRenderer(docType, renderMode)` signature defined T4, used T5. `suggest_source` return shape (`action`/`connector_id`/`search_query`/`reason`) defined T6 backend, consumed by T6 frontend card. Connector API client function names (T2) match Sources usage (T3).
- **Dependency:** requires Plan 2's API + provenance fields live. Stated in header.
- **Adjustment points flagged inline:** axios client import style (T2), AIChat tool-result surfacing (T6 S7), schema availability in DocumentViewer non-review mode (T5 S1) — each names what to check.
