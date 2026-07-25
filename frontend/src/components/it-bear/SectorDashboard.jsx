/**
 * SectorDashboard — IT-Bear landing page.
 *
 * Thesis score, macro indicators, NIFTY IT vs NIFTY 50 returns,
 * sector heatmap of all India IT stocks, and quick actions.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import ITBearNav from './ITBearNav'
import { fmtNum, fmtPct, pctColor } from '../../utils/format'

const API_BASE = ''

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
      <p className="text-slate-500 text-sm ml-3">Loading sector data…</p>
    </div>
  )
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center my-6">
      <p className="text-red-400 text-sm mb-3">{message}</p>
      <button
        onClick={onRetry}
        className="px-4 py-2 text-xs font-medium rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors"
      >
        Retry
      </button>
    </div>
  )
}

function ThesisScoreCard({ score }) {
  const color = score >= 70
    ? 'text-emerald-400'
    : score >= 40
    ? 'text-amber-400'
    : 'text-red-400'

  const bg = score >= 70
    ? 'bg-emerald-500/10 border-emerald-500/30'
    : score >= 40
    ? 'bg-amber-500/10 border-amber-500/30'
    : 'bg-red-500/10 border-red-500/30'

  const barColor = score >= 70
    ? 'bg-emerald-500'
    : score >= 40
    ? 'bg-amber-500'
    : 'bg-red-500'

  const label = score >= 70
    ? 'Thesis Validated — strong bearish case'
    : score >= 40
    ? 'Thesis Neutral — mixed signals'
    : 'Thesis Weak — bearish case not confirmed'

  return (
    <div className={`rounded-xl border p-6 ${bg}`}>
      <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">IT-Bear Thesis Score</p>
      <div className="flex items-end gap-4 mb-3">
        <span className={`text-5xl font-black tabular-nums leading-none ${color}`}>
          {score ?? '—'}
        </span>
        <span className="text-slate-500 text-sm pb-1">/ 100</span>
      </div>
      <div className="h-2 bg-slate-700/60 rounded-full mb-3">
        <div
          className={`h-2 rounded-full transition-all duration-700 ${barColor}`}
          style={{ width: `${Math.min(100, score ?? 0)}%` }}
        />
      </div>
      <p className={`text-xs font-medium ${color}`}>{label}</p>
    </div>
  )
}

function MacroCard({ label, value, sub, valueClass = 'text-white' }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-base font-bold tabular-nums ${valueClass}`}>{value ?? '—'}</p>
      {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
    </div>
  )
}

function ReturnChip({ label, value }) {
  const cls = value > 0 ? 'text-emerald-400' : value < 0 ? 'text-red-400' : 'text-slate-400'
  return (
    <div className="text-center">
      <p className="text-[10px] text-slate-500 mb-0.5">{label}</p>
      <p className={`text-sm font-bold tabular-nums ${cls}`}>{fmtPct(value, 1)}</p>
    </div>
  )
}

function HeatmapRow({ stock }) {
  // Backend returns change_pct_1d / change_pct_5d / change_pct_20d
  const chg1d = stock.change_pct_1d ?? stock.change_1d ?? 0
  const chg5d = stock.change_pct_5d ?? stock.change_5d ?? 0
  const chg20d = stock.change_pct_20d ?? stock.change_20d ?? 0
  const rsi = stock.rsi ?? null
  const above50 = stock.above_50dma

  const cellCls = (v) => v > 0
    ? 'text-emerald-400 bg-emerald-500/5'
    : v < 0
    ? 'text-red-400 bg-red-500/5'
    : 'text-slate-400'

  return (
    <tr className="border-b border-slate-700/40 last:border-0 hover:bg-slate-700/20 transition-colors">
      <td className="px-3 py-2">
        <span className="text-xs font-bold text-white">{stock.symbol}</span>
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-xs text-slate-300">
        {fmtNum(stock.price, 2)}
      </td>
      <td className={`px-3 py-2 text-right tabular-nums text-xs rounded ${cellCls(chg1d)}`}>
        {fmtPct(chg1d, 1)}
      </td>
      <td className={`px-3 py-2 text-right tabular-nums text-xs rounded ${cellCls(chg5d)}`}>
        {fmtPct(chg5d, 1)}
      </td>
      <td className={`px-3 py-2 text-right tabular-nums text-xs rounded ${cellCls(chg20d)}`}>
        {fmtPct(chg20d, 1)}
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-xs">
        <span className={
          rsi === null ? 'text-slate-500'
          : rsi < 30 ? 'text-emerald-400 font-semibold'
          : rsi > 70 ? 'text-red-400 font-semibold'
          : 'text-slate-300'
        }>
          {rsi !== null ? fmtNum(rsi, 1) : '—'}
        </span>
      </td>
      <td className="px-3 py-2 text-center text-xs">
        {above50 === true
          ? <span className="text-emerald-400 font-bold">Y</span>
          : above50 === false
          ? <span className="text-red-400 font-bold">N</span>
          : <span className="text-slate-500">—</span>
        }
      </td>
    </tr>
  )
}

export default function SectorDashboard() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const fetchHealth = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/it-bear/sector-health`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      setHealth(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchHealth() }, [fetchHealth])

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(fetchHealth, 30000)
    return () => clearInterval(id)
  }, [fetchHealth])

  // Backend response structure:
  //   { summary: { thesis_score, regime, key_signals, ... },
  //     nifty_it_vs_nifty50: { nifty_it_pct_5d, nifty50_pct_5d, ... },
  //     macro: { usd_inr: {value}, india_vix, us_10y_yield, xlk_trend, igv_trend },
  //     heatmap: [{ symbol, change_pct_1d, change_pct_5d, change_pct_20d, ... }] }
  const summary = health?.summary ?? {}
  const macroRaw = health?.macro ?? {}
  const relPerf = health?.nifty_it_vs_nifty50 ?? {}
  const heatmap = health?.heatmap ?? []
  const score = summary.thesis_score ?? health?.thesis_score ?? 0

  // Find NIFTYIT in heatmap to extract spot price
  const niftyItRow = heatmap.find(s => s.symbol === 'NIFTYIT')
  const niftyItSpot = niftyItRow?.price

  // Flatten macro for cards
  const macro = {
    nifty_it_spot: niftyItSpot,
    india_vix: macroRaw.india_vix,
    usdinr: macroRaw.usd_inr?.value ?? macroRaw.usd_inr,
    us_10y: macroRaw.us_10y_yield,
    xlk_trend: macroRaw.xlk_trend,
  }

  // Returns for both indices
  const niftyItReturns = {
    ret_5d: relPerf.nifty_it_pct_5d,
    ret_20d: relPerf.nifty_it_pct_20d,
    ret_90d: relPerf.nifty_it_pct_90d,
  }
  const nifty50Returns = {
    ret_5d: relPerf.nifty50_pct_5d,
    ret_20d: relPerf.nifty50_pct_20d,
    ret_90d: relPerf.nifty50_pct_90d,
  }
  const relativeStrength = relPerf.relative_strength

  // Sort by weakest 20d first (most bearish at top) — use change_pct_20d
  const sortedHeatmap = [...heatmap].sort(
    (a, b) => (a.change_pct_20d ?? 0) - (b.change_pct_20d ?? 0)
  )

  return (
    <div>
      <ITBearNav />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-black text-white">IT Sector — Bear Thesis</h1>
            <p className="text-slate-500 text-xs mt-1">
              1-year bearish thesis on Indian + US IT services. Paper trading active.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Link
              to="/it-bear/earnings"
              className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20 transition-colors"
            >
              Earnings Calendar
            </Link>
            <Link
              to="/it-bear/scanner"
              className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25 transition-colors"
            >
              Run Scanner
            </Link>
            <Link
              to="/trading/positions"
              className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
            >
              All Positions
            </Link>
          </div>
        </div>

        {loading && <Spinner />}
        {!loading && error && <ErrorState message={error} onRetry={fetchHealth} />}

        {!loading && !error && (
          <>
            {/* Thesis Score + Macro Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
              <div className="lg:col-span-1">
                <ThesisScoreCard score={score} />
              </div>
              <div className="lg:col-span-2 grid grid-cols-2 sm:grid-cols-3 gap-3">
                <MacroCard
                  label="NIFTY IT Spot"
                  value={macro.nifty_it_spot ? `${fmtNum(macro.nifty_it_spot, 0)}` : '—'}
                  sub="NSE NIFTY IT Index"
                  valueClass="text-white"
                />
                <MacroCard
                  label="India VIX"
                  value={macro.india_vix ? fmtNum(macro.india_vix, 2) : '—'}
                  sub={macro.india_vix > 20 ? 'High volatility' : macro.india_vix > 15 ? 'Moderate' : 'Low volatility'}
                  valueClass={macro.india_vix > 20 ? 'text-red-400' : macro.india_vix > 15 ? 'text-amber-400' : 'text-emerald-400'}
                />
                <MacroCard
                  label="USD/INR"
                  value={macro.usdinr ? fmtNum(macro.usdinr, 2) : '—'}
                  sub="Spot rate"
                  valueClass={macro.usdinr > 85 ? 'text-red-400' : 'text-slate-300'}
                />
                <MacroCard
                  label="US 10Y Yield"
                  value={macro.us_10y ? `${fmtNum(macro.us_10y, 2)}%` : '—'}
                  sub="Treasury yield"
                  valueClass={macro.us_10y > 4.5 ? 'text-red-400' : 'text-amber-400'}
                />
                <MacroCard
                  label="XLK Trend"
                  value={macro.xlk_trend ?? '—'}
                  sub="US Tech ETF"
                  valueClass={
                    /bear/i.test(macro.xlk_trend ?? '') ? 'text-red-400'
                    : /bull/i.test(macro.xlk_trend ?? '') ? 'text-emerald-400'
                    : 'text-amber-400'
                  }
                />
                <MacroCard
                  label="Thesis Score"
                  value={`${score}/100`}
                  sub={score >= 70 ? 'Validated' : score >= 40 ? 'Neutral' : 'Weak'}
                  valueClass={score >= 70 ? 'text-emerald-400' : score >= 40 ? 'text-amber-400' : 'text-red-400'}
                />
              </div>
            </div>

            {/* NIFTY IT vs NIFTY 50 Returns */}
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 mb-6">
              <h2 className="text-sm font-semibold text-slate-200 mb-4">NIFTY IT vs NIFTY 50 — Relative Performance</h2>
              <div className="grid grid-cols-2 gap-6">
                {/* NIFTY IT */}
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-3 font-semibold">NIFTY IT</p>
                  <div className="flex gap-6">
                    <ReturnChip label="5D" value={niftyItReturns.ret_5d} />
                    <ReturnChip label="20D" value={niftyItReturns.ret_20d} />
                    <ReturnChip label="90D" value={niftyItReturns.ret_90d} />
                  </div>
                </div>
                {/* NIFTY 50 */}
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-3 font-semibold">NIFTY 50</p>
                  <div className="flex gap-6">
                    <ReturnChip label="5D" value={nifty50Returns.ret_5d} />
                    <ReturnChip label="20D" value={nifty50Returns.ret_20d} />
                    <ReturnChip label="90D" value={nifty50Returns.ret_90d} />
                  </div>
                </div>
              </div>
              {/* Relative strength row */}
              {relativeStrength !== undefined && relativeStrength !== null && (
                <div className="mt-4 pt-4 border-t border-slate-700 flex items-center gap-3">
                  <span className="text-xs text-slate-500">Relative Strength (IT vs N50, 20d):</span>
                  <span className={`text-sm font-bold tabular-nums ${
                    relativeStrength < 0 ? 'text-red-400' : 'text-emerald-400'
                  }`}>
                    {fmtPct(relativeStrength, 2)}
                  </span>
                  {relativeStrength < 0 && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30">
                      IT underperforming — thesis supported
                    </span>
                  )}
                </div>
              )}

              {/* Key signals from backend summary */}
              {summary.key_signals?.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 font-semibold">Key Signals</p>
                  <ul className="space-y-1">
                    {summary.key_signals.map((sig, i) => (
                      <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                        <span className="text-red-400 mt-0.5">▸</span>
                        <span>{sig}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Sector Heatmap */}
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden mb-6">
              <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-200">
                  India IT Sector Heatmap
                  <span className="ml-2 text-[10px] text-slate-500">Sorted by weakest first</span>
                </h2>
                <Link
                  to="/it-bear/universe"
                  className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  Full Universe
                </Link>
              </div>
              <div className="overflow-x-auto">
                {sortedHeatmap.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-slate-500 text-sm">No heatmap data available.</p>
                    <p className="text-slate-600 text-xs mt-1">Backend may not be returning sector health data yet.</p>
                  </div>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-[10px] text-slate-500 uppercase border-b border-slate-700 bg-slate-900/40">
                        <th className="px-3 py-2 text-left">Symbol</th>
                        <th className="px-3 py-2 text-right">Price</th>
                        <th className="px-3 py-2 text-right">1D %</th>
                        <th className="px-3 py-2 text-right">5D %</th>
                        <th className="px-3 py-2 text-right">20D %</th>
                        <th className="px-3 py-2 text-right">RSI</th>
                        <th className="px-3 py-2 text-center">Above 50DMA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedHeatmap.map(stock => (
                        <HeatmapRow key={stock.symbol} stock={stock} />
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Link
                to="/it-bear/earnings"
                className="flex items-center gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl hover:bg-amber-500/15 transition-colors group"
              >
                <div className="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center shrink-0">
                  <span className="text-amber-300 font-bold text-sm">E</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-amber-300">Earnings Calendar</p>
                  <p className="text-[10px] text-slate-500">Pre-earnings sweet spot trades</p>
                </div>
              </Link>
              <Link
                to="/it-bear/scanner"
                className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl hover:bg-red-500/15 transition-colors group"
              >
                <div className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center shrink-0">
                  <span className="text-red-300 font-bold text-sm">S</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-red-300">Run Scanner Now</p>
                  <p className="text-[10px] text-slate-500">Evaluate all 5 IT-bear signals</p>
                </div>
              </Link>
              <Link
                to="/trading/positions"
                className="flex items-center gap-3 p-4 bg-slate-800/80 border border-slate-700 rounded-xl hover:bg-slate-700/50 transition-colors group"
              >
                <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center shrink-0">
                  <span className="text-slate-300 font-bold text-sm">P</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-300">View All Positions</p>
                  <p className="text-[10px] text-slate-500">Open P&L, paper trades</p>
                </div>
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
