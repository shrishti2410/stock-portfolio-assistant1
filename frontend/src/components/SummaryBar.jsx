/**
 * SummaryBar — top strip showing portfolio-level aggregate stats.
 *
 * Props:
 *   data  Array of dashboard rows (from /api/dashboard)
 *
 * Computes on the fly:
 *   Total invested value  = sum(avg_price   * quantity)
 *   Total current value   = sum(current_price * quantity)
 *   Total P&L (₹)         = sum(pnl)
 *   Total P&L %           = (total_pnl / total_invested) * 100
 */
export default function SummaryBar({ data }) {
  const totalInvested = data.reduce((s, r) => s + r.avg_price * r.quantity, 0)
  const totalCurrent  = data.reduce((s, r) => s + r.current_price * r.quantity, 0)
  const totalPnl      = data.reduce((s, r) => s + r.pnl, 0)
  const totalPnlPct   = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0

  const isPositive = totalPnl >= 0
  const pnlColor   = isPositive ? 'text-emerald-400' : 'text-red-400'
  const pnlBg      = isPositive ? 'bg-emerald-400/10' : 'bg-red-400/10'

  const fmt = (n) =>
    new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)

  const stats = [
    {
      label: 'Portfolio Value',
      value: `₹${fmt(totalCurrent)}`,
      color: 'text-white',
    },
    {
      label: 'Invested',
      value: `₹${fmt(totalInvested)}`,
      color: 'text-slate-300',
    },
    {
      label: 'Total P&L',
      value: `${isPositive ? '+' : ''}₹${fmt(totalPnl)}`,
      color: pnlColor,
    },
    {
      label: 'P&L %',
      value: `${isPositive ? '+' : ''}${totalPnlPct.toFixed(2)}%`,
      color: pnlColor,
    },
    {
      label: 'Holdings',
      value: data.length,
      color: 'text-slate-300',
    },
  ]

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 mb-6">
      <div className="flex flex-wrap gap-4 justify-between items-center">
        {stats.map((s) => (
          <div key={s.label} className="flex flex-col items-center min-w-[110px]">
            <span className="text-xs uppercase tracking-widest text-slate-500 mb-1">
              {s.label}
            </span>
            <span className={`text-xl font-semibold tabular-nums ${s.color}`}>
              {s.value}
            </span>
          </div>
        ))}

        {/* Compact P&L pill — visible only on wider screens */}
        <div
          className={`hidden sm:flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${pnlColor} ${pnlBg}`}
        >
          <span>{isPositive ? '▲' : '▼'}</span>
          <span>
            {isPositive ? 'Portfolio up' : 'Portfolio down'}{' '}
            {Math.abs(totalPnlPct).toFixed(2)}%
          </span>
        </div>
      </div>
    </div>
  )
}
