/**
 * StockDetail — single IT stock detail page.
 * Route: /it-bear/stock/:symbol
 *
 * Header, returns, quarterly table, earnings countdown,
 * technical indicators, suggest strategy button.
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import ITBearNav from './ITBearNav'
import { fmtNum, fmtPct, pctColor, daysUntil, earningsDaysColor } from '../../utils/format'

const API_BASE = ''

function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
      <p className="text-slate-500 text-sm ml-3">Loading stock details…</p>
    </div>
  )
}

function BeatMissChip({ result }) {
  if (!result) return <span className="text-slate-600">—</span>
  const cfg = {
    beat: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    miss: 'bg-red-500/15 text-red-300 border-red-500/30',
    'in-line': 'bg-slate-700 text-slate-400 border-slate-600',
  }
  const label = { beat: 'Beat', miss: 'Miss', 'in-line': 'In-line' }
  const cls = cfg[result] ?? cfg['in-line']
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cls}`}>
      {label[result] ?? result}
    </span>
  )
}

function ReturnChip({ label, value }) {
  const cls = pctColor(value)
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3 text-center">
      <p className="text-[10px] text-slate-500 uppercase mb-1">{label}</p>
      <p className={`text-base font-bold tabular-nums ${cls}`}>{fmtPct(value, 2)}</p>
    </div>
  )
}

function TechItem({ label, value, valueClass = 'text-white' }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-700/40 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`text-xs font-semibold tabular-nums ${valueClass}`}>{value ?? '—'}</span>
    </div>
  )
}

export default function StockDetail() {
  const { symbol } = useParams()
  const navigate = useNavigate()
  const [stock, setStock] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchStock = useCallback(async () => {
    if (!symbol) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/it-bear/universe/${symbol}`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      setStock(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [symbol])

  useEffect(() => { fetchStock() }, [fetchStock])

  if (loading) {
    return (
      <div>
        <ITBearNav />
        <Spinner />
      </div>
    )
  }

  if (error || !stock) {
    return (
      <div>
        <ITBearNav />
        <main className="max-w-4xl mx-auto px-4 py-12">
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-8 text-center">
            <p className="text-red-400 text-sm mb-4">{error ?? 'Stock not found'}</p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={fetchStock}
                className="px-4 py-2 text-xs font-medium rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors"
              >
                Retry
              </button>
              <Link
                to="/it-bear/universe"
                className="text-blue-400 hover:text-blue-300 text-sm underline"
              >
                Back to Universe
              </Link>
            </div>
          </div>
        </main>
      </div>
    )
  }

  const quarters = stock.recent_quarters ?? []
  const tech = stock.technicals ?? {}
  const days = daysUntil(stock.next_earnings_date)
  const daysColor = earningsDaysColor(days)
  const isUS = stock.country === 'US'

  return (
    <div>
      <ITBearNav />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6">

        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 mb-4">
          <Link to="/it-bear" className="hover:text-slate-300 transition-colors">IT Bear</Link>
          <span>/</span>
          <Link to="/it-bear/universe" className="hover:text-slate-300 transition-colors">Universe</Link>
          <span>/</span>
          <span className="text-slate-300">{symbol}</span>
        </div>

        {/* Stock Header */}
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 mb-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl">{isUS ? '🇺🇸' : '🇮🇳'}</span>
                <h1 className="text-2xl font-black text-white">{stock.symbol}</h1>
                <span className="text-[10px] px-2 py-0.5 rounded border bg-slate-700 border-slate-600 text-slate-400">
                  {stock.tier ?? 'N/A'}
                </span>
              </div>
              <p className="text-sm text-slate-400">{stock.name}</p>
              <p className="text-[10px] text-slate-600 mt-0.5">{stock.segment}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-2xl font-black text-white tabular-nums">
                {isUS ? `$${fmtNum(stock.price, 2)}` : `₹${fmtNum(stock.price, 2)}`}
              </p>
              <p className={`text-sm font-semibold tabular-nums ${pctColor(stock.change_1d)}`}>
                {fmtPct(stock.change_1d, 2)} today
              </p>
            </div>
          </div>

          {/* Returns row */}
          <div className="grid grid-cols-3 gap-3 mt-4">
            <ReturnChip label="1D Return" value={stock.change_1d} />
            <ReturnChip label="5D Return" value={stock.change_5d} />
            <ReturnChip label="20D Return" value={stock.change_20d} />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">

          {/* Quarterly History */}
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700">
              <h2 className="text-sm font-semibold text-slate-200">Last 4 Quarters</h2>
            </div>
            {quarters.length === 0 ? (
              <div className="px-4 py-8 text-center text-slate-500 text-xs">
                No quarterly data available from backend yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[10px] text-slate-500 uppercase border-b border-slate-700/50 bg-slate-900/30">
                      <th className="px-3 py-2 text-left">Period</th>
                      <th className="px-3 py-2 text-right">Revenue</th>
                      <th className="px-3 py-2 text-right">YoY %</th>
                      <th className="px-3 py-2 text-right">EPS</th>
                      <th className="px-3 py-2 text-right">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quarters.slice(0, 4).map((q, i) => (
                      <tr key={i} className="border-b border-slate-700/40 last:border-0 hover:bg-slate-700/10">
                        <td className="px-3 py-2.5 text-slate-400">{q.period}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                          {q.revenue ? fmtNum(q.revenue, 0) : '—'}
                        </td>
                        <td className={`px-3 py-2.5 text-right tabular-nums ${
                          (q.revenue_yoy ?? 0) < 0 ? 'text-red-400' : 'text-emerald-400'
                        }`}>
                          {q.revenue_yoy !== undefined ? fmtPct(q.revenue_yoy, 1) : '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                          {q.eps !== undefined ? fmtNum(q.eps, 2) : '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <BeatMissChip result={q.beat_miss} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Right column: Earnings + Technicals */}
          <div className="flex flex-col gap-4">

            {/* Next Earnings Card */}
            <div className={`rounded-xl border p-4 ${
              days !== null && days >= 7 && days <= 21
                ? 'bg-amber-500/10 border-amber-500/30'
                : 'bg-slate-800/80 border-slate-700'
            }`}>
              <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">Next Earnings</p>
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-white">{stock.next_earnings_date ?? 'Not scheduled'}</p>
                {days !== null && (
                  <span className={`text-xl font-black tabular-nums ${daysColor}`}>
                    {days === 0 ? 'Today' : days < 0 ? 'Past' : `${days}d`}
                  </span>
                )}
              </div>
              {days !== null && days >= 7 && days <= 21 && (
                <p className="text-[10px] text-amber-400 mt-1.5">
                  Pre-earnings sweet spot — ideal window for put options
                </p>
              )}
            </div>

            {/* Technical Indicators */}
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 flex-1">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Technical Indicators</h3>
              <TechItem
                label="RSI (14)"
                value={tech.rsi !== undefined ? fmtNum(tech.rsi, 1) : '—'}
                valueClass={
                  tech.rsi < 30 ? 'text-emerald-400'
                  : tech.rsi > 70 ? 'text-red-400'
                  : 'text-slate-300'
                }
              />
              <TechItem
                label="Above 50 DMA"
                value={tech.above_50dma === true ? 'Yes' : tech.above_50dma === false ? 'No' : '—'}
                valueClass={tech.above_50dma === true ? 'text-emerald-400' : 'text-red-400'}
              />
              <TechItem
                label="Above 200 DMA"
                value={tech.above_200dma === true ? 'Yes' : tech.above_200dma === false ? 'No' : '—'}
                valueClass={tech.above_200dma === true ? 'text-emerald-400' : 'text-red-400'}
              />
              <TechItem
                label="Recent Breakdown"
                value={tech.recent_breakdown === true ? 'Yes — Bearish' : tech.recent_breakdown === false ? 'No' : '—'}
                valueClass={tech.recent_breakdown === true ? 'text-red-400 font-bold' : 'text-slate-400'}
              />
              {tech.macd_signal !== undefined && (
                <TechItem
                  label="MACD Signal"
                  value={tech.macd_signal}
                  valueClass={tech.macd_signal === 'Bearish' ? 'text-red-400' : 'text-emerald-400'}
                />
              )}
            </div>
          </div>
        </div>

        {/* Suggest Strategy CTA */}
        <div className="flex items-center justify-between p-5 bg-red-500/10 border border-red-500/30 rounded-xl">
          <div>
            <p className="text-sm font-semibold text-red-300">Build a Bearish Strategy</p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Get AI-suggested put options, spreads, or collars for {symbol}
            </p>
          </div>
          <button
            onClick={() => navigate(`/it-bear/strategy-builder/${symbol}`)}
            className="px-5 py-2.5 text-sm font-bold rounded-xl border bg-red-500/20 border-red-500/40 text-red-300 hover:bg-red-500/30 transition-colors shrink-0"
          >
            Suggest Strategy
          </button>
        </div>
      </main>
    </div>
  )
}
