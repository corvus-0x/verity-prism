import { useState, useEffect } from 'react'
import AppShell from '../components/layout/AppShell'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import { listSchemas } from '../api/schemas'

const STRATEGY_LABEL = {
  claude: 'AI extraction',
  xml_direct: 'XML direct',
}

const VERTICAL_LABEL = {
  general: 'General',
  fraud: 'Fraud Investigation',
  insurance: 'Insurance',
}

function FieldRow({ field }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-slate-700/50 last:border-0">
      <span className="text-slate-200 text-sm font-mono w-72 shrink-0">{field.name}</span>
      <span className="text-slate-500 text-xs w-20 shrink-0 pt-0.5">{field.type}</span>
      <span className="text-slate-400 text-sm">{field.description}</span>
      {field.required && (
        <span className="ml-auto shrink-0 text-xs text-amber-400 font-medium">required</span>
      )}
    </div>
  )
}

function SchemaCard({ schema }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left px-5 py-4 flex items-center gap-4 hover:bg-slate-700/40 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-white font-semibold">{schema.display_name}</span>
            <span className="text-slate-500 text-xs font-mono">{schema.document_type}</span>
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-slate-400 text-xs">{schema.field_count} fields</span>
            <span className="text-slate-600 text-xs">·</span>
            <span className="text-slate-400 text-xs">{STRATEGY_LABEL[schema.parse_strategy] ?? schema.parse_strategy}</span>
            <span className="text-slate-600 text-xs">·</span>
            <span className="text-slate-400 text-xs">confidence ≥ {Math.round(schema.default_confidence_threshold * 100)}%</span>
          </div>
        </div>
        <span className="text-slate-500 text-sm shrink-0">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t border-slate-700 px-5 py-3">
          {schema.fields.length === 0 ? (
            <p className="text-slate-500 text-sm py-2">No fields defined.</p>
          ) : (
            <div>
              <div className="flex items-start gap-3 pb-2 mb-1 border-b border-slate-700">
                <span className="text-slate-500 text-xs font-medium w-72 shrink-0">FIELD</span>
                <span className="text-slate-500 text-xs font-medium w-20 shrink-0">TYPE</span>
                <span className="text-slate-500 text-xs font-medium">DESCRIPTION</span>
              </div>
              {schema.fields.map((f) => (
                <FieldRow key={f.name} field={f} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function SchemaLibrary() {
  const [schemas, setSchemas] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listSchemas()
      .then((res) => setSchemas(res.data))
      .finally(() => setLoading(false))
  }, [])

  const grouped = schemas.reduce((acc, s) => {
    const key = s.vertical ?? 'general'
    if (!acc[key]) acc[key] = []
    acc[key].push(s)
    return acc
  }, {})

  return (
    <AppShell>
      <div className="flex-1 p-8 max-w-4xl mx-auto w-full">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white">Schema Library</h1>
          <p className="text-slate-400 text-sm mt-1">
            Document types the platform knows how to extract, and every field they produce.
          </p>
        </div>

        {loading ? <LoadingSpinner /> : (
          <div className="space-y-8">
            {Object.entries(grouped).map(([vertical, items]) => (
              <div key={vertical}>
                <h2 className="text-slate-400 text-xs font-semibold uppercase tracking-widest mb-3">
                  {VERTICAL_LABEL[vertical] ?? vertical}
                </h2>
                <div className="space-y-2">
                  {items.map((s) => <SchemaCard key={s.id} schema={s} />)}
                </div>
              </div>
            ))}
            {schemas.length === 0 && (
              <p className="text-slate-400 text-center py-12">No schemas loaded yet.</p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
