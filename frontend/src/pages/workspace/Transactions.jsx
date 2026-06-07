import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listTransactions } from '../../api/transactions'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

function overpaymentPct(paid, appraised) {
  if (!paid || !appraised || appraised === 0) return null
  return Math.round(((paid - appraised) / appraised) * 100)
}

export default function Transactions() {
  const { workspaceId } = useParams()
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listTransactions(workspaceId).then((r) => setTransactions(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  if (loading) return <LoadingSpinner />
  if (!transactions.length) return <EmptyState message="No transactions recorded yet." />

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-700">
            <th className="pb-3 pr-4">Type</th>
            <th className="pb-3 pr-4">Amount Paid</th>
            <th className="pb-3 pr-4">Appraised</th>
            <th className="pb-3 pr-4">Consideration</th>
            <th className="pb-3 pr-4">Date</th>
            <th className="pb-3">Instrument</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {transactions.map((t) => {
            const pct = overpaymentPct(t.amount_paid, t.appraised_value)
            return (
              <tr key={t.id} className={
                t.consideration === 'above_market' ? 'bg-red-950'
                : t.consideration === 'zero' ? 'bg-orange-950'
                : ''
              }>
                <td className="py-3 pr-4 capitalize text-white">{t.transaction_type}</td>
                <td className="py-3 pr-4 text-white">
                  {t.amount_paid != null ? `$${Number(t.amount_paid).toLocaleString()}` : '—'}
                </td>
                <td className="py-3 pr-4 text-slate-300">
                  {t.appraised_value != null ? `$${Number(t.appraised_value).toLocaleString()}` : '—'}
                </td>
                <td className="py-3 pr-4">
                  {t.consideration && <Badge label={t.consideration} />}
                  {pct !== null && (
                    <span className={`ml-2 text-xs ${pct > 100 ? 'text-red-400' : pct > 0 ? 'text-yellow-400' : 'text-green-400'}`}>
                      {pct > 0 ? '+' : ''}{pct}%
                    </span>
                  )}
                </td>
                <td className="py-3 pr-4 text-slate-400">{t.transaction_date || '—'}</td>
                <td className="py-3 text-slate-500 text-xs font-mono">{t.instrument_number || '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
