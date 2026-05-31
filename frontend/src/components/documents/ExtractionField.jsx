import { useState } from 'react'

/**
 * Single field row in the schema review form.
 * Handles four states: auto-extracted (high confidence), low confidence,
 * not extracted (null extraction row), and source obscured.
 *
 * Props:
 *   field: schema field definition { name, type, description, group, required, ai_threshold? }
 *   extraction: DocumentExtraction row or null (null = field never extracted)
 *   threshold: float — confidence threshold from schema (field.ai_threshold or schema default)
 *   isActive: bool — true when this field has keyboard/click focus
 *   onFocus: () => void — notify parent to update PDF highlight
 *   onChange: (fieldName, value) => void — local state accumulation for save-all
 *   onVerify: (fieldName, value, note, evidenceType) => Promise — save with evidence
 */
export default function ExtractionField({
  field, extraction, threshold, isActive,
  onFocus, onChange, onVerify,
}) {
  const [value, setValue] = useState(extraction?.field_value || '')
  const [note, setNote] = useState('')
  const [isObscured, setIsObscured] = useState(false)
  const [saving, setSaving] = useState(false)
  const [verified, setVerified] = useState(extraction?.evidence != null)

  const isHumanCorrected = extraction?.attempt === 3
  const isMissing = extraction == null
  const isLowConfidence = !isMissing && !isHumanCorrected &&
    (extraction.confidence < threshold || extraction.ocr_confidence < threshold)

  const borderClass = isHumanCorrected || verified
    ? 'border-green-700 bg-green-950/30'
    : isObscured
    ? 'border-purple-700 bg-purple-950/30'
    : isMissing
    ? 'border-slate-700 bg-slate-900/50 border-dashed'
    : isLowConfidence
    ? 'border-yellow-700 bg-yellow-950/30'
    : 'border-slate-700'

  const handleChange = (v) => {
    setValue(v)
    onChange(field.name, v)
  }

  const handleVerify = async (type = 'auto_highlight') => {
    setSaving(true)
    try {
      await onVerify(field.name, value, note, type)
      setVerified(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className={`border rounded p-2 mb-1 transition-colors cursor-pointer ${borderClass} ${isActive ? 'ring-1 ring-blue-500' : ''}`}
      onClick={onFocus}
    >
      {/* Label row */}
      <div className="flex items-center justify-between mb-1">
        <label className={`text-xs font-medium ${isActive ? 'text-blue-400' : 'text-slate-500'}`}>
          {field.name}
          {field.required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
        <div className="flex items-center gap-2">
          {/* Confidence pills — shown on extracted, non-corrected, non-obscured fields */}
          {extraction && !isHumanCorrected && !isObscured && (
            <span className="flex gap-1 text-xs">
              <span className={extraction.confidence >= 0.85 ? 'text-green-400' : extraction.confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}>
                AI {Math.round(extraction.confidence * 100)}%
              </span>
              <span className={extraction.ocr_confidence >= 0.85 ? 'text-green-400' : extraction.ocr_confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}>
                OCR {Math.round(extraction.ocr_confidence * 100)}%
              </span>
            </span>
          )}
          {verified && <span className="text-xs text-green-400 font-medium">✓ Verified</span>}
          {isHumanCorrected && !verified && <span className="text-xs text-green-400">Corrected</span>}
          {/* Obscured toggle — available on unverified, uncorrected fields */}
          {!isHumanCorrected && !verified && (
            <button
              onClick={(e) => { e.stopPropagation(); setIsObscured((v) => !v) }}
              className={`text-xs px-1.5 py-0.5 rounded transition-colors ${isObscured ? 'bg-purple-800 text-purple-200' : 'bg-slate-800 text-slate-500 hover:text-purple-400'}`}
              title="Mark source as physically obscured"
            >
              ▒
            </button>
          )}
        </div>
      </div>

      {/* Value input */}
      {isObscured ? (
        <div className="text-xs text-purple-400 italic px-1 py-1">
          Source obscured — capture the damaged region on the PDF
        </div>
      ) : (
        <input
          className={`w-full text-xs rounded px-2 py-1 outline-none focus:ring-1 focus:ring-blue-500 ${
            isMissing
              ? 'bg-slate-800 border border-dashed border-slate-600 text-slate-400 placeholder:italic'
              : 'bg-slate-800 border border-slate-600 text-white'
          }`}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={isMissing ? `enter ${field.name} from document…` : undefined}
          onFocus={onFocus}
          onClick={(e) => e.stopPropagation()}
        />
      )}

      {/* Note field — shown on actionable states */}
      {(isLowConfidence || isMissing || isObscured) && !verified && !isHumanCorrected && (
        <input
          className="w-full text-xs rounded px-2 py-0.5 mt-1 bg-slate-800/50 border border-slate-700 text-slate-400 placeholder:text-slate-600 outline-none"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="note (e.g. nominal consideration, stamp overlay)…"
          onClick={(e) => e.stopPropagation()}
        />
      )}

      {/* Action buttons */}
      {!isHumanCorrected && !verified && (
        <div className="flex gap-1 mt-1.5">
          {isObscured ? (
            <button
              disabled={saving}
              onClick={(e) => { e.stopPropagation(); handleVerify('obscured') }}
              className="flex-1 text-xs py-1 bg-purple-800 hover:bg-purple-700 text-purple-100 rounded disabled:opacity-50 transition-colors"
            >
              {saving ? '…' : '📷 Capture obscured region'}
            </button>
          ) : (
            <>
              {(isMissing || isLowConfidence) && (
                <button
                  onClick={(e) => { e.stopPropagation(); onFocus() }}
                  className="text-xs px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
                  title="Activate PDF highlight for this field"
                >
                  ↗ PDF
                </button>
              )}
              <button
                disabled={saving || (!value && !isObscured)}
                onClick={(e) => { e.stopPropagation(); handleVerify('auto_highlight') }}
                className="flex-1 text-xs py-1 bg-blue-700 hover:bg-blue-600 text-white rounded disabled:opacity-50 transition-colors"
              >
                {saving ? '…' : '✓ Verify'}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
