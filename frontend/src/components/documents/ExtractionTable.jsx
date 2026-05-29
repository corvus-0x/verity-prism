import { useState } from 'react'
import { correctExtraction } from '../../api/documents'

export default function ExtractionTable({ extractions, editable = false, workspaceId, documentId, onUpdate }) {
  if (!extractions?.length) return <p className="text-slate-500 text-sm">No extractions yet.</p>

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-slate-500 border-b border-slate-700">
          <th className="pb-2 font-medium">Field</th>
          <th className="pb-2 font-medium">Value</th>
          <th className="pb-2 font-medium text-right">{editable ? 'Status' : 'Confidence'}</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-800">
        {extractions.map((e) => (
          <ExtractionRow
            key={e.id}
            extraction={e}
            editable={editable}
            workspaceId={workspaceId}
            documentId={documentId}
            onUpdate={onUpdate}
          />
        ))}
      </tbody>
    </table>
  )
}

function ExtractionRow({ extraction: e, editable, workspaceId, documentId, onUpdate }) {
  const [editing, setEditing] = useState(false)
  const [inputValue, setInputValue] = useState(e.field_value || '')
  const [saving, setSaving] = useState(false)
  const isHumanCorrected = e.attempt === 3

  const rowClass = isHumanCorrected
    ? 'bg-green-950'
    : e.confidence < 0.7
    ? 'bg-yellow-950'
    : ''

  const handleAccept = async () => {
    setSaving(true)
    try {
      const res = await correctExtraction(workspaceId, documentId, e.id, inputValue)
      onUpdate?.(res.data)
      setEditing(false)
    } catch {
      // leave editing open so the user can retry
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className={rowClass}>
      <td className="py-2 text-slate-400 pr-4 align-top">{e.field_name}</td>
      <td className="py-2 text-white">
        {editable && !isHumanCorrected && editing ? (
          <input
            className="bg-slate-800 text-white px-2 py-1 rounded text-sm w-full border border-slate-600 focus:outline-none focus:border-blue-500"
            value={inputValue}
            onChange={(ev) => setInputValue(ev.target.value)}
            autoFocus
          />
        ) : (
          e.field_value || '—'
        )}
      </td>
      <td className="py-2 text-right align-top">
        {isHumanCorrected ? (
          <span className="text-xs text-green-400 font-medium">Corrected</span>
        ) : editable ? (
          <div className="flex items-center justify-end gap-1">
            <span className={`text-xs ${e.confidence >= 0.7 ? 'text-yellow-400' : 'text-red-400'}`}>
              {Math.round(e.confidence * 100)}%
            </span>
            {editing ? (
              <>
                <button
                  onClick={handleAccept}
                  disabled={saving}
                  className="text-xs px-2 py-0.5 bg-blue-600 hover:bg-blue-500 text-white rounded disabled:opacity-50"
                >
                  {saving ? '…' : 'Accept'}
                </button>
                <button
                  onClick={() => { setEditing(false); setInputValue(e.field_value || '') }}
                  className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                onClick={() => setEditing(true)}
                className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded"
              >
                Edit
              </button>
            )}
          </div>
        ) : (
          <span className={`text-xs ${
            e.confidence >= 0.9 ? 'text-green-400'
            : e.confidence >= 0.7 ? 'text-yellow-400'
            : 'text-red-400'
          }`}>
            {Math.round(e.confidence * 100)}%
          </span>
        )}
      </td>
    </tr>
  )
}
