// frontend/src/components/documents/SchemaReviewPane.jsx
import { useState, useCallback, useMemo } from 'react'
import ExtractionField from './ExtractionField'
import { correctExtraction, createExtraction } from '../../api/documents'

/**
 * Schema-driven review form — maps over schema.fields (not extractions).
 * Shows every field the schema defines: pre-populated where extracted, empty where not.
 * Groups fields by their `group` key into labeled sections.
 *
 * Props:
 *   schema: { id, fields: [{name, type, description, group, required, ai_threshold?, ...}],
 *              default_confidence_threshold }
 *   extractions: list of ExtractionOut rows (latest attempt per field)
 *   workspaceId: string
 *   documentId: string
 *   onFieldFocus: (fieldName, fieldValue) => void — parent updates PDF highlight
 *   onSaveComplete: () => void — called after save to refresh extractions list
 */
export default function SchemaReviewPane({
  schema, extractions, workspaceId, documentId,
  onFieldFocus, onSaveComplete,
}) {
  const [activeField, setActiveField] = useState(null)
  const [pendingChanges, setPendingChanges] = useState({})  // { fieldName: value }
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  // Build lookup: field_name → latest extraction row
  const extractionByName = useMemo(
    () => Object.fromEntries(extractions.map((e) => [e.field_name, e])),
    [extractions]
  )

  // Group schema fields by their group key
  const groups = useMemo(() => {
    const g = {}
    for (const field of (schema.fields || [])) {
      const name = field.group || 'Other'
      if (!g[name]) g[name] = []
      g[name].push(field)
    }
    return g
  }, [schema.fields])

  const handleFieldFocus = useCallback((fieldName) => {
    setActiveField(fieldName)
    const extraction = extractionByName[fieldName]
    const fieldValue = pendingChanges[fieldName] ?? extraction?.field_value ?? ''
    onFieldFocus(fieldName, fieldValue)
  }, [extractionByName, pendingChanges, onFieldFocus])

  const handleFieldChange = useCallback((fieldName, value) => {
    setPendingChanges((prev) => ({ ...prev, [fieldName]: value }))
  }, [])

  const handleVerify = useCallback(async (fieldName, value, note, evidenceType, skipCallback = false) => {
    const evidence = evidenceType
      ? { type: evidenceType, note: note || undefined }
      : null
    const extraction = extractionByName[fieldName]

    if (extraction) {
      await correctExtraction(workspaceId, documentId, extraction.id, value, evidence)
    } else {
      const field = (schema.fields || []).find((f) => f.name === fieldName)
      await createExtraction(
        workspaceId, documentId, fieldName, value,
        field?.type || 'text', schema.id, evidence
      )
    }

    setPendingChanges((prev) => {
      const next = { ...prev }
      delete next[fieldName]
      return next
    })
    if (!skipCallback) onSaveComplete()
  }, [extractionByName, schema, workspaceId, documentId, onSaveComplete])

  const dirtyCount = Object.keys(pendingChanges).length

  const handleSaveAll = async () => {
    setSaving(true)
    setSaveError(null)
    const entries = Object.entries(pendingChanges)
    const results = await Promise.allSettled(
      entries.map(([fieldName, value]) =>
        handleVerify(fieldName, value, '', 'manual_entry', true)
      )
    )
    setSaving(false)
    const failed = results.filter((r) => r.status === 'rejected')
    if (failed.length > 0) {
      setSaveError(`${failed.length} field(s) failed to save — try again.`)
    } else {
      onSaveComplete()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700 shrink-0">
        <div>
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
            {schema.document_type}
          </span>
          <span className="text-xs text-slate-500 ml-2">
            {extractions.length}/{(schema.fields || []).length} extracted
          </span>
        </div>
        <span className="text-xs text-slate-600">Tab to navigate</span>
      </div>

      {/* Scrollable form body */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {Object.entries(groups).map(([groupName, fields]) => (
          <div key={groupName} className="mb-4">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 pb-1 border-b border-slate-800">
              {groupName}
            </div>
            {fields.map((field) => (
              <ExtractionField
                key={field.name}
                field={field}
                extraction={extractionByName[field.name] || null}
                threshold={field.ai_threshold || schema.default_confidence_threshold}
                isActive={activeField === field.name}
                onFocus={() => handleFieldFocus(field.name)}
                onChange={handleFieldChange}
                onVerify={handleVerify}
              />
            ))}
          </div>
        ))}
      </div>

      {/* Save bar */}
      <div className="shrink-0 px-3 py-2 border-t border-slate-700 bg-slate-900/50">
        {saveError && (
          <p className="text-xs text-red-400 mb-1">{saveError}</p>
        )}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 flex-1">
            {dirtyCount > 0
              ? `${dirtyCount} unsaved change${dirtyCount !== 1 ? 's' : ''}`
              : 'No unsaved changes'}
          </span>
          <button
            disabled={dirtyCount === 0 || saving}
            onClick={handleSaveAll}
            className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded disabled:opacity-40 transition-colors"
          >
            {saving ? 'Saving…' : 'Save all'}
          </button>
        </div>
      </div>
    </div>
  )
}
