/**
 * PositionMonitor — shows all open and recently closed positions.
 *
 * Cards for each position with strategy, legs, entry price, current P&L,
 * SL/Target progress bar, adjustment history for straddles, and Close button.
 * Recently closed positions (last 10) shown below.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import useTradingWebSocket from '../../hooks/useTradingWebSocket'

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

function pnlBg(val) {
  if (val > 0) return 'bg-emerald-500/10 border-emerald-500/20'
  if (val < 0) return 'bg-red-500/10 border-red-500/20'
  return 'bg-slate-800/80 border-slate-700'
}

function PnLProgressBar({ pnl, maxProfit, maxLoss }) {
  // Progress bar showing where current P&L sits between max loss and max profit
  const range = (maxProfit ?? 0) + Math.abs(maxLoss ?? 0)
  if (!range) return null

  const normalized = Math.max(0, Math.min(1, ((pnl - (maxLoss ?? 0)) / range)))
  const pct = normalized * 100

  // SL level (e.g., 50% of max loss from entry) and target
  const slPct = (Math.abs(maxLoss ?? 0) * 0.5 / range) * 100
  const targetPct = ((maxProfit ?? 0) * 0.75 / range) * 100

  return (
    <div className="my-3">
      <div className="relative h-3 bg-slate-700 rounded-full overflow-hidden">
        {/* Loss zone */}
        <div className="absolute left-0 top-0 bottom-0 bg-red-500/20" style={{ width: `${slPct}%` }} />
        {/* Profit zone */}
        <div className="absolute right-0 top-0 bottom-0 bg-emerald-500/20" style={{ width: `${100 - targetPct - slPct}%` }} />
        {/* Current P&L marker */}
        <div
          className={`absolute top-0 bottom-0 w-1 rounded-full ${pnl >= 0 ? 'bg-emerald-400' : 'bg-red-400'}`}
          style={{ left: `calc(${pct}% - 2px)` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-slate-500 mt-1">
        <span>SL: {fmtINR(maxLoss)}</span>
        <span>P&L: <span className={pnlColor(pnl)}>{fmtINR(pnl)}</span></span>
        <span>Target: {fmtINR(maxProfit)}</span>
      </div>
    </div>
  )
}

