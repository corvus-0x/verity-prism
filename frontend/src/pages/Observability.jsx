import { useState, useEffect } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  getAutomationRate,
  getClassificationDetails,
  getCurrentProcessing,
  getVolume,
} from '../api/observability'
import LoadingSpinner from '../components/shared/LoadingSpinner'

function StatCard({ label, value, sub, color = 'text-white' }) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
      <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-slate-500 text-xs mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Observability() {
  const [rate, setRate] = useState(null)
  const [volume, setVolume] = useState(null)
  const [details, setDetails] = useState(null)
  const [current, setCurrent] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      getAutomationRate(),
      getVolume(30),
      getClassificationDetails(),
      getCurrentProcessing(),
    ]).then(([rateRes, volRes, detailRes, curRes]) => {
      if (rateRes.status === 'fulfilled') setRate(rateRes.value.data)
      if (volRes.status === 'fulfilled') setVolume(volRes.value.data)
      if (detailRes.status === 'fulfilled') setDetails(detailRes.value.data)
      if (curRes.status === 'fulfilled') setCurrent(curRes.value.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />

  const automationPct = rate ? Math.round(rate.automation_rate * 100) : 0

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
      <div>
        <h1 className="text-white text-xl font-semibold">Observability</h1>
        <p className="text-slate-400 text-sm mt-0.5">Extraction quality metrics — operator view</p>
      </div>

      {/* ── Automation Rate ───────────────────────────────── */}
      {rate && (
        <section>
          <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
            Automation Rate
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard
              label="Automation Rate"
              value={`${automationPct}%`}
              sub="straight-through"
              color={automationPct >= 80 ? 'text-green-400' : automationPct >= 60 ? 'text-yellow-400' : 'text-red-400'}
            />
            <StatCard label="Total Documents" value={rate.total ?? '—'} />
            <StatCard label="Needs Review" value={rate.needs_review ?? '—'} color="text-yellow-400" />
            <StatCard label="Failed" value={rate.failed ?? '—'} color={rate.failed > 0 ? 'text-red-400' : 'text-slate-400'} />
          </div>
        </section>
      )}

      {/* ── Current Processing ───────────────────────────── */}
      {current && (
        <section>
          <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
            Current Processing
          </h2>
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="Pending" value={current.pending} />
            <StatCard label="Review Queue" value={current.needs_review} color={current.needs_review > 0 ? 'text-yellow-400' : 'text-slate-400'} />
            <StatCard label="Total Active" value={current.total_active} />
          </div>
        </section>
      )}

      {/* ── Volume Trend ──────────────────────────────────── */}
      {volume?.days && (
        <section>
          <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
            Inbound / Completed — Last 30 Days
          </h2>
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={volume.days} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  tickFormatter={(d) => d.slice(5)}
                  interval={4}
                />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6 }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#e2e8f0' }}
                />
                <Line type="monotone" dataKey="inbound" stroke="#3b82f6" strokeWidth={2} dot={false} name="Inbound" />
                <Line type="monotone" dataKey="completed" stroke="#22c55e" strokeWidth={2} dot={false} name="Completed" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* ── Classification Details ───────────────────────── */}
      {details?.schemas?.length > 0 && (
        <section>
          <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
            Extraction Quality by Schema
          </h2>
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={Math.max(160, details.schemas.length * 36)}>
              <BarChart
                data={details.schemas}
                layout="vertical"
                margin={{ top: 4, right: 40, left: 80, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis type="category" dataKey="document_type" tick={{ fill: '#94a3b8', fontSize: 11 }} width={75} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6 }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#e2e8f0' }}
                  formatter={(v) => `${Math.round(v * 100)}%`}
                />
                <Bar dataKey="avg_ai_confidence" name="AI Confidence" fill="#3b82f6" radius={[0, 3, 3, 0]} />
                <Bar dataKey="avg_ocr_confidence" name="OCR Confidence" fill="#8b5cf6" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-700">
                    <th className="pb-2 font-medium">Schema</th>
                    <th className="pb-2 font-medium text-right">Docs</th>
                    <th className="pb-2 font-medium text-right">AI Conf</th>
                    <th className="pb-2 font-medium text-right">OCR Conf</th>
                    <th className="pb-2 font-medium text-right">Retry Rate</th>
                    <th className="pb-2 font-medium text-right">Correction Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {details.schemas.map((s) => (
                    <tr key={s.document_type}>
                      <td className="py-1.5 text-white font-medium">{s.document_type}</td>
                      <td className="py-1.5 text-slate-400 text-right">{s.total_documents}</td>
                      <td className="py-1.5 text-right">
                        <span className={s.avg_ai_confidence >= 0.85 ? 'text-green-400' : s.avg_ai_confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}>
                          {Math.round(s.avg_ai_confidence * 100)}%
                        </span>
                      </td>
                      <td className="py-1.5 text-right">
                        <span className={s.avg_ocr_confidence >= 0.85 ? 'text-green-400' : s.avg_ocr_confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}>
                          {Math.round(s.avg_ocr_confidence * 100)}%
                        </span>
                      </td>
                      <td className="py-1.5 text-slate-400 text-right">{Math.round(s.retry_rate * 100)}%</td>
                      <td className="py-1.5 text-slate-400 text-right">{Math.round(s.correction_rate * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
