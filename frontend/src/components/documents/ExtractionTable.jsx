import { useState } from 'react'
import { correctExtraction } from '../../api/documents'

const COL_TEMPLATE = 'minmax(0,5fr) minmax(0,7fr) minmax(0,4fr)'

export default function ExtractionTable({ extractions, editable = false, workspaceId, documentId, onUpdate }) {
  if (!extractions?.length) return <p className="text-slate-500 text-sm">No extractions yet.</p>

  return (
    <div className="w-full text-sm min-w-0">
      {/* Header */}
      <div
        className="grid gap-x-3 pb-2 mb-1 text-slate-500 font-medium"
        style={{ gridTemplateColumns: COL_TEMPLATE, borderBottom: '1px solid #111E30' }}
      >
        <span>Field</span>
        <span>Value</span>
        <span className="text-right">Confidence</span>
      </div>

      {/* Rows */}
      <div className="divide-y divide-[#111E30]">
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
      </div>
    </div>
  )
}

function ConfidencePill({ label, value }) {
  const pct = Math.round(value * 100)
  const color = pct >= 90 ? 'text-green-400' : pct >= 70 ? 'text-yellow-400' : 'text-red-400'
  return (
    <span className="flex items-center gap-1">
      <span className="text-slate-600 text-xs">{label}</span>
      <span className={`text-xs font-medium ${color}`}>{pct}%</span>
    </span>
  )
}

function ExtractionRow({ extraction: e, editable, workspaceId, documentId, onUpdate }) {
  const [editing, setEditing] = useState(false)
  const [inputValue, setInputValue] = useState(e.field_value || '')
  const [saving, setSaving] = useState(false)
  const isHumanCorrected = e.attempt === 3

  const rowBg = isHumanCorrected
    ? 'bg-green-950'
    : e.confidence < 0.7 || (e.ocr_confidence != null && e.ocr_confidence < 0.7)
    ? 'bg-yellow-950/60'
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
    <div
      className={`grid gap-x-3 py-2 ${rowBg}`}
      style={{ gridTemplateColumns: COL_TEMPLATE }}
    >
      {/* Field name — breaks on underscores when narrow */}
      <span className="text-slate-400 break-all leading-snug pt-0.5 min-w-0">
        {e.field_name}
      </span>

      {/* Value — wraps, never overflows */}
      <span className="text-slate-100 break-words leading-snug min-w-0">
        {editable && !isHumanCorrected && editing ? (
          <input
            className="field-input text-xs py-1"
            value={inputValue}
            onChange={(ev) => setInputValue(ev.target.value)}
            autoFocus
          />
        ) : (
          e.field_value || <span className="text-slate-600">—</span>
        )}
      </span>

      {/* Confidence / actions */}
      <div className="flex flex-col items-end gap-0.5 min-w-0">
        {isHumanCorrected ? (
          <span className="text-xs text-green-400 font-medium">Corrected</span>
        ) : editable ? (
          <>
            <ConfidencePill label="AI"  value={e.confidence} />
            {e.ocr_confidence != null && (
              <ConfidencePill label="OCR" value={e.ocr_confidence} />
            )}
            <div className="flex items-center gap-1 mt-1">
              {editing ? (
                <>
                  <button
                    onClick={handleAccept}
                    disabled={saving}
                    className="text-xs px-2 py-0.5 rounded text-white disabled:opacity-50 transition-colors"
                    style={{ background: '#991B1B' }}
                  >
                    {saving ? '…' : 'Accept'}
                  </button>
                  <button
                    onClick={() => { setEditing(false); setInputValue(e.field_value || '') }}
                    className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setEditing(true)}
                  className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
                >
                  Edit
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <ConfidencePill label="AI"  value={e.confidence} />
            {e.ocr_confidence != null && (
              <ConfidencePill label="OCR" value={e.ocr_confidence} />
            )}
          </>
        )}
      </div>
    </div>
  )
}
