import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  listConnectors,
  searchConnector,
  listConnectorItems,
  fetchConnector,
  listRuns,
} from "../../api/connectors";
import { useToast } from "../../hooks/useToast";

export default function Sources() {
  const { workspaceId } = useParams();
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const [connectors, setConnectors] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [picked, setPicked] = useState(null);
  const [items, setItems] = useState([]);
  const [checked, setChecked] = useState({});
  const [runs, setRuns] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    listConnectors(workspaceId).then((c) => {
      setConnectors(c);
      const deepConnector = searchParams.get("connector");
      const deepQuery = searchParams.get("query");
      const initial = deepConnector && c.find((x) => x.id === deepConnector)
        ? deepConnector
        : c.length ? c[0].id : null;
      setActiveId(initial);
      if (deepQuery) setQuery(deepQuery);
    });
    listRuns(workspaceId).then(setRuns);
  }, [workspaceId]);

  // Auto-search when connector + query come from deep-link
  useEffect(() => {
    const deepQuery = searchParams.get("query");
    const deepConnector = searchParams.get("connector");
    if (deepQuery && deepConnector && activeId === deepConnector) {
      doSearch(deepConnector, deepQuery);
    }
  }, [activeId]);

  const doSearch = async (connectorId = activeId, searchQuery = query) => {
    if (!connectorId) return;
    setPicked(null);
    setItems([]);
    setChecked({});
    setSearching(true);
    try {
      const res = await searchConnector(workspaceId, connectorId, { query: searchQuery });
      setCandidates(res);
    } finally {
      setSearching(false);
    }
  };

  const pick = async (cand) => {
    setPicked(cand);
    const its = await listConnectorItems(workspaceId, activeId, cand.ref);
    setItems(its);
    setChecked(Object.fromEntries(its.map((i) => [i.item_ref, true])));
  };

  const pull = async () => {
    const item_refs = items.filter((i) => checked[i.item_ref]).map((i) => i.item_ref);
    if (!item_refs.length) return;
    try {
      await fetchConnector(workspaceId, activeId, {
        candidate_ref: picked.ref,
        candidate_label: `${picked.display_name} · ${picked.identifier}`,
        search_query: query,
        item_refs,
      });
      toast.success(`Pulling ${item_refs.length} into workspace`);
      setRuns(await listRuns(workspaceId));
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
            <select
              value={activeId || ""}
              onChange={(e) => setActiveId(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200"
            >
              {connectors.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              placeholder="Search by organization name…"
              className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200"
            />
            <button
              onClick={() => doSearch()}
              disabled={searching}
              className="bg-sky-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              Search
            </button>
          </div>

          {!picked &&
            candidates.map((c) => (
              <button
                key={c.ref}
                onClick={() => pick(c)}
                className="w-full text-left bg-slate-900 border border-slate-800 rounded-lg p-3 mb-2 hover:border-cyan-700"
              >
                <div className="font-semibold text-slate-100">{c.display_name}</div>
                <div className="text-xs text-slate-400">
                  {c.location} · EIN {c.identifier}
                </div>
              </button>
            ))}

          {picked && (
            <div>
              <div className="bg-cyan-950/40 border border-cyan-800 rounded-lg p-3 mb-3">
                <button
                  onClick={() => setPicked(null)}
                  className="text-xs text-slate-400 hover:text-slate-200 float-right"
                >
                  ← back
                </button>
                <div className="font-bold text-slate-100">{picked.display_name}</div>
                <div className="text-xs text-cyan-300">
                  EIN {picked.identifier} · {picked.location}
                </div>
              </div>
              {items.map((i) => (
                <label
                  key={i.item_ref}
                  className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg p-3 mb-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={!!checked[i.item_ref]}
                    onChange={(e) =>
                      setChecked({ ...checked, [i.item_ref]: e.target.checked })
                    }
                  />
                  <span className="font-semibold text-slate-100 w-14">{i.year}</span>
                  <span className="text-sm text-slate-400 flex-1">
                    {i.label} · filed {i.filed_date}
                  </span>
                </label>
              ))}
              <button
                onClick={pull}
                className="bg-cyan-600 text-white rounded-lg px-4 py-2 text-sm font-semibold mt-2"
              >
                Pull {items.filter((i) => checked[i.item_ref]).length} into workspace →
              </button>
            </div>
          )}
        </div>

        {/* RIGHT: pull history */}
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-3">
            Pull History
          </div>
          {runs.length === 0 && (
            <p className="text-slate-600 text-sm">No pulls yet.</p>
          )}
          {runs.map((r) => (
            <div
              key={r.id}
              className="bg-slate-900 border border-slate-800 rounded-lg p-3 mb-2"
            >
              <div className="flex justify-between items-center">
                <div className="font-semibold text-slate-100 text-sm">
                  {r.candidate_label || r.connector_id}
                </div>
                <span
                  className="text-xs px-2 py-0.5 rounded-full text-white"
                  style={{
                    background:
                      r.status === "complete"
                        ? "#16a34a"
                        : r.status === "failed"
                        ? "#dc2626"
                        : "#0284c7",
                  }}
                >
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
