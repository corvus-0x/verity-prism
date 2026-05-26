export default function ExtractionTable({ extractions }) {
  if (!extractions?.length) return <p className="text-slate-500 text-sm">No extractions yet.</p>

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-slate-500 border-b border-slate-700">
          <th className="pb-2 font-medium">Field</th>
          <th className="pb-2 font-medium">Value</th>
          <th className="pb-2 font-medium text-right">Confidence</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-800">
        {extractions.map((e) => (
          <tr key={e.id} className={e.confidence < 0.7 ? 'bg-yellow-950' : ''}>
            <td className="py-2 text-slate-400 pr-4">{e.field_name}</td>
            <td className="py-2 text-white">{e.field_value || '—'}</td>
            <td className="py-2 text-right">
              <span className={`text-xs ${
                e.confidence >= 0.9 ? 'text-green-400'
                : e.confidence >= 0.7 ? 'text-yellow-400'
                : 'text-red-400'
              }`}>
                {Math.round(e.confidence * 100)}%
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
