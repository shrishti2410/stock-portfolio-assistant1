/**
 * TradingDashboard — main trading control center.
 *
 * Shows engine status, market overview (NIFTY spot, VIX, PCR, IV%ile),
 * pending proposals with approve/reject, open positions with live P&L,
 * today's P&L summary, and links to Settings and History.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import useTradingWebSocket from '../../hooks/useTradingWebSocket'

const API_BASE = ''

function fmtINR(n) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)
}

function fmtNum(n, decimals = 2) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: decimals }).format(n)
}

function pnlColor(val) {
  if (val > 0) return 'text-emerald-400'
  if (val < 0) return 'text-red-400'
  return 'text-slate-400'
}

function StatCard({ label, value, sub, valueClass = 'text-white' }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-lg font-bold tabular-nums ${valueClass}`}>{value}</p>
      {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
    </div>
  )
}

function ProposalCard({ proposal, onApprove, onReject }) {
  const [acting, setActing] = useState(false)

  async function handleApprove() {
    if (acting) return
    setActing(true)
    try {
      const res = await fetch(`${API_BASE}/api/trading/proposals/${proposal.id}/approve`, { method: 'POST' })
      if (res.ok) onApprove(proposal.id)
    } catch { /* ignore */ }
    finally { setActing(false) }
  }

  async function handleReject() {
    if (acting) return
    setActing(true)
    try {
      const res = await fetch(`${API_BASE}/api/trading/proposals/${proposal.id}/reject`, { method: 'POST' })
      if (res.ok) onReject(proposal.id)
    } catch { /* ignore */ }
    finally { setActing(false) }
  }

  const confidence = proposal.confidence_score ?? 0
  const confColor = confidence >= 80 ? 'text-emerald-400' : confidence >= 60 ? 'text-amber-400' : 'text-red-400'
  const confBg = confidence >= 80 ? 'bg-emerald-500' : confidence >= 60 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="bg-slate-800/80 border border-amber-500/30 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-bold text-white truncate">{proposal.strategy_name}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 border border-blue-500/30 text-blue-300 shrink-0">
              {proposal.symbol}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 line-clamp-2">{proposal.reasoning?.slice(0, 100)}…</p>
        </div>
        <div className="text-right shrink-0">
          <p className={`text-sm font-bold tabular-nums ${confColor}`}>{confidence}%</p>
          <p className="text-[10px] text-slate-500">confidence</p>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="h-1 bg-slate-700 rounded-full mb-3">
        <div className={`h-1 rounded-full transition-all ${confBg}`} style={{ width: `${confidence}%` }} />
      </div>

      {/* Legs summary */}
      {proposal.legs?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {proposal.legs.map((leg, i) => (
            <span key={i} className={`text-[10px] px-2 py-0.5 rounded border font-medium ${
              leg.action === 'BUY'
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                : 'bg-red-500/15 border-red-500/30 text-red-300'
            }`}>
              {leg.action} {leg.strike}{leg.option_type} @{leg.ltp}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 pt-2 border-t border-slate-700/50">
        <div className="flex-1 flex items-center gap-2 text-[10px] text-slate-500">
          <span>Max P: <span className="text-emerald-400 font-medium">{fmtINR(proposal.max_profit)}</span></span>
          <span>Max L: <span className="text-red-400 font-medium">{fmtINR(proposal.max_loss)}</span></span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/trading/approve/${proposal.id}`}
            className="px-2 py-1 text-[10px] rounded border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
          >
            Details
          </Link>
          <button
            onClick={handleReject}
            disabled={acting}
            className="px-3 py-1 text-[11px] font-medium rounded border bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25 disabled:opacity-50 transition-colors"
          >
            Reject
          </button>
          <button
            onClick={handleApprove}
            disabled={acting}
            className="px-3 py-1 text-[11px] font-medium rounded border bg-emerald-500/20 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-50 transition-colors"
          >
            {acting ? '…' : 'Approve'}
          </button>
        </div>
      </div>
    </div>
  )
}

function PositionRow({ position, onClose }) {
  const [closing, setClosing] = useState(false)
  const pnl = position.unrealized_pnl ?? 0

  async function handleClose() {
    if (!window.confirm(`Close position for ${position.symbol}?`)) return
    setClosing(true)
    try {
      await fetch(`${API_BASE}/api/trading/positions/${position.id}/close`, { method: 'POST' })
      onClose(position.id)
    } catch { /* ignore */ }
    finally { setClosing(false) }
  }

  const pnlPct = position.entry_premium > 0 ? (pnl / (position.entry_premium * (position.quantity ?? 1))) * 100 : 0

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-slate-700/40 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-semibold text-white">{position.symbol}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
            {position.strategy_name}
          </span>
        </div>
        <p className="text-[10px] text-slate-500">
          Entry: {fmtINR(position.entry_premium)} | Qty: {position.quantity}
        </p>
      </div>
      <div className="text-right">
        <p className={`text-sm font-bold tabular-nums ${pnlColor(pnl)}`}>{fmtINR(pnl)}</p>
        <p className={`text-[10px] tabular-nums ${pnlColor(pnl)}`}>
          {pnlPct >= 0 ? '+' : ''}{fmtNum(pnlPct, 1)}%
        </p>
      </div>
      <button
        onClick={handleClose}
        disabled={closing}
        className="px-2 py-1 text-[10px] rounded border bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-colors shrink-0"
      >
        {closing ? '…' : 'Close'}
      </button>
    </div>
  )
}

export default function TradingDashboard() {
  const [engineStatus, setEngineStatus] = useState(null)
  const [intelligence, setIntelligence] = useState(null)
  const [proposals, setProposals] = useState([])
  const [positions, setPositions] = useState([])
  const [pnlData, setPnlData] = useState(null)
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [engineLoading, setEngineLoading] = useState(false)
  const [scanLoading, setScanLoading] = useState(false)
  const [error, setError] = useState(null)

  const { connected, lastMessage, proposals: wsProposals } = useTradingWebSocket()

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [statusRes, proposalsRes, positionsRes, intelligenceRes, pnlRes, configRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/trading/status`),
        fetch(`${API_BASE}/api/trading/proposals?status=pending`),
        fetch(`${API_BASE}/api/trading/positions?status=open`),
        fetch(`${API_BASE}/api/trading/intelligence/NIFTY`),
        fetch(`${API_BASE}/api/trading/pnl`),
        fetch(`${API_BASE}/api/trading/config`),
      ])

      if (statusRes.status === 'fulfilled' && statusRes.value.ok) {
        setEngineStatus(await statusRes.value.json())
      }
      if (proposalsRes.status === 'fulfilled' && proposalsRes.value.ok) {
        setProposals(await proposalsRes.value.json())
      }
      if (positionsRes.status === 'fulfilled' && positionsRes.value.ok) {
        setPositions(await positionsRes.value.json())
      }
      if (intelligenceRes.status === 'fulfilled' && intelligenceRes.value.ok) {
        setIntelligence(await intelligenceRes.value.json())
      }
      if (pnlRes.status === 'fulfilled' && pnlRes.value.ok) {
        setPnlData(await pnlRes.value.json())
      }
      if (configRes.status === 'fulfilled' && configRes.value.ok) {
        setConfig(await configRes.value.json())
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-refresh every 30s while engine is running
  useEffect(() => {
    if (!engineStatus?.running) return
    const interval = setInterval(fetchAll, 30000)
    return () => clearInterval(interval)
  }, [engineStatus?.running, fetchAll])

  useEffect(() => { fetchAll() }, [fetchAll])

  // React to WebSocket messages — refresh positions/proposals on events
  useEffect(() => {
    if (!lastMessage) return
    if (['position_opened', 'position_closed', 'proposal_approved', 'proposal_rejected'].includes(lastMessage.type)) {
      fetchAll()
    }
  }, [lastMessage, fetchAll])

  // Merge WS proposals with fetched ones (avoid duplicates)
  useEffect(() => {
    if (wsProposals.length > 0) {
      setProposals(prev => {
        const existingIds = new Set(prev.map(p => p.id))
        const newOnes = wsProposals.filter(p => !existingIds.has(p.id))
        return newOnes.length > 0 ? [...newOnes, ...prev] : prev
      })
    }
  }, [wsProposals])

  async function toggleEngine() {
    if (!engineStatus) return
    setEngineLoading(true)
    const endpoint = engineStatus.running ? '/api/trading/stop' : '/api/trading/start'
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setEngineStatus(prev => ({ ...prev, running: !prev.running, ...data }))
      }
    } catch { /* ignore */ }
    finally { setEngineLoading(false) }
  }

  async function triggerScan() {
    setScanLoading(true)
    try {
      await fetch(`${API_BASE}/api/trading/scan-now`, { method: 'POST' })
    } catch { /* ignore */ }
    finally {
      setScanLoading(false)
      setTimeout(fetchAll, 2000)
    }
  }

  function handleProposalApproved(id) {
    setProposals(prev => prev.filter(p => p.id !== id))
    fetchAll()
  }

  function handleProposalRejected(id) {
    setProposals(prev => prev.filter(p => p.id !== id))
  }

  function handlePositionClose(id) {
    setPositions(prev => prev.filter(p => p.id !== id))
  }

  const todayPnl = pnlData?.today_pnl ?? 0
  const totalPnl = pnlData?.total_pnl ?? 0
  const intelData = intelligence?.market_data ?? {}
  const vix = intelData.vix ?? intelligence?.vix
  const spot = intelData.spot ?? intelligence?.spot_price
  const pcr = intelData.pcr ?? intelligence?.pcr
  const ivPct = intelData.iv_percentile ?? intelligence?.iv_percentile
  const nextEvent = intelligence?.next_event ?? intelData.next_event

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

      {/* ── Engine Status Bar ───────────────────────────────────────────── */}
      <div className={`flex items-center justify-between px-4 py-3 rounded-xl mb-5 border ${
        engineStatus?.running
          ? 'bg-emerald-500/10 border-emerald-500/30'
          : 'bg-slate-800/80 border-slate-700'
      }`}>
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${engineStatus?.running ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
          <div>
            <p className="text-sm font-semibold text-white">
              Trading Engine — {engineStatus?.running ? 'Running' : 'Stopped'}
            </p>
            <p className="text-[10px] text-slate-500">
              {engineStatus?.mode === 'live' ? 'LIVE MODE' : 'Paper Trading'} &nbsp;|&nbsp;
              WS: {connected ? <span className="text-emerald-400">Connected</span> : <span className="text-red-400">Disconnected</span>}
              {engineStatus?.last_scan && <>&nbsp;| Last scan: {new Date(engineStatus.last_scan).toLocaleTimeString()}</>}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={triggerScan}
            disabled={scanLoading || !engineStatus?.running}
            className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-blue-500/15 border-blue-500/30 text-blue-300 hover:bg-blue-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {scanLoading ? 'Scanning…' : 'Scan Now'}
          </button>
          <Link
            to="/trading/settings"
            className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
          >
            Settings
          </Link>
          <button
            onClick={toggleEngine}
            disabled={engineLoading}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg border transition-colors disabled:opacity-50 ${
              engineStatus?.running
                ? 'bg-red-500/20 border-red-500/40 text-red-300 hover:bg-red-500/30'
                : 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30'
            }`}
          >
            {engineLoading ? '…' : engineStatus?.running ? 'Stop Engine' : 'Start Engine'}
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
          <p className="text-slate-500 text-sm ml-3">Loading trading data…</p>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
          <button onClick={fetchAll} className="text-xs text-red-300 underline mt-1">Retry</button>
        </div>
      )}

      {!loading && (
        <>
          {/* ── Paper Trading Account ───────────────────────────────────── */}
          {config?.paper_mode === 1 && (
            <section className="mb-6">
              <div className="bg-gradient-to-br from-blue-500/10 via-slate-800/80 to-slate-800/80 border border-blue-500/30 rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-[10px] text-blue-300 font-semibold uppercase tracking-wider">📝 Paper Trading Account</p>
                    <h2 className="text-lg font-bold text-white mt-0.5">Virtual Capital</h2>
                  </div>
                  <span className="text-[10px] px-2 py-1 rounded-full bg-blue-500/20 border border-blue-500/40 text-blue-300 font-semibold">SIMULATED</span>
                </div>
                {(() => {
                  const startingCapital = config?.max_capital ?? 100000
                  const totalPnL = pnlData?.total_pnl ?? 0
                  const balance = startingCapital + totalPnL
                  const pctChange = startingCapital > 0 ? (totalPnL / startingCapital) * 100 : 0
                  return (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      <div>
                        <p className="text-[10px] text-slate-500 uppercase mb-0.5">Starting Capital</p>
                        <p className="text-xl font-bold text-white tabular-nums">{fmtINR(startingCapital)}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500 uppercase mb-0.5">Current Balance</p>
                        <p className={`text-xl font-bold tabular-nums ${balance >= startingCapital ? 'text-emerald-400' : 'text-red-400'}`}>
                          {fmtINR(balance)}
                        </p>
                        <p className={`text-[10px] tabular-nums ${pctChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {pctChange >= 0 ? '+' : ''}{fmtNum(pctChange, 2)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500 uppercase mb-0.5">Total P&L</p>
                        <p className={`text-xl font-bold tabular-nums ${pnlColor(totalPnL)}`}>{fmtINR(totalPnL)}</p>
                        <p className="text-[10px] text-slate-500">All-time realized</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500 uppercase mb-0.5">Open Risk</p>
                        <p className="text-xl font-bold text-amber-400 tabular-nums">
                          {fmtINR(positions.reduce((s, p) => s + Math.abs(p.stop_loss_level ?? 0), 0))}
                        </p>
                        <p className="text-[10px] text-slate-500">Max possible loss</p>
                      </div>
                    </div>
                  )
                })()}
              </div>
            </section>
          )}

          {/* ── Market Overview ─────────────────────────────────────────── */}
          <section className="mb-6">
            <h2 className="text-base font-semibold text-slate-200 mb-3">Market Overview</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <StatCard
                label="NIFTY Spot"
                value={spot ? `₹${fmtNum(spot, 0)}` : '—'}
                sub="NSE Index"
              />
              <StatCard
                label="India VIX"
                value={vix ? fmtNum(vix, 2) : '—'}
                valueClass={vix > 20 ? 'text-red-400' : vix > 15 ? 'text-amber-400' : 'text-emerald-400'}
                sub={vix > 20 ? 'High volatility' : vix > 15 ? 'Moderate' : 'Low volatility'}
              />
              <StatCard
                label="PCR"
                value={pcr ? fmtNum(pcr, 2) : '—'}
                valueClass={pcr > 1 ? 'text-emerald-400' : 'text-red-400'}
                sub={pcr > 1 ? 'Bullish bias' : 'Bearish bias'}
              />
              <StatCard
                label="IV Percentile"
                value={ivPct !== undefined && ivPct !== null ? `${fmtNum(ivPct, 1)}%` : '—'}
                valueClass={ivPct > 70 ? 'text-red-400' : ivPct > 40 ? 'text-amber-400' : 'text-emerald-400'}
                sub={ivPct > 70 ? 'Expensive options' : ivPct > 40 ? 'Moderate IV' : 'Cheap options'}
              />
              <StatCard
                label="Next Event"
                value={nextEvent?.name ?? '—'}
                valueClass="text-amber-300 text-sm"
                sub={nextEvent?.date ?? 'No upcoming events'}
              />
            </div>
          </section>

          {/* ── Today's P&L Summary ─────────────────────────────────────── */}
          <section className="mb-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className={`rounded-xl border p-4 ${todayPnl >= 0 ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
                <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Today's P&L</p>
                <p className={`text-2xl font-bold tabular-nums ${pnlColor(todayPnl)}`}>{fmtINR(todayPnl)}</p>
                <p className="text-[10px] text-slate-500 mt-1">
                  {pnlData?.today_trades ?? 0} trades today
                </p>
              </div>
              <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
                <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Total P&L (All Time)</p>
                <p className={`text-2xl font-bold tabular-nums ${pnlColor(totalPnl)}`}>{fmtINR(totalPnl)}</p>
                <p className="text-[10px] text-slate-500 mt-1">
                  Win rate: {pnlData?.win_rate ? `${fmtNum(pnlData.win_rate, 1)}%` : '—'}
                </p>
              </div>
              <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
                <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Open Positions</p>
                <p className="text-2xl font-bold text-white">{positions.length}</p>
                <p className={`text-[10px] mt-1 tabular-nums ${pnlColor(positions.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0))}`}>
                  Unrealized: {fmtINR(positions.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0))}
                </p>
              </div>
            </div>
          </section>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

            {/* ── Pending Proposals ───────────────────────────────────────── */}
            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-slate-200">
                  Pending Proposals
                  {proposals.length > 0 && (
                    <span className="ml-2 px-2 py-0.5 text-[10px] rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {proposals.length}
                    </span>
                  )}
                </h2>
                <Link to="/trading/history" className="text-xs text-slate-400 hover:text-slate-200 transition-colors">
                  View History
                </Link>
              </div>

              {proposals.length === 0 ? (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 text-center">
                  <p className="text-slate-400 text-sm">No pending proposals</p>
                  <p className="text-slate-500 text-xs mt-1">
                    {engineStatus?.running ? 'Engine is scanning for opportunities…' : 'Start the engine to begin scanning.'}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {proposals.map(p => (
                    <ProposalCard
                      key={p.id}
                      proposal={p}
                      onApprove={handleProposalApproved}
                      onReject={handleProposalRejected}
                    />
                  ))}
                </div>
              )}
            </section>

            {/* ── Open Positions ──────────────────────────────────────────── */}
            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-slate-200">Open Positions</h2>
                <Link to="/trading/history" className="text-xs text-slate-400 hover:text-slate-200 transition-colors">
                  Full Monitor
                </Link>
              </div>

              <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
                {positions.length === 0 ? (
                  <p className="text-slate-400 text-sm text-center py-4">No open positions</p>
                ) : (
                  <div>
                    {positions.map(pos => (
                      <PositionRow
                        key={pos.id}
                        position={pos}
                        onClose={handlePositionClose}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Quick links */}
              <div className="flex gap-2 mt-3">
                <Link
                  to="/trading/settings"
                  className="flex-1 text-center px-3 py-2 text-xs font-medium rounded-lg border bg-slate-700/80 border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Settings
                </Link>
                <Link
                  to="/trading/history"
                  className="flex-1 text-center px-3 py-2 text-xs font-medium rounded-lg border bg-slate-700/80 border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Trade History
                </Link>
              </div>
            </section>

          </div>
        </>
      )}
    </main>
  )
}
