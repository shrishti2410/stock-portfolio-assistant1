/**
 * PnLChart — P&L visualization using plain HTML/CSS bar charts.
 *
 * Daily P&L as colored bars (green positive, red negative),
 * cumulative P&L line simulation, and per-strategy breakdown table.
 * No charting library required.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'

function fmtINR(n) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)
}

function fmtNum(n, dec = 2) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: dec }).format(n)
}

function pnlColor(val) {
  if (val > 0) return 'text-emerald-400'
  if (val < 0) return 'text-red-400'
  return 'text-slate-400'
}

function DailyBar({ date, pnl, maxAbs, isToday }) {
  const pct = maxAbs > 0 ? Math.abs(pnl) / maxAbs : 0
  const barHeight = Math.max(2, Math.round(pct * 80)) // max 80px

  const label = new Date(date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

  return (
    <div className="flex flex-col items-center gap-1 group cursor-default" style={{ minWidth: 32 }}>
      {/* Value tooltip on hover */}
      <div className="opacity-0 group-hover:opacity-100 transition-opacity text-[9px] tabular-nums font-medium whitespace-nowrap px-1.5 py-0.5 rounded bg-slate-700 border border-slate-600 text-slate-200 mb-0.5">
        {fmtINR(pnl)}
      </div>

      {/* Bar chart area: 80px total height, zero line in middle */}
      <div className="flex items-end justify-center" style={{ height: 44 }}>
        {pnl >= 0 ? (
          <div
            className={`w-6 rounded-t transition-all ${isToday ? 'bg-emerald-400' : 'bg-emerald-500/60'}`}
            style={{ height: barHeight }}
          />
        ) : (
          <div className="flex flex-col justify-start" style={{ height: 44 }}>
            <div style={{ height: 44 - barHeight }} />
            <div
              className={`w-6 rounded-b transition-all ${isToday ? 'bg-red-400' : 'bg-red-500/60'}`}
              style={{ height: barHeight }}
            />
          </div>
        )}
      </div>

      {/* Zero line */}
      <div className="w-6 h-px bg-slate-600" />

      {/* Date label */}
      <span className="text-[9px] text-slate-500 rotate-0 whitespace-nowrap">{label}</span>

      {isToday && (
        <span className="text-[8px] text-blue-400 font-bold">TODAY</span>
      )}
    </div>
  )
}

