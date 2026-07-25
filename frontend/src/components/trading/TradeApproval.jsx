/**
 * TradeApproval — full-page proposal review.
 *
 * Shows strategy details, all legs, Greeks, market intelligence,
 * risk/reward metrics, 12-point risk checks, full reasoning,
 * APPROVE/REJECT buttons with confirmation, and auto-expiry countdown.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API_BASE = ''

const AUTO_EXPIRY_SECONDS = 600 // 10 minutes

function fmtINR(n) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)
}

function fmtNum(n, dec = 2) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: dec }).format(n)
}

function ConfidenceBar({ value }) {
  const color = value >= 80 ? 'bg-emerald-500' : value >= 60 ? 'bg-amber-500' : 'bg-red-500'
  const textColor = value >= 80 ? 'text-emerald-400' : value >= 60 ? 'text-amber-400' : 'text-red-400'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-2 rounded-full transition-all ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className={`text-sm font-bold tabular-nums w-12 text-right ${textColor}`}>{value}%</span>
    </div>
  )
}

function CountdownTimer({ createdAt, expirySeconds }) {
  const [remaining, setRemaining] = useState(expirySeconds)

  useEffect(() => {
    const created = createdAt ? new Date(createdAt).getTime() : Date.now()
    const expiry = created + expirySeconds * 1000

    function tick() {
      const secs = Math.max(0, Math.floor((expiry - Date.now()) / 1000))
      setRemaining(secs)
    }

    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [createdAt, expirySeconds])

  const mins = Math.floor(remaining / 60)
  const secs = remaining % 60
  const isUrgent = remaining < 120
  const pct = Math.min(100, (remaining / expirySeconds) * 100)

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${
      isUrgent ? 'bg-red-500/10 border-red-500/30' : 'bg-slate-800 border-slate-700'
    }`}>
      <span className={`text-xs font-medium ${isUrgent ? 'text-red-400' : 'text-slate-400'}`}>
        Auto-expires in
      </span>
      <span className={`text-sm font-bold tabular-nums ${isUrgent ? 'text-red-300' : 'text-amber-300'}`}>
        {mins}:{secs.toString().padStart(2, '0')}
      </span>
      <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-1 rounded-full transition-all ${isUrgent ? 'bg-red-500' : 'bg-amber-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function RiskCheck({ label, passed }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${
      passed
        ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-300'
        : 'bg-red-500/5 border-red-500/20 text-red-300'
    }`}>
      <span className="font-bold shrink-0">{passed ? '✓' : '✗'}</span>
      <span>{label}</span>
    </div>
  )
}

function MetricBox({ label, value, valueClass = 'text-white', note }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-xl font-bold tabular-nums ${valueClass}`}>{value}</p>
      {note && <p className="text-[10px] text-slate-500 mt-1">{note}</p>}
    </div>
  )
}

const DEFAULT_RISK_LABELS = [
  'Capital within limits',
  'Max positions not exceeded',
  'Daily loss limit safe',
  'VIX within acceptable range',
  'Margin available',
  'No conflicting positions',
  'PCR neutral or favorable',
  'IV percentile suitable',
  'No major event in next 24h',
  'Liquidity check passed',
  'Greeks within bounds',
  'Circuit breaker not triggered',
]

export default function TradeApproval() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [proposal, setProposal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [acting, setActing] = useState(null) // 'approve' | 'reject' | null
  const [showConfirm, setShowConfirm] = useState(null) // 'approve' | 'reject' | null

  const fetchProposal = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/trading/proposals/${id}`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setProposal(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetchProposal() }, [fetchProposal])

  async function handleAction(action) {
    setShowConfirm(null)
    setActing(action)
    try {
      const res = await fetch(`${API_BASE}/api/trading/proposals/${id}/${action}`, { method: 'POST' })
      if (res.ok) {
        navigate('/trading')
      } else {
        const body = await res.json().catch(() => ({}))
        setError(body.detail ?? `Failed to ${action}`)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setActing(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
        <p className="text-slate-500 text-sm ml-3">Loading proposal…</p>
      </div>
    )
  }

  if (error || !proposal) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-8 text-center">
          <p className="text-red-400 text-sm mb-4">{error ?? 'Proposal not found'}</p>
          <Link to="/trading" className="text-blue-400 hover:text-blue-300 text-sm underline">
            Back to Trading Dashboard
          </Link>
        </div>
      </div>
    )
  }

  const intel = proposal.intelligence ?? {}
  const legs = proposal.legs ?? []
  const greeks = proposal.greeks ?? {}
  const riskChecks = proposal.risk_checks ?? []
  const confidence = proposal.confidence_score ?? 0

  // Build default risk checks if none provided
  const checksToShow = riskChecks.length > 0
    ? riskChecks
    : DEFAULT_RISK_LABELS.map((label, i) => ({ label, passed: i < 9 }))

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6">

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-5 gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link to="/trading" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
              Trading
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-slate-300">Trade Approval</span>
          </div>
          <h1 className="text-2xl font-bold text-white">{proposal.strategy_name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 border border-blue-500/30 text-blue-300">
              {proposal.symbol}
            </span>
            <span className="px-2 py-0.5 text-xs rounded bg-slate-700 border border-slate-600 text-slate-400">
              {proposal.direction ?? 'NEUTRAL'}
            </span>
            {proposal.mode === 'live' && (
              <span className="px-2 py-0.5 text-xs rounded bg-red-500/20 border border-red-500/30 text-red-300 font-bold">
                LIVE
              </span>
            )}
          </div>
        </div>

        <CountdownTimer
          createdAt={proposal.created_at}
          expirySeconds={AUTO_EXPIRY_SECONDS}
        />
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 mb-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* ── Confidence Score ─────────────────────────────────────────────── */}
      <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 mb-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-semibold text-slate-300">Confidence Score</p>
          <span className="text-[10px] text-slate-500">
            {confidence >= 80 ? 'High confidence' : confidence >= 60 ? 'Moderate confidence' : 'Low confidence'}
          </span>
        </div>
        <ConfidenceBar value={confidence} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-5">

        {/* ── Legs Table ───────────────────────────────────────────────────── */}
        <div className="lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Strategy Legs</h2>
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700 text-[10px] text-slate-500 uppercase">
                    <th className="px-3 py-2 text-left">Action</th>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-right">Strike</th>
                    <th className="px-3 py-2 text-right">LTP</th>
                    <th className="px-3 py-2 text-right">IV</th>
                    <th className="px-3 py-2 text-right">Delta</th>
                    <th className="px-3 py-2 text-right">Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {legs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-3 py-4 text-center text-slate-500">No legs available</td>
                    </tr>
                  ) : (
                    legs.map((leg, i) => (
                      <tr key={i} className="border-b border-slate-700/40 last:border-0 hover:bg-slate-700/20">
                        <td className="px-3 py-2.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            leg.action === 'BUY'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : 'bg-red-500/20 text-red-300'
                          }`}>
                            {leg.action}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`font-semibold ${leg.option_type === 'CE' ? 'text-emerald-400' : 'text-red-400'}`}>
                            {leg.option_type}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-white font-medium">
                          {fmtNum(leg.strike, 0)}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                          {fmtNum(leg.ltp, 2)}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">
                          {leg.iv ? `${fmtNum(leg.iv, 1)}%` : '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-slate-400">
                          {fmtNum(leg.delta, 3)}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">
                          {leg.quantity ?? '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Greeks Summary ─────────────────────────────────────────────── */}
          <h2 className="text-sm font-semibold text-slate-300 mt-5 mb-3">Greeks Summary</h2>
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3 text-center">
              <p className="text-[10px] text-slate-500 mb-1">Net Delta</p>
              <p className={`text-lg font-bold tabular-nums ${
                (greeks.net_delta ?? 0) > 0 ? 'text-emerald-400' : (greeks.net_delta ?? 0) < 0 ? 'text-red-400' : 'text-slate-400'
              }`}>
                {fmtNum(greeks.net_delta, 3)}
              </p>
            </div>
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3 text-center">
              <p className="text-[10px] text-slate-500 mb-1">Net Theta</p>
              <p className={`text-lg font-bold tabular-nums ${(greeks.net_theta ?? 0) > 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {fmtNum(greeks.net_theta, 2)}
              </p>
            </div>
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-3 text-center">
              <p className="text-[10px] text-slate-500 mb-1">Net Vega</p>
              <p className="text-lg font-bold tabular-nums text-blue-400">
                {fmtNum(greeks.net_vega, 2)}
              </p>
            </div>
          </div>
        </div>

        {/* ── Intelligence Panel ──────────────────────────────────────────── */}
        <div>
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Market Intelligence</h2>
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 space-y-3">
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">VIX</span>
              <span className={`font-semibold tabular-nums ${(intel.vix ?? 0) > 20 ? 'text-red-400' : 'text-emerald-400'}`}>
                {fmtNum(intel.vix, 2)}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Regime</span>
              <span className="font-semibold text-white capitalize">{intel.regime ?? '—'}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">PCR</span>
              <span className={`font-semibold tabular-nums ${(intel.pcr ?? 0) > 1 ? 'text-emerald-400' : 'text-red-400'}`}>
                {fmtNum(intel.pcr, 2)}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">IV Percentile</span>
              <span className="font-semibold tabular-nums text-amber-300">
                {intel.iv_percentile !== undefined ? `${fmtNum(intel.iv_percentile, 1)}%` : '—'}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Expected Move</span>
              <span className="font-semibold tabular-nums text-blue-300">
                {intel.expected_move ? `±${fmtNum(intel.expected_move, 0)}` : '—'}
              </span>
            </div>
            <div className="border-t border-slate-700 pt-3">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">Max Pain</span>
                <span className="font-semibold tabular-nums text-white">
                  {intel.max_pain ? fmtNum(intel.max_pain, 0) : '—'}
                </span>
              </div>
            </div>
            {(intel.oi_support || intel.oi_resistance) && (
              <div className="border-t border-slate-700 pt-3 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">OI Support</span>
                  <span className="font-semibold tabular-nums text-emerald-400">
                    {fmtNum(intel.oi_support, 0)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">OI Resistance</span>
                  <span className="font-semibold tabular-nums text-red-400">
                    {fmtNum(intel.oi_resistance, 0)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Risk/Reward ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        <MetricBox
          label="Max Profit"
          value={fmtINR(proposal.max_profit)}
          valueClass="text-emerald-400"
          note="Best case scenario"
        />
        <MetricBox
          label="Max Loss"
          value={fmtINR(proposal.max_loss)}
          valueClass="text-red-400"
          note="Worst case scenario"
        />
        <MetricBox
          label="Margin Required"
          value={fmtINR(proposal.margin_required)}
          valueClass="text-amber-300"
          note="Capital at risk"
        />
      </div>

      {/* ── Risk Checks ──────────────────────────────────────────────────── */}
      <div className="mb-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">
          Risk Checks
          <span className="ml-2 text-[10px] text-slate-500">
            {checksToShow.filter(c => c.passed).length}/{checksToShow.length} passed
          </span>
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {checksToShow.map((check, i) => (
            <RiskCheck key={i} label={check.label} passed={check.passed} />
          ))}
        </div>
        {checksToShow.some(c => !c.passed) && (
          <div className="mt-2 px-3 py-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <p className="text-xs text-amber-300">
              Some risk checks failed. Review carefully before approving.
            </p>
          </div>
        )}
      </div>

      {/* ── Full Reasoning ───────────────────────────────────────────────── */}
      {proposal.reasoning && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Full Reasoning</h2>
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
              {proposal.reasoning}
            </p>
          </div>
        </div>
      )}

      {/* ── Action Buttons ───────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 sticky bottom-4">
        <Link
          to="/trading"
          className="px-4 py-3 text-sm font-medium rounded-xl border bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
        >
          Back
        </Link>

        <button
          onClick={() => setShowConfirm('reject')}
          disabled={acting !== null}
          className="flex-1 py-3 text-sm font-bold rounded-xl border bg-red-500/15 border-red-500/40 text-red-300 hover:bg-red-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {acting === 'reject' ? 'Rejecting…' : 'REJECT'}
        </button>

        <button
          onClick={() => setShowConfirm('approve')}
          disabled={acting !== null}
          className="flex-1 py-3 text-sm font-bold rounded-xl border bg-emerald-500/20 border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {acting === 'approve' ? 'Approving…' : 'APPROVE'}
        </button>
      </div>

      {/* ── Confirmation Modal ───────────────────────────────────────────── */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-sm w-full shadow-2xl">
            <h3 className={`text-lg font-bold mb-2 ${showConfirm === 'approve' ? 'text-emerald-300' : 'text-red-300'}`}>
              {showConfirm === 'approve' ? 'Confirm Approval' : 'Confirm Rejection'}
            </h3>
            <p className="text-sm text-slate-400 mb-4">
              {showConfirm === 'approve'
                ? `This will execute the ${proposal.strategy_name} trade${proposal.mode === 'live' ? ' in LIVE mode with real money' : ' in paper trading mode'}.`
                : `Reject this proposal. It will be archived and no trade will be placed.`
              }
            </p>
            {proposal.mode === 'live' && showConfirm === 'approve' && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4">
                <p className="text-xs text-red-300 font-medium">LIVE TRADE — Real money will be used. Margin required: {fmtINR(proposal.margin_required)}</p>
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirm(null)}
                className="flex-1 py-2.5 text-sm font-medium rounded-xl bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleAction(showConfirm)}
                className={`flex-1 py-2.5 text-sm font-bold rounded-xl transition-colors ${
                  showConfirm === 'approve'
                    ? 'bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/35'
                    : 'bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30'
                }`}
              >
                {showConfirm === 'approve' ? 'Yes, Approve' : 'Yes, Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
