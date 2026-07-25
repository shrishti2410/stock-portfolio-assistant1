/**
 * MCXCommodities — MCX commodity prices dashboard with drill-down history.
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = ''

function fmt(n) {
  if (n === undefined || n === null || n === 0) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)
}

export default function MCXCommodities() {
  const [prices, setPrices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Detail view
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [history, setHistory] = useState(null)
  const [histLoading, setHistLoading] = useState(false)

  useEffect(() => {
    fetchPrices()
  }, [])

  async function fetchPrices() {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/mcx`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setPrices(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadHistory(symbol) {
    setSelectedSymbol(symbol)
    setHistLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/mcx/${symbol}?days=60`)
      if (res.ok) setHistory(await res.json())
    } catch { /* ignore */ }
    setHistLoading(false)
  }

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">MCX Commodities</h1>
          <p className="text-xs text-slate-500">Live commodity futures prices from MCX India</p>
        </div>
        <button
          onClick={fetchPrices}
          disabled={loading}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600
                     rounded-lg text-xs font-medium text-slate-200 transition-colors
                     disabled:opacity-50"
        >
          {loading ? '↻ Loading…' : '↻ Refresh'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {loading && prices.length === 0 ? (
        <p className="text-slate-500 text-sm animate-pulse py-8 text-center">
          Fetching MCX prices from TradingView… (first load may take 10-15 seconds)
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {prices.map((c) => {
            const isUp = (c.change_pct ?? 0) >= 0
            return (
              <button
                key={c.symbol}
                onClick={() => loadHistory(c.symbol)}
                className={`bg-slate-800/80 border rounded-xl p-4 text-left transition-colors
                           hover:border-slate-500 ${
                  selectedSymbol === c.symbol
                    ? 'border-emerald-500/40'
                    : 'border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h3 className="text-sm font-bold text-white">{c.name}</h3>
                    <p className="text-[10px] text-slate-500">{c.symbol} · {c.unit}</p>
                  </div>
                  {c.error ? (
                    <span className="text-[10px] text-red-400">No data</span>
                  ) : (
                    <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                      isUp
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-red-500/20 text-red-300'
                    }`}>
                      {isUp ? '+' : ''}{c.change_pct?.toFixed(2)}%
                    </span>
                  )}
                </div>

                {!c.error && (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-[10px] text-slate-500">LTP</p>
                      <p className="text-lg font-bold text-white tabular-nums">{c.currency === 'INR' ? '₹' : '$'}{fmt(c.ltp)}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] text-slate-500">Change</p>
                      <p className={`text-sm font-semibold tabular-nums ${isUp ? 'text-emerald-400' : 'text-red-400'}`}>
                        {isUp ? '+' : ''}{c.currency === 'INR' ? '₹' : '$'}{fmt(c.change)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-500">High</p>
                      <p className="text-xs text-slate-300 tabular-nums">{c.currency === 'INR' ? '₹' : '$'}{fmt(c.high)}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] text-slate-500">Low</p>
                      <p className="text-xs text-slate-300 tabular-nums">{c.currency === 'INR' ? '₹' : '$'}{fmt(c.low)}</p>
                    </div>
                  </div>
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* Detail / History panel */}
      {selectedSymbol && (
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-white">
              {history?.name ?? selectedSymbol} — 60 Day History
            </h2>
            <button onClick={() => setSelectedSymbol(null)}
                    className="text-xs text-slate-500 hover:text-slate-300">Close</button>
          </div>

          {histLoading ? (
            <p className="text-slate-500 text-sm animate-pulse">Loading history…</p>
          ) : history?.candles ? (
            <>
              {/* Summary */}
              <div className="grid grid-cols-4 gap-3 mb-4">
                <div>
                  <p className="text-[10px] text-slate-500">Current</p>
                  <p className="text-sm font-bold text-white">{history.currency === 'INR' ? '₹' : '$'}{fmt(history.ltp)}</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-500">60D High</p>
                  <p className="text-sm font-medium text-emerald-400">{history.currency === 'INR' ? '₹' : '$'}{fmt(history.high_period)}</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-500">60D Low</p>
                  <p className="text-sm font-medium text-red-400">{history.currency === 'INR' ? '₹' : '$'}{fmt(history.low_period)}</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-500">Data Points</p>
                  <p className="text-sm font-medium text-slate-300">{history.data_points}</p>
                </div>
              </div>

              {/* Price table */}
              <div className="max-h-72 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-slate-800">
                    <tr className="border-b border-slate-700 text-slate-500 uppercase">
                      <th className="px-2 py-1.5 text-left">Date</th>
                      <th className="px-2 py-1.5 text-right">Open</th>
                      <th className="px-2 py-1.5 text-right">High</th>
                      <th className="px-2 py-1.5 text-right">Low</th>
                      <th className="px-2 py-1.5 text-right">Close</th>
                      <th className="px-2 py-1.5 text-right">Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...history.candles].reverse().map((c, i) => (
                      <tr key={i} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                        <td className="px-2 py-1.5 text-slate-300">{c.date}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-400">{history.currency === 'INR' ? '₹' : '$'}{fmt(c.open)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-emerald-400">{c.currency === 'INR' ? '₹' : '$'}{fmt(c.high)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-red-400">{c.currency === 'INR' ? '₹' : '$'}{fmt(c.low)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums font-medium text-white">{history.currency === 'INR' ? '₹' : '$'}{fmt(c.close)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-400">{fmt(c.volume)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="text-slate-500 text-sm">No history available</p>
          )}
        </div>
      )}
    </main>
  )
}
