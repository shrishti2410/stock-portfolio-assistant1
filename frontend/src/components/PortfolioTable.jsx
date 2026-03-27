/**
 * PortfolioTable — tabular view of all holdings.
 *
 * Props:
 *   data     Array of dashboard rows
 *   loading  Boolean — show skeleton rows while true
 */
export default function PortfolioTable({ data, loading }) {
  const fmt = (n) =>
    new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)

  const headers = [
    { label: 'Stock',         align: 'text-left'  },
    { label: 'Qty',           align: 'text-right' },
    { label: 'Avg Price',     align: 'text-right' },
    { label: 'Current Price', align: 'text-right' },
    { label: 'P&L (₹)',       align: 'text-right' },
    { label: 'P&L %',         align: 'text-right' },
  ]

  if (loading) {
    return (
      <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-700">
          <h2 className="text-base font-semibold text-slate-200">Holdings</h2>
        </div>
        <div className="p-6 text-slate-500 text-sm text-center animate-pulse">
          Loading portfolio...
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-base font-semibold text-slate-200">Holdings</h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
              {headers.map((h) => (
                <th
                  key={h.label}
                  className={`px-4 py-3 text-xs uppercase tracking-wider text-slate-500 font-medium ${h.align}`}
                >
                  {h.label}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {data.map((row, i) => {
              const isPos   = row.pnl >= 0
              const pnlColor = isPos ? 'text-emerald-400' : 'text-red-400'
              const rowBg   = i % 2 === 0 ? '' : 'bg-slate-700/20'

              return (
                <tr
                  key={row.symbol}
                  className={`border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors ${rowBg}`}
                >
                  {/* Stock */}
                  <td className="px-4 py-3 text-left">
                    <span className="font-semibold text-white tracking-wide">
                      {row.symbol}
                    </span>
                  </td>

                  {/* Qty */}
                  <td className="px-4 py-3 text-right text-slate-300 tabular-nums">
                    {row.quantity}
                  </td>

                  {/* Avg Price */}
                  <td className="px-4 py-3 text-right text-slate-300 tabular-nums">
                    ₹{fmt(row.avg_price)}
                  </td>

                  {/* Current Price */}
                  <td className="px-4 py-3 text-right text-slate-200 tabular-nums font-medium">
                    ₹{fmt(row.current_price)}
                  </td>

                  {/* P&L ₹ */}
                  <td className={`px-4 py-3 text-right tabular-nums font-medium ${pnlColor}`}>
                    {isPos ? '+' : ''}₹{fmt(row.pnl)}
                  </td>

                  {/* P&L % */}
                  <td className={`px-4 py-3 text-right tabular-nums font-semibold ${pnlColor}`}>
                    {isPos ? '+' : ''}{row.pnl_pct.toFixed(2)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
