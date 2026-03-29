/**
 * AnalysisHistory — shows all saved AI analyses with filtering.
 * Tracks how recommendations change over time per stock.
 */

import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'

const REC_STYLE = {
  Buy:  'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  Sell: 'bg-red-500/20 text-red-300 border-red-500/40',
  Hold: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
}

export default function AnalysisHistory() {
  const [searchParams] = useSearchParams()
  const filterSymbol = searchParams.get('symbol') || ''

  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [symbolFilter, setSymbolFilter] = useState(filterSymbol)

  useEffect(() => {
    fetchHistory()
  }, [filterSymbol])

  async function fetchHistory() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterSymbol) params.set('symbol', filterSymbol)
      params.set('limit', '100')
      const res = await fetch(`${API_BASE}/api/history?${params}`)
      if (res.ok) setHistory(await res.json())
    } catch { /* ignore */ }
    setLoading(false)
  }

  function handleFilter() {
    const trimmed = symbolFilter.trim().toUpperCase()
    if (trimmed) {
      window.location.href = `/history?symbol=${trimmed}`
    } else {
      window.location.href = '/history'
    }
  }

  // Group by symbol for summary
  const symbolGroups = {}
  history.forEach(h => {
    if (!symbolGroups[h.symbol]) symbolGroups[h.symbol] = []
    symbolGroups[h.symbol].push(h)
  })

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Analysis History</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Track how AI recommendations change over time
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={symbolFilter}
            onChange={(e) => setSymbolFilter(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleFilter()}
            placeholder="Filter by symbol…"
            className="w-36 px-2 py-1.5 rounded-lg bg-slate-800 border border-slate-700
                       text-xs text-slate-200 placeholder-slate-500 focus:outline-none
                       focus:border-slate-500"
          />
          <button
            onClick={handleFilter}
            className="px-3 py-1.5 rounded-lg text-xs font-medium border bg-slate-700
                       border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
          >
            Filter
          </button>
          {filterSymbol && (
            <Link
              to="/history"
              className="px-2 py-1.5 text-xs text-slate-500 hover:text-slate-300"
            >
              Clear
            </Link>
          )}
        </div>
      </div>

      {loading ? (
        <p className="text-slate-500 text-sm animate-pulse">Loading…</p>
      ) : history.length === 0 ? (
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-8 text-center">
          <p className="text-slate-400 text-sm mb-2">No analysis history yet.</p>
          <p className="text-slate-500 text-xs">
            Run "AI Analysis" on any stock from the dashboard — results are saved automatically.
          </p>
          <Link
            to="/"
            className="inline-block mt-4 text-emerald-400 hover:text-emerald-300 text-sm font-medium"
          >
            Go to Dashboard →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Summary cards if viewing all symbols */}
          {!filterSymbol && Object.keys(symbolGroups).length > 1 && (
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 mb-4">
              <h2 className="text-xs font-semibold text-slate-400 mb-2">Stocks Analyzed</h2>
              <div className="flex flex-wrap gap-2">
                {Object.entries(symbolGroups).map(([sym, analyses]) => {
                  const latest = analyses[0]
                  const recStyle = REC_STYLE[latest.recommendation] ?? REC_STYLE.Hold
                  return (
                    <Link
                      key={sym}
                      to={`/history?symbol=${sym}`}
                      className={`px-2 py-1 rounded border text-xs font-medium ${recStyle}
                                  hover:opacity-80 transition-opacity`}
                    >
                      {sym} ({analyses.length})
                    </Link>
                  )
                })}
              </div>
            </div>
          )}

          {/* Individual analysis entries */}
          {history.map((entry) => {
            const recStyle = REC_STYLE[entry.recommendation] ?? REC_STYLE.Hold
            const date = new Date(entry.created_at)

            // Parse screening data if available
            let screening = null
            try {
              if (entry.screening_data) screening = JSON.parse(entry.screening_data)
            } catch { /* ignore */ }

            return (
              <div
                key={entry.id}
                className="bg-slate-800/80 border border-slate-700 rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/stock/${entry.symbol}`}
                      className="text-sm font-bold text-white hover:text-emerald-300 transition-colors"
                    >
                      {entry.symbol}
                    </Link>
                    <span className={`text-xs px-2 py-0.5 rounded border font-bold ${recStyle}`}>
                      {entry.recommendation}
                    </span>
                    {entry.trend && (
                      <span className="text-[10px] text-slate-500">{entry.trend}</span>
                    )}
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-slate-500 block">
                      {date.toLocaleDateString()} {date.toLocaleTimeString()}
                    </span>
                    <span className="text-[10px] text-slate-600">
                      {entry.source} | {Math.round((entry.confidence ?? 0) * 100)}%
                    </span>
                  </div>
                </div>

                {/* Full reasoning */}
                <p className="text-xs text-slate-400 leading-relaxed">
                  {entry.reasoning}
                </p>

                {/* Screening signals snapshot */}
                {screening?.signals && (
                  <div className="flex flex-wrap gap-1 mt-2 pt-2 border-t border-slate-700/50">
                    <span className="text-[10px] text-slate-500 mr-1">Signals at time:</span>
                    {screening.signals.slice(0, 5).map((sig, i) => {
                      const c = sig.direction === 'bullish'
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : sig.direction === 'bearish'
                          ? 'bg-red-500/15 text-red-400 border-red-500/30'
                          : 'bg-slate-500/15 text-slate-400 border-slate-500/30'
                      return (
                        <span key={i} className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${c}`}>
                          {sig.name.replace(/_/g, ' ')}
                        </span>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </main>
  )
}