function OpenPositionCard({ position, onClose }) {
  const [closing, setClosing] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const pnl = position.unrealized_pnl ?? 0
  const legs = position.legs ?? []
  const adjustments = position.adjustment_history ?? []

  async function handleClose() {
    if (!window.confirm(`Close position "${position.strategy_name}" for ${position.symbol}? This will place market orders.`)) return
    setClosing(true)
    try {
      await fetch(`${API_BASE}/api/trading/positions/${position.id}/close`, { method: 'POST' })
      onClose(position.id)
    } catch { /* ignore */ }
    finally { setClosing(false) }
  }

  const enteredAt = position.created_at ? new Date(position.created_at) : null
  const elapsed = enteredAt ? Math.floor((Date.now() - enteredAt.getTime()) / 60000) : null

  return (
    <div className={`border rounded-xl p-4 mb-3 transition-all ${pnlBg(pnl)}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <span className="text-base font-bold text-white">{position.symbol}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
              {position.strategy_name}
            </span>
            {position.mode === 'live' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 border border-red-500/30 text-red-300 font-bold">
                LIVE
              </span>
            )}
          </div>
          <p className="text-[10px] text-slate-500">
            Entered: {enteredAt ? enteredAt.toLocaleString() : '—'}
            {elapsed !== null && <> ({elapsed}m ago)</>}
            {position.quantity && <> | Qty: {position.quantity}</>}
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className={`text-xl font-bold tabular-nums ${pnlColor(pnl)}`}>{fmtINR(pnl)}</p>
          <p className="text-[10px] text-slate-500">unrealized P&L</p>
        </div>
      </div>

      {/* P&L Progress Bar */}
      <PnLProgressBar
        pnl={pnl}
        maxProfit={position.max_profit}
        maxLoss={position.max_loss}
      />

      {/* Entry stats */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="text-center">
          <p className="text-[10px] text-slate-500">Entry Premium</p>
          <p className="text-xs font-semibold text-slate-300 tabular-nums">{fmtINR(position.entry_premium)}</p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-slate-500">Current Value</p>
          <p className="text-xs font-semibold text-slate-300 tabular-nums">{fmtINR(position.current_premium)}</p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-slate-500">Margin Used</p>
          <p className="text-xs font-semibold text-slate-300 tabular-nums">{fmtINR(position.margin_used)}</p>
        </div>
      </div>

      {/* Legs table (collapsible) */}
      {legs.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(v => !v)}
            className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors mb-2"
          >
            {expanded ? 'Hide' : 'Show'} {legs.length} leg{legs.length !== 1 ? 's' : ''}
            {adjustments.length > 0 && <> + {adjustments.length} adjustment{adjustments.length !== 1 ? 's' : ''}</>}
          </button>

          {expanded && (
            <div className="bg-slate-900/50 rounded-lg overflow-hidden mb-2">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-500">
                    <th className="px-2 py-1.5 text-left">Action</th>
                    <th className="px-2 py-1.5 text-left">Type</th>
                    <th className="px-2 py-1.5 text-right">Strike</th>
                    <th className="px-2 py-1.5 text-right">Entry</th>
                    <th className="px-2 py-1.5 text-right">Current</th>
                    <th className="px-2 py-1.5 text-right">P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {legs.map((leg, i) => {
                    const legPnl = leg.unrealized_pnl ?? 0
                    return (
                      <tr key={i} className="border-b border-slate-700/30 last:border-0">
                        <td className="px-2 py-1.5">
                          <span className={`font-bold ${leg.action === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                            {leg.action}
                          </span>
                        </td>
                        <td className={`px-2 py-1.5 font-medium ${leg.option_type === 'CE' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {leg.strike}{leg.option_type}
                        </td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-300">{fmtNum(leg.strike, 0)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-400">{fmtNum(leg.entry_price, 2)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-300">{fmtNum(leg.current_price, 2)}</td>
                        <td className={`px-2 py-1.5 text-right tabular-nums font-medium ${pnlColor(legPnl)}`}>
                          {fmtINR(legPnl)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              {/* Adjustment History for straddles */}
              {adjustments.length > 0 && (
                <div className="border-t border-slate-700 p-2">
                  <p className="text-[10px] text-slate-500 mb-1.5 font-medium">Adjustment History</p>
                  <div className="space-y-1">
                    {adjustments.map((adj, i) => (
                      <div key={i} className="flex items-center gap-2 text-[10px] text-slate-400">
                        <span className="text-slate-600">{new Date(adj.timestamp).toLocaleTimeString()}</span>
                        <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">{adj.type}</span>
                        <span>{adj.description}</span>
                        {adj.cost && <span className={pnlColor(-adj.cost)}>{fmtINR(-adj.cost)}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Close button */}
      <div className="flex justify-end pt-2 border-t border-slate-700/40">
        <button
          onClick={handleClose}
          disabled={closing}
          className="px-4 py-1.5 text-xs font-bold rounded-lg border bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {closing ? 'Closing…' : 'Close Position'}
        </button>
      </div>
    </div>
  )
}

function ClosedPositionRow({ position }) {
  const pnl = position.realized_pnl ?? 0
  const closedAt = position.closed_at ? new Date(position.closed_at) : null

  return (
    <tr className="border-b border-slate-700/30 last:border-0 hover:bg-slate-700/10">
      <td className="px-3 py-2.5 text-xs text-slate-400 tabular-nums whitespace-nowrap">
        {closedAt ? closedAt.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
      </td>
      <td className="px-3 py-2.5">
        <p className="text-xs font-semibold text-white">{position.symbol}</p>
        <p className="text-[10px] text-slate-500">{position.strategy_name}</p>
      </td>
      <td className="px-3 py-2.5 text-xs tabular-nums text-slate-300">{fmtINR(position.entry_premium)}</td>
      <td className="px-3 py-2.5 text-xs tabular-nums text-slate-300">{fmtINR(position.exit_premium)}</td>
      <td className={`px-3 py-2.5 text-xs tabular-nums font-bold ${pnlColor(pnl)}`}>{fmtINR(pnl)}</td>
      <td className="px-3 py-2.5">
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
          position.mode === 'live'
            ? 'bg-red-500/15 text-red-300'
            : 'bg-slate-700 text-slate-400'
        }`}>
          {position.mode === 'live' ? 'Live' : 'Paper'}
        </span>
      </td>
    </tr>
  )
}

export default function PositionMonitor() {
  const [openPositions, setOpenPositions] = useState([])
  const [closedPositions, setClosedPositions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const { lastMessage } = useTradingWebSocket()

  const fetchPositions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [openRes, closedRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/trading/positions?status=open`),
        fetch(`${API_BASE}/api/trading/positions?status=closed&limit=10`),
      ])

      if (openRes.status === 'fulfilled' && openRes.value.ok) {
        setOpenPositions(await openRes.value.json())
      }
      if (closedRes.status === 'fulfilled' && closedRes.value.ok) {
        setClosedPositions(await closedRes.value.json())
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchPositions() }, [fetchPositions])

  // Refresh on WebSocket events
  useEffect(() => {
    if (!lastMessage) return
    if (['position_opened', 'position_closed', 'position_updated'].includes(lastMessage.type)) {
      fetchPositions()
    }
  }, [lastMessage, fetchPositions])

  function handleClose(id) {
    setOpenPositions(prev => prev.filter(p => p.id !== id))
    setTimeout(fetchPositions, 1500)
  }

  const totalUnrealized = openPositions.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0)

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6">

      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 text-sm mb-1">
            <Link to="/trading" className="text-slate-500 hover:text-slate-300 transition-colors">Trading</Link>
            <span className="text-slate-600">/</span>
            <span className="text-slate-300">Position Monitor</span>
          </div>
          <h1 className="text-xl font-bold text-white">Position Monitor</h1>
        </div>
        <button
          onClick={fetchPositions}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 disabled:opacity-50 transition-colors"
        >
          <span className={loading ? 'animate-spin inline-block' : ''}>↻</span>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
          <button onClick={fetchPositions} className="text-xs text-red-300 underline mt-1">Retry</button>
        </div>
      )}

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3">
          <p className="text-[10px] text-slate-500 uppercase tracking-wide">Open Positions</p>
          <p className="text-2xl font-bold text-white mt-1">{openPositions.length}</p>
        </div>
        <div className={`border rounded-xl p-3 ${totalUnrealized >= 0 ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
          <p className="text-[10px] text-slate-500 uppercase tracking-wide">Total Unrealized P&L</p>
          <p className={`text-2xl font-bold tabular-nums mt-1 ${totalUnrealized >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {fmtINR(totalUnrealized)}
          </p>
        </div>
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3">
          <p className="text-[10px] text-slate-500 uppercase tracking-wide">Recent Closed</p>
          <p className="text-2xl font-bold text-white mt-1">{closedPositions.length}</p>
        </div>
      </div>

      {/* Open Positions */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-slate-200 mb-3">Open Positions</h2>

        {loading && openPositions.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
          </div>
        ) : openPositions.length === 0 ? (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
            <p className="text-slate-400 text-sm">No open positions</p>
            <Link to="/trading" className="text-blue-400 hover:text-blue-300 text-xs underline mt-2 inline-block">
              Go to Trading Dashboard
            </Link>
          </div>
        ) : (
          <div>
            {openPositions.map(pos => (
              <OpenPositionCard key={pos.id} position={pos} onClose={handleClose} />
            ))}
          </div>
        )}
      </section>

      {/* Recently Closed */}
      <section>
        <h2 className="text-base font-semibold text-slate-200 mb-3">
          Recently Closed
          <span className="ml-2 text-xs text-slate-500">(last {closedPositions.length})</span>
        </h2>

        {closedPositions.length === 0 ? (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 text-center">
            <p className="text-slate-400 text-sm">No closed positions yet</p>
          </div>
        ) : (
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700 text-[10px] text-slate-500 uppercase">
                    <th className="px-3 py-2 text-left">Closed At</th>
                    <th className="px-3 py-2 text-left">Symbol / Strategy</th>
                    <th className="px-3 py-2 text-right">Entry</th>
                    <th className="px-3 py-2 text-right">Exit</th>
                    <th className="px-3 py-2 text-right">P&L</th>
                    <th className="px-3 py-2 text-left">Mode</th>
                  </tr>
                </thead>
                <tbody>
                  {closedPositions.map(pos => (
                    <ClosedPositionRow key={pos.id} position={pos} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {closedPositions.length > 0 && (
          <div className="mt-2 text-right">
            <Link to="/trading/history" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              View full trade history →
            </Link>
          </div>
        )}
      </section>
    </main>
  )
}
