import { useNavigate } from "react-router-dom";

export default function SuggestSourceCard({ workspaceId, suggestion, onDismiss }) {
  const navigate = useNavigate();

  const runSearch = () => {
    const q = new URLSearchParams({
      connector: suggestion.connector_id,
      query: suggestion.search_query,
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
          <div className="text-xs text-cyan-300 font-mono">
            search: "{suggestion.search_query}"
          </div>
        </div>
      </div>
      <div className="text-sm text-slate-300 border-l-2 border-cyan-800 pl-3 my-2">
        {suggestion.reason}
      </div>
      <div className="flex gap-2">
        <button
          onClick={runSearch}
          className="bg-cyan-600 text-white rounded-lg px-3 py-1.5 text-sm font-semibold"
        >
          Run this search
        </button>
        <button
          onClick={onDismiss}
          className="bg-slate-700 text-slate-200 rounded-lg px-3 py-1.5 text-sm"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
