/**
 * Dashboard — root view component.
 *
 * Fetches /api/dashboard on mount and on manual refresh.
 * Renders:
 *   SummaryBar         — aggregate portfolio stats (top)
 *   PortfolioTable     — full holdings table (left column)
 *   RecommendationCard — one card per holding (right column grid)
 *
 * "Run All AI" button runs analysis for every stock sequentially,
 * showing live progress and feeding results into each card.
 */

import { useCallback, useEffect, useState } from 'react'
import SummaryBar from './SummaryBar'
import PortfolioTable from './PortfolioTable'
import RecommendationCard from './RecommendationCard'
import ConnectZerodha from './ConnectZerodha'

const API_BASE = 'http://localhost:8000'

export default function Dashboard() {
  const [data,        setData]        = useState([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [lastFetched, setLastFetched] = useState(null)
  const [showConnect, setShowConnect] = useState(false)
  const [isConnected, setIsConnected] = useState(
    () => localStorage.getItem('zerodha_connected') === 'true'
  )

  // Per-symbol AI results injected by "Run All" → fed into each card
  const [aiResults,    setAiResults]    = useState({})   // { symbol: result }
  // Run All progress: null when idle, object while running
  const [runAllStatus, setRunAllStatus] = useState(null) // { label, done, total }
  const [runAllActive, setRunAllActive] = useState(false)

  const fetchDashboard = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/dashboard`)
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const json = await res.json()
      setData(json)
      setLastFetched(new Date())
    } catch (err) {
      setError(err.message ?? 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchDashboard() }, [fetchDashboard])

  // Track results from individual card runs
  function handleAiResult(symbol, result) {
    setAiResults(prev => ({ ...prev, [symbol]: result }))
  }

  // Run AI analysis for every stock sequentially
  async function runAll() {
    if (runAllActive || data.length === 0) return
    setRunAllActive(true)
    setRunAllStatus({ label: 'Starting…', done: 0, total: data.length })

    for (let i = 0; i < data.length; i++) {
      const symbol = data[i].symbol
      setRunAllStatus({ label: `Analyzing ${symbol}`, done: i, total: data.length })
      try {
        const res = await fetch(`${API_BASE}/api/analysis/ai/${symbol}`)
        if (res.ok) {
          const result = await res.json()
          setAiResults(prev => ({ ...prev, [symbol]: result }))
        }
      } catch {
        // Individual failure — continue to next stock
      }
    }

    setRunAllStatus({ label: 'Done', done: data.length, total: data.length })
    setRunAllActive(false)
    // Clear status bar after 3 s
    setTimeout(() => setRunAllStatus(null), 3000)
  }

  // ── Error state ──────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-8 text-center max-w-md">
          <p className="text-red-400 text-lg font-semibold mb-2">Error loading data</p>
          <p className="text-slate-400 text-sm mb-6">{error}</p>
          <button
            onClick={fetchDashboard}
            className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40
                       text-red-300 text-sm font-medium rounded-lg transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans">
      {/* ── Page header ────────────────────────────────────────────────── */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">
              Stock Portfolio Assistant
            </h1>
            {lastFetched && !loading && (
              <p className="text-xs text-slate-500 mt-0.5">
                Last updated {lastFetched.toLocaleTimeString()}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Connect Zerodha toggle */}
            <button
              onClick={() => setShowConnect((v) => !v)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium
                          border transition-colors
                          ${isConnected
                            ? 'bg-emerald-600/20 border-emerald-500/40 text-emerald-300 hover:bg-emerald-600/30'
                            : showConnect
                              ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                              : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
                          }`}
            >
              <span>{isConnected ? '✓' : '⚡'}</span>
              {isConnected
                ? (showConnect ? 'Hide' : 'Zerodha Connected')
                : (showConnect ? 'Hide' : 'Connect Zerodha')
              }
            </button>

            {/* Run All AI Analysis */}
            <button
              onClick={runAll}
              disabled={runAllActive || data.length === 0}
              className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600/20 hover:bg-emerald-600/30
                         disabled:opacity-50 disabled:cursor-not-allowed
                         border border-emerald-500/40 rounded-lg text-sm font-medium
                         text-emerald-300 transition-colors"
            >
              {runAllActive ? (
                <>
                  <span className="animate-spin inline-block">↻</span>
                  {runAllStatus?.label ?? 'Running…'}
                  <span className="text-emerald-500">
                    ({runAllStatus?.done ?? 0}/{runAllStatus?.total ?? data.length})
                  </span>
                </>
              ) : runAllStatus?.label === 'Done' ? (
                <>✓ All Done</>
              ) : (
                <>✦ Run All AI</>
              )}
            </button>

            {/* Refresh */}
            <button
              onClick={fetchDashboard}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600
                         disabled:opacity-50 disabled:cursor-not-allowed
                         border border-slate-600 rounded-lg text-sm font-medium
                         text-slate-200 transition-colors"
            >
              <span className={loading ? 'animate-spin inline-block' : ''} aria-hidden="true">
                ↻
              </span>
              {loading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>
      </header>

      {/* ── Connect Zerodha panel (toggled) ───────────────────────────── */}
      {showConnect && (
        <ConnectZerodha
          onSuccess={() => { setIsConnected(true); setShowConnect(false); fetchDashboard() }}
          onClose={() => setShowConnect(false)}
          onDisconnect={() => { setIsConnected(false); setShowConnect(false) }}
        />
      )}

      {/* ── Main content ───────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

        {loading && data.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-10 h-10 border-2 border-slate-600 border-t-slate-300
                            rounded-full animate-spin" />
            <p className="text-slate-500 text-sm">Loading portfolio…</p>
          </div>
        ) : (
          <>
            {data.length > 0 && <SummaryBar data={data} />}

            <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">

              {/* Left — holdings table */}
              <div className="xl:col-span-3">
                <PortfolioTable data={data} loading={loading && data.length === 0} />
              </div>

              {/* Right — recommendation cards */}
              <div className="xl:col-span-2 flex flex-col gap-3">
                <h2 className="text-base font-semibold text-slate-200 px-1">
                  Recommendations
                </h2>
                {data.length === 0 && !loading && (
                  <p className="text-slate-500 text-sm px-1">No data available.</p>
                )}
                {data.map((item) => (
                  <RecommendationCard
                    key={item.symbol}
                    item={item}
                    externalAiResult={aiResults[item.symbol] ?? null}
                    onAiResult={handleAiResult}
                  />
                ))}
              </div>

            </div>
          </>
        )}
      </main>
    </div>
  )
}
