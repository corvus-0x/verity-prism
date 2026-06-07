export default function DigitalDocumentRenderer({ schema, extractions }) {
  const byName = Object.fromEntries(
    (extractions || []).map((e) => [e.field_name, e.field_value])
  );

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
            <div
              key={f.name}
              className="flex justify-between px-5 py-2 text-sm border-b border-slate-800/50 last:border-0"
            >
              <span className="text-slate-300">{f.name}</span>
              <span className="text-slate-100 font-mono">{byName[f.name] ?? "—"}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
