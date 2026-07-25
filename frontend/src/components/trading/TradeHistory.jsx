/**
 * TradeHistory — audit trail of all past trades.
 *
 * Table with Date, Strategy, Symbol, Direction, Entry Premium, Exit Premium,
 * P&L, Paper/Live columns. Filters by strategy, date range, mode.
 * Summary stats: Total P&L, Win Rate, Best Trade, Worst Trade.
 * Embedded PnLChart for visual P&L overview.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import PnLChart from './PnLChart'

const API_BASE = ''

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

function SummaryCard({ label, value, valueClass = 'text-white', sub }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-xl font-bold tabular-nums ${valueClass}`}>{value}</p>
      {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function TradeHistory() {
  const [trades, setTrades] = useState([])
  const [pnlData, setPnlData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters
  const [filterStrategy, setFilterStrategy] = useState('')
  const [filterMode, setFilterMode] = useState('all') // 'all' | 'paper' | 'live'
  const [filterDateFrom, setFilterDateFrom] = useState('')
  const [filterDateTo, setFilterDateTo] = useState('')
  const [showChart, setShowChart] = useState(false)

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ status: 'closed', limit: '200' })
      if (filterStrategy) params.set('strategy', filterStrategy)
      if (filterMode !== 'all') params.set('mode', filterMode)
      if (filterDateFrom) params.set('from_date', filterDateFrom)
      if (filterDateTo) params.set('to_date', filterDateTo)

      const [tradesRes, pnlRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/trading/positions?${params}`),
        fetch(`${API_BASE}/api/trading/pnl`),
      ])

      if (tradesRes.status === 'fulfilled' && tradesRes.value.ok) {
        setTrades(await tradesRes.value.json())
      } else if (tradesRes.status === 'fulfilled') {
        throw new Error(`Error ${tradesRes.value.status}`)
      }

      if (pnlRes.status === 'fulfilled' && pnlRes.value.ok) {
        setPnlData(await pnlRes.value.json())
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [filterStrategy, filterMode, filterDateFrom, filterDateTo])

  useEffect(() => { fetchHistory() }, [fetchHistory])

  // Unique strategies for filter dropdown
  const strategies = [...new Set(trades.map(t => t.strategy_name).filter(Boolean))]

  // Derived stats from displayed trades
  const closedTrades = trades.filter(t => t.realized_pnl !== undefined)
  const totalPnl = closedTrades.reduce((s, t) => s + (t.realized_pnl ?? 0), 0)
  const winners = closedTrades.filter(t => (t.realized_pnl ?? 0) > 0)
  const losers = closedTrades.filter(t => (t.realized_pnl ?? 0) < 0)
  const winRate = closedTrades.length > 0 ? (winners.length / closedTrades.length) * 100 : 0
  const bestTrade = closedTrades.length > 0 ? Math.max(...closedTrades.map(t => t.realized_pnl ?? 0)) : null
  const worstTrade = closedTrades.length > 0 ? Math.min(...closedTrades.map(t => t.realized_pnl ?? 0)) : null

  function clearFilters() {
    setFilterStrategy('')
    setFilterMode('all')
    setFilterDateFrom('')
    setFilterDateTo('')
  }

  const hasFilters = filterStrategy || filterMode !== 'all' || filterDateFrom || filterDateTo

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">

      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 text-sm mb-1">
            <Link to="/trading" className="text-slate-500 hover:text-slate-300 transition-colors">Trading</Link>
            <span className="text-slate-600">/</span>
            <span className="text-slate-300">History</span>
          </div>
          <h1 className="text-xl font-bold text-white">Trade History</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowChart(v => !v)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
              showChart
                ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {showChart ? 'Hide Chart' : 'Show Chart'}
          </button>
          <button
            onClick={fetchHistory}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 disabled:opacity-50 transition-colors"
          >
            <span className={loading ? 'animate-spin inline-block' : ''}>↻</span>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
          <button onClick={fetchHistory} className="text-xs text-red-300 underline mt-1">Retry</button>
        </div>
      )}

      {/* P&L Chart (collapsible) */}
      {showChart && (
        <div className="mb-6">
          <PnLChart />
        </div>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <SummaryCard
          label="Total P&L"
          value={fmtINR(totalPnl)}
          valueClass={totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}
          sub={`${closedTrades.length} trades`}
        />
        <SummaryCard
          label="Win Rate"
          value={closedTrades.length > 0 ? `${fmtNum(winRate, 1)}%` : '—'}
          valueClass={winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}
          sub={`${winners.length}W / ${losers.length}L`}
        />
        <SummaryCard
          label="Best Trade"
          value={bestTrade !== null ? fmtINR(bestTrade) : '—'}
          valueClass="text-emerald-400"
        />
        <SummaryCard
          label="Worst Trade"
          value={worstTrade !== null ? fmtINR(worstTrade) : '—'}
          valueClass="text-red-400"
        />
      </div>

      {/* Filters */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-[10px] text-slate-500 mb-1 uppercase tracking-wide">Strategy</label>
            <select
              value={filterStrategy}
              onChange={e => setFilterStrategy(e.target.value)}
              className="py-1.5 px-2 bg-slate-800 border border-slate-600 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Strategies</option>
              {strategies.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] text-slate-500 mb-1 uppercase tracking-wide">Mode</label>
            <div className="flex rounded-lg overflow-hidden border border-slate-600">
              {['all', 'paper', 'live'].map(m => (
                <button
                  key={m}
                  onClick={() => setFilterMode(m)}
                  className={`px-2.5 py-1.5 text-xs font-medium transition-colors capitalize ${
                    filterMode === m
                      ? 'bg-slate-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-slate-500 mb-1 uppercase tracking-wide">From Date</label>
            <input
              type="date"
              value={filterDateFrom}
              onChange={e => setFilterDateFrom(e.target.value)}
              className="py-1.5 px-2 bg-slate-800 border border-slate-600 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-[10px] text-slate-500 mb-1 uppercase tracking-wide">To Date</label>
            <input
              type="date"
              value={filterDateTo}
              onChange={e => setFilterDateTo(e.target.value)}
              className="py-1.5 px-2 bg-slate-800 border border-slate-600 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="py-1.5 px-3 text-xs font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
            >
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {/* Trade Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
          <p className="text-slate-500 text-sm ml-3">Loading trades…</p>
        </div>
      ) : trades.length === 0 ? (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-10 text-center">
          <p className="text-slate-400 text-sm mb-1">No trades found</p>
          <p className="text-slate-500 text-xs">
            {hasFilters ? 'Try adjusting your filters.' : 'Approved and closed trades will appear here.'}
          </p>
          {hasFilters && (
            <button onClick={clearFilters} className="mt-3 text-xs text-blue-400 hover:text-blue-300 underline">
              Clear all filters
            </button>
          )}
        </div>
      ) : (
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-700 text-[10px] text-slate-500 uppercase">
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Strategy</th>
                  <th className="px-4 py-3 text-left">Symbol</th>
                  <th className="px-4 py-3 text-left">Direction</th>
                  <th className="px-4 py-3 text-right">Entry Premium</th>
                  <th className="px-4 py-3 text-right">Exit Premium</th>
                  <th className="px-4 py-3 text-right">P&L</th>
                  <th className="px-4 py-3 text-center">Mode</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade, i) => {
                  const pnl = trade.realized_pnl ?? 0
                  const closedAt = trade.closed_at ? new Date(trade.closed_at) : null
                  return (
                    <tr
                      key={trade.id ?? i}
                      className={`border-b border-slate-700/30 last:border-0 hover:bg-slate-700/20 transition-colors ${
                        pnl > 0 ? 'hover:bg-emerald-500/5' : pnl < 0 ? 'hover:bg-red-500/5' : ''
                      }`}
                    >
                      <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">
                        {closedAt
                          ? closedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })
                          : '—'}
                        <br />
                        <span className="text-[10px] text-slate-600">
                          {closedAt ? closedAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-medium text-slate-200 whitespace-nowrap">
                        {trade.strategy_name ?? '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-white font-semibold">{trade.symbol}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        {trade.direction ? (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                            trade.direction === 'BULLISH'
                              ? 'bg-emerald-500/15 text-emerald-300'
                              : trade.direction === 'BEARISH'
                                ? 'bg-red-500/15 text-red-300'
                                : 'bg-slate-700 text-slate-400'
                          }`}>
                            {trade.direction}
                          </span>
                        ) : <span className="text-slate-500">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-300">
                        {fmtINR(trade.entry_premium)}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-300">
                        {fmtINR(trade.exit_premium)}
                      </td>
                      <td className={`px-4 py-2.5 text-right tabular-nums font-bold ${pnlColor(pnl)}`}>
                        {pnl > 0 ? '+' : ''}{fmtINR(pnl)}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                          trade.mode === 'live'
                            ? 'bg-red-500/15 text-red-300 border border-red-500/30'
                            : 'bg-slate-700 text-slate-400'
                        }`}>
                          {trade.mode === 'live' ? 'Live' : 'Paper'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-2.5 border-t border-slate-700 flex items-center justify-between">
            <span className="text-[10px] text-slate-500">
              Showing {trades.length} trade{trades.length !== 1 ? 's' : ''}
              {hasFilters && ' (filtered)'}
            </span>
            <span className={`text-xs font-semibold tabular-nums ${pnlColor(totalPnl)}`}>
              Total: {fmtINR(totalPnl)}
            </span>
          </div>
        </div>
      )}
    </main>
  )
}
