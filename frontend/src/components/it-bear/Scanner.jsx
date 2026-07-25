/**
 * Scanner — runs all 5 IT-bear evaluators, shows ranked signals.
 * Route: /it-bear/scanner
 *
 * Run scan button, signal cards with confidence bars, auto-refresh every 5 min.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import ITBearNav from './ITBearNav'
import { fmtNum } from '../../utils/format'

const API_BASE = ''

const LAYER_COLORS = {
  core: 'bg-red-500/20 border-red-500/30 text-red-300',
  tactical: 'bg-amber-500/20 border-amber-500/30 text-amber-300',
  hedge: 'bg-purple-500/20 border-purple-500/30 text-purple-300',
  us: 'bg-blue-500/20 border-blue-500/30 text-blue-300',
}

function LayerBadge({ layer }) {
  const cls = LAYER_COLORS[layer?.toLowerCase()] ?? 'bg-slate-700 border-slate-600 text-slate-400'
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded border font-semibold uppercase ${cls}`}>
      {layer}
    </span>
  )
}

function ConfidenceBar({ value }) {
  const color = value >= 75 ? 'bg-emerald-500' : value >= 55 ? 'bg-amber-500' : 'bg-red-500'
  const textColor = value >= 75 ? 'text-emerald-400' : value >= 55 ? 'text-amber-400' : 'text-red-400'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className={`text-xs font-bold tabular-nums w-10 text-right ${textColor}`}>{value}%</span>
    </div>
  )
}

function SignalCard({ signal }) {
  const confidence = signal.confidence_score ?? signal.confidence ?? 0
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 hover:border-slate-600 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-sm font-bold text-white">{signal.symbol}</span>
            <LayerBadge layer={signal.layer} />
            {signal.direction && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
                signal.direction === 'BEARISH' || signal.direction === 'SHORT'
                  ? 'bg-red-500/15 border-red-500/30 text-red-300'
                  : 'bg-slate-700 border-slate-600 text-slate-400'
              }`}>
                {signal.direction}
              </span>
            )}
          </div>
          <p className="text-xs font-semibold text-slate-300">{signal.strategy_name}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-[10px] text-slate-500">Confidence</p>
        </div>
      </div>

      <ConfidenceBar value={confidence} />

      {signal.reasoning && (
        <p className="text-[11px] text-slate-400 mt-3 leading-relaxed line-clamp-3">
          {signal.reasoning}
        </p>
      )}

      {/* Tags */}
      {(signal.tags ?? []).length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {signal.tags.map((tag, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/60 text-slate-500">
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-700/40">
        <Link
          to={`/it-bear/strategy-builder/${signal.symbol}`}
          className="flex-1 text-center px-3 py-1.5 text-xs font-medium rounded-lg border bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25 transition-colors"
        >
          Strategy Builder
        </Link>
        <Link
          to={`/it-bear/stock/${signal.symbol}`}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
        >
          View Stock
        </Link>
        {signal.proposal_id && (
          <Link
            to={`/trading/approve/${signal.proposal_id}`}
            className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-amber-500/15 border-amber-500/30 text-amber-300 hover:bg-amber-500/25 transition-colors"
          >
            Review & Approve
          </Link>
        )}
      </div>
    </div>
  )
}

const LAYER_FILTERS = ['All', 'Core', 'Tactical', 'Hedge', 'US']

export default function Scanner() {
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(false)
  const [lastScanned, setLastScanned] = useState(null)
  const [error, setError] = useState(null)
  const [layerFilter, setLayerFilter] = useState('All')

  const runScan = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/it-bear/scanner`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const json = await res.json()
      setSignals(Array.isArray(json) ? json : json.signals ?? [])
      setLastScanned(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-refresh every 5 minutes if we have results
  useEffect(() => {
    if (signals.length === 0) return
    const id = setInterval(runScan, 5 * 60 * 1000)
    return () => clearInterval(id)
  }, [signals.length, runScan])

  const filtered = signals.filter(s => {
    if (layerFilter === 'All') return true
    return s.layer?.toLowerCase() === layerFilter.toLowerCase()
  })

  // Sort by confidence descending
  const sorted = [...filtered].sort((a, b) =>
    (b.confidence_score ?? b.confidence ?? 0) - (a.confidence_score ?? a.confidence ?? 0)
  )

  const highConfidence = signals.filter(s => (s.confidence_score ?? s.confidence ?? 0) >= 75).length

  return (
    <div>
      <ITBearNav />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

        {/* Header + Run button */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <h1 className="text-2xl font-black text-white">IT Bear Scanner</h1>
            <p className="text-slate-500 text-xs mt-1">
              Runs all 5 evaluators: Earnings Momentum, Price Breakdown, Sector Divergence,
              Valuation Stretch, and US Contagion.
            </p>
            {lastScanned && (
              <p className="text-[10px] text-slate-600 mt-1">
                Last scan: {lastScanned.toLocaleTimeString()} — auto-refresh every 5 min
              </p>
            )}
          </div>
          <button
            onClick={runScan}
            disabled={loading}
            className="px-5 py-2.5 text-sm font-bold rounded-xl border bg-red-500/20 border-red-500/40 text-red-300 hover:bg-red-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            {loading ? 'Scanning…' : 'Run Scan'}
          </button>
        </div>

        {/* Summary chips */}
        {signals.length > 0 && (
          <div className="flex flex-wrap gap-3 mb-5">
            <div className="px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-center">
              <p className="text-lg font-bold text-white">{signals.length}</p>
              <p className="text-[10px] text-slate-500">Total Signals</p>
            </div>
            <div className="px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-center">
              <p className="text-lg font-bold text-emerald-400">{highConfidence}</p>
              <p className="text-[10px] text-slate-500">High Confidence</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-5 mb-5 flex items-center justify-between">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={runScan}
              className="px-4 py-2 text-xs font-medium rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors shrink-0"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-slate-600 border-t-red-400 rounded-full animate-spin" />
            <p className="text-slate-500 text-sm ml-3">Running IT bear evaluators…</p>
          </div>
        )}

        {/* Empty before first scan */}
        {!loading && signals.length === 0 && !error && (
          <div className="text-center py-16 bg-slate-800/50 border border-slate-700 rounded-xl">
            <p className="text-slate-400 text-sm mb-2">No scan results yet.</p>
            <p className="text-slate-600 text-xs mb-4">
              Click "Run Scan" to evaluate all IT bear signals across the universe.
            </p>
            <button
              onClick={runScan}
              className="px-6 py-2.5 text-sm font-bold rounded-xl border bg-red-500/20 border-red-500/40 text-red-300 hover:bg-red-500/30 transition-colors"
            >
              Run First Scan
            </button>
          </div>
        )}

        {/* Results */}
        {!loading && signals.length > 0 && (
          <>
            {/* Layer filter */}
            <div className="flex items-center gap-2 mb-4">
              {LAYER_FILTERS.map(f => (
                <button
                  key={f}
                  onClick={() => setLayerFilter(f)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                    layerFilter === f
                      ? 'bg-red-500/20 border-red-500/30 text-red-300'
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {f}
                </button>
              ))}
              <span className="text-[10px] text-slate-600 ml-2">{sorted.length} signals</span>
            </div>

            {sorted.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                No signals for "{layerFilter}" layer.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {sorted.map((signal, i) => (
                  <SignalCard key={`${signal.symbol}-${i}`} signal={signal} />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