function CumulativeLine({ data }) {
  if (!data || data.length === 0) return null

  // Build cumulative values
  const cumulative = []
  let running = 0
  data.forEach(d => {
    running += d.pnl ?? 0
    cumulative.push({ date: d.date, cumulative: running })
  })

  const min = Math.min(...cumulative.map(d => d.cumulative))
  const max = Math.max(...cumulative.map(d => d.cumulative))
  const range = max - min || 1
  const height = 60

  // Build SVG polyline points
  const width = 100 // percentage
  const points = cumulative.map((d, i) => {
    const x = (i / Math.max(1, cumulative.length - 1)) * 100
    const y = height - ((d.cumulative - min) / range) * height
    return `${x},${y}`
  }).join(' ')

  const finalVal = cumulative[cumulative.length - 1]?.cumulative ?? 0
  const lineColor = finalVal >= 0 ? '#10b981' : '#ef4444'

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-slate-300">Cumulative P&L</p>
        <span className={`text-sm font-bold tabular-nums ${pnlColor(finalVal)}`}>{fmtINR(finalVal)}</span>
      </div>
      <div className="relative bg-slate-900/50 rounded-lg overflow-hidden" style={{ height }}>
        <svg
          viewBox={`0 0 100 ${height}`}
          preserveAspectRatio="none"
          className="w-full h-full"
          style={{ height }}
        >
          {/* Zero line */}
          {min < 0 && max >= 0 && (
            <line
              x1="0"
              x2="100"
              y1={height - ((0 - min) / range) * height}
              y2={height - ((0 - min) / range) * height}
              stroke="#334155"
              strokeWidth="0.5"
              strokeDasharray="2,2"
            />
          )}
          {/* Fill area */}
          {cumulative.length > 1 && (
            <polyline
              points={[
                `0,${height}`,
                ...cumulative.map((d, i) => {
                  const x = (i / Math.max(1, cumulative.length - 1)) * 100
                  const y = height - ((d.cumulative - min) / range) * height
                  return `${x},${y}`
                }),
                `100,${height}`,
              ].join(' ')}
              fill={finalVal >= 0 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)'}
              stroke="none"
            />
          )}
          {/* Line */}
          {cumulative.length > 1 && (
            <polyline
              points={points}
              fill="none"
              stroke={lineColor}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
        </svg>
        <div className="absolute top-1 left-2 text-[9px] text-slate-500">{fmtINR(max)}</div>
        <div className="absolute bottom-1 left-2 text-[9px] text-slate-500">{fmtINR(min)}</div>
      </div>
    </div>
  )
}

export default function PnLChart() {
  const [pnlData, setPnlData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchPnL = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/trading/pnl`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setPnlData(await res.json())
    } catch (err) {
      setError(err.message)
      // Use mock data for display
      setPnlData({
        today_pnl: 0,
        total_pnl: 0,
        win_rate: 0,
        today_trades: 0,
        daily_pnl: [],
        strategy_breakdown: [],
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchPnL() }, [fetchPnL])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
        <p className="text-slate-500 text-sm ml-3">Loading P&L data…</p>
      </div>
    )
  }

  const daily = pnlData?.daily_pnl ?? []
  const strategies = pnlData?.strategy_breakdown ?? []
  const today = new Date().toISOString().slice(0, 10)

  // Only show last 30 days
  const recentDaily = daily.slice(-30)
  const maxAbs = Math.max(1, ...recentDaily.map(d => Math.abs(d.pnl ?? 0)))

  const totalPnl = pnlData?.total_pnl ?? 0
  const todayPnl = pnlData?.today_pnl ?? 0

  return (
    <div className="space-y-5">

      {error && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-300">
          Could not load live data. Showing placeholder.
        </div>
      )}

      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className={`rounded-xl border p-3 ${todayPnl >= 0 ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
          <p className="text-[10px] text-slate-500 uppercase tracking-wide">Today</p>
          <p className={`text-lg font-bold tabular-nums mt-0.5 ${pnlColor(todayPnl)}`}>{fmtINR(todayPnl)}</p>
        </div>
        <div className={`rounded-xl border p-3 ${totalPnl >= 0 ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
          <p className="text-[10px] text-slate-500 uppercase tracking-wide">Total</p>
          <p className={`text-lg font-bold tabular-nums mt-0.5 ${pnlColor(totalPnl)}`}>{fmtINR(totalPnl)}</p>
        </div>
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3">
          <p className="text-[10px] text-slate-500 uppercase tracking-wide">Win Rate</p>
          <p className="text-lg font-bold tabular-nums text-white mt-0.5">
            {pnlData?.win_rate !== undefined ? `${fmtNum(pnlData.win_rate, 1)}%` : '—'}
          </p>
        </div>
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3">
          <p className="text-[10px] text-slate-500 uppercase tracking-wide">Total Trades</p>
          <p className="text-lg font-bold text-white mt-0.5">{pnlData?.total_trades ?? 0}</p>
        </div>
      </div>

      {/* Daily bar chart */}
      <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-semibold text-slate-200">Daily P&L — Last 30 Days</p>
          <div className="flex items-center gap-3 text-[10px] text-slate-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-2 bg-emerald-500/60 rounded-sm" /> Profit
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-2 bg-red-500/60 rounded-sm" /> Loss
            </span>
          </div>
        </div>

        {recentDaily.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-slate-500 text-sm">No daily P&L data yet</p>
            <p className="text-slate-600 text-xs mt-1">Data will appear once trades are closed</p>
          </div>
        ) : (
          <div className="overflow-x-auto pb-1">
            <div className="flex gap-1.5 min-w-0" style={{ minWidth: recentDaily.length * 38 }}>
              {recentDaily.map(d => (
                <DailyBar
                  key={d.date}
                  date={d.date}
                  pnl={d.pnl ?? 0}
                  maxAbs={maxAbs}
                  isToday={d.date === today}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Cumulative P&L line */}
      {recentDaily.length > 1 && (
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
          <CumulativeLine data={recentDaily} />
        </div>
      )}

      {/* Per-strategy breakdown */}
      <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700">
          <h3 className="text-sm font-semibold text-slate-200">Per-Strategy Breakdown</h3>
        </div>

        {strategies.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-slate-500 text-sm">No strategy data yet</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-700 text-[10px] text-slate-500 uppercase">
                  <th className="px-4 py-2.5 text-left">Strategy</th>
                  <th className="px-4 py-2.5 text-right">Trades</th>
                  <th className="px-4 py-2.5 text-right">Wins</th>
                  <th className="px-4 py-2.5 text-right">Win Rate</th>
                  <th className="px-4 py-2.5 text-right">Total P&L</th>
                  <th className="px-4 py-2.5 text-right">Avg P&L</th>
                  <th className="px-4 py-2.5 text-right">Best</th>
                  <th className="px-4 py-2.5 text-right">Worst</th>
                </tr>
              </thead>
              <tbody>
                {strategies.map((strat, i) => {
                  const winRate = strat.trades > 0 ? (strat.wins / strat.trades) * 100 : 0
                  const avgPnl = strat.trades > 0 ? strat.total_pnl / strat.trades : 0
                  return (
                    <tr key={i} className="border-b border-slate-700/30 last:border-0 hover:bg-slate-700/10">
                      <td className="px-4 py-2.5 font-medium text-slate-200">{strat.name}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-400">{strat.trades ?? 0}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-emerald-400">{strat.wins ?? 0}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        <span className={winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}>
                          {fmtNum(winRate, 1)}%
                        </span>
                      </td>
                      <td className={`px-4 py-2.5 text-right tabular-nums font-semibold ${pnlColor(strat.total_pnl)}`}>
                        {fmtINR(strat.total_pnl)}
                      </td>
                      <td className={`px-4 py-2.5 text-right tabular-nums ${pnlColor(avgPnl)}`}>
                        {fmtINR(avgPnl)}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-emerald-400">
                        {fmtINR(strat.best_trade)}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-red-400">
                        {fmtINR(strat.worst_trade)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr className="border-t border-slate-600 bg-slate-700/30 font-semibold">
                  <td className="px-4 py-2.5 text-xs text-slate-300">Total</td>
                  <td className="px-4 py-2.5 text-right text-xs tabular-nums text-slate-300">
                    {strategies.reduce((s, r) => s + (r.trades ?? 0), 0)}
                  </td>
                  <td className="px-4 py-2.5 text-right text-xs tabular-nums text-emerald-400">
                    {strategies.reduce((s, r) => s + (r.wins ?? 0), 0)}
                  </td>
                  <td className="px-4 py-2.5 text-right text-xs tabular-nums text-slate-300">—</td>
                  <td className={`px-4 py-2.5 text-right text-xs tabular-nums ${pnlColor(totalPnl)}`}>
                    {fmtINR(totalPnl)}
                  </td>
                  <td colSpan={3} />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

    </div>
  )
}
