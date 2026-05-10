/**
 * StrategyBuilder — build a bearish options strategy for an IT stock.
 * Route: /it-bear/strategy-builder/:symbol?
 *
 * Pick symbol, conviction, horizon — get AI suggestion — execute as paper trade.
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import ITBearNav from './ITBearNav'
import { fmtNum, fmtINR } from '../../utils/format'

const API_BASE = 'http://localhost:8000'

// Conviction options
const CONVICTION_OPTIONS = [
  { id: 'weak', label: 'Weak', desc: 'Uncertain — small position, hedge-focused' },
  { id: 'moderate', label: 'Moderate', desc: 'Moderate confidence — balanced risk/reward' },
  { id: 'strong', label: 'Strong', desc: 'High conviction — larger position, directional' },
]

// Horizon options (days)
const HORIZON_OPTIONS = [
  { id: 7, label: '1 Week', desc: '~7 days' },
  { id: 30, label: '1 Month', desc: '~30 days' },
  { id: 90, label: '3 Months', desc: '~90 days' },
  { id: 180, label: '6 Months', desc: '~180 days' },
]

function RadioCard({ selected, onClick, label, desc }) {
  return (
    <div
      onClick={onClick}
      className={`cursor-pointer p-3 rounded-xl border transition-colors ${
        selected
          ? 'bg-red-500/15 border-red-500/40 text-red-300'
          : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'
      }`}
    >
      <div className="flex items-center gap-2 mb-0.5">
        <div className={`w-3.5 h-3.5 rounded-full border-2 shrink-0 ${
          selected ? 'border-red-400 bg-red-400/40' : 'border-slate-600'
        }`} />
        <span className={`text-sm font-semibold ${selected ? 'text-red-300' : 'text-slate-300'}`}>{label}</span>
      </div>
      <p className="text-[10px] text-slate-500 pl-5">{desc}</p>
    </div>
  )
}

function LegBadge({ action, strike, optionType, expiry }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium ${
      action === 'BUY'
        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
        : 'bg-red-500/10 border-red-500/30 text-red-300'
    }`}>
      <span className="font-bold">{action}</span>
      <span className="text-white tabular-nums">{strike} {optionType}</span>
      {expiry && <span className="text-slate-500">exp {expiry}</span>}
    </div>
  )
}

function MetricBox({ label, value, valueClass = 'text-white' }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 text-center">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-lg font-bold tabular-nums ${valueClass}`}>{value}</p>
    </div>
  )
}

// All IT stocks as dropdown fallback
const ALL_SYMBOLS = [
  'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTI', 'MPHASIS', 'LTTS',
  'PERSISTENT', 'COFORGE', 'MINDTREE', 'NIITTECH', 'HEXAWARE',
  'ACN', 'IBM', 'CTSH', 'WIT', 'INFY', 'EPAM', 'GLOB', 'KFRC',
]

export default function StrategyBuilder() {
  const { symbol: paramSymbol } = useParams()
  const navigate = useNavigate()

  const [symbol, setSymbol] = useState(paramSymbol ?? '')
  const [conviction, setConviction] = useState('moderate')
  const [horizonDays, setHorizonDays] = useState(30)
  const [suggestion, setSuggestion] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [executing, setExecuting] = useState(false)
  const [executed, setExecuted] = useState(false)

  // If paramSymbol changes (navigation), update symbol state
  useEffect(() => {
    if (paramSymbol) setSymbol(paramSymbol)
  }, [paramSymbol])

  const fetchSuggestion = useCallback(async () => {
    if (!symbol.trim()) {
      setError('Please select a stock symbol.')
      return
    }
    setLoading(true)
    setError(null)
    setSuggestion(null)
    setExecuted(false)
    try {
      const url = `${API_BASE}/api/it-bear/strategy-suggest/${encodeURIComponent(symbol.trim())}?conviction=${conviction}&horizon_days=${horizonDays}`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      setSuggestion(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [symbol, conviction, horizonDays])

  async function handleExecutePaperTrade() {
    if (!suggestion) return
    setExecuting(true)
    setError(null)
    try {
      // Build a proposal payload matching the existing trading engine schema
      const payload = {
        symbol: symbol.toUpperCase(),
        strategy_name: suggestion.structure ?? `Bear ${suggestion.strategy_type ?? 'Put'} — ${symbol}`,
        direction: 'BEARISH',
        mode: 'paper',
        legs: suggestion.legs ?? [],
        max_profit: suggestion.max_profit,
        max_loss: suggestion.max_loss,
        margin_required: suggestion.capital_required,
        confidence_score: suggestion.confidence ?? 70,
        reasoning: suggestion.reasoning ?? '',
        source: 'it-bear-strategy-builder',
      }

      const res = await fetch(`${API_BASE}/api/trading/proposals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Execute failed (${res.status})`)
      }
      setExecuted(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div>
      <ITBearNav />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-6">

        {/* Header */}
        <div className="flex items-center gap-2 text-xs text-slate-500 mb-4">
          <Link to="/it-bear" className="hover:text-slate-300 transition-colors">IT Bear</Link>
          <span>/</span>
          <span className="text-slate-300">Strategy Builder</span>
        </div>
        <h1 className="text-2xl font-black text-white mb-1">Bearish Strategy Builder</h1>
        <p className="text-slate-500 text-xs mb-6">
          AI-powered IT sector bearish strategy suggestion — puts, spreads, collars.
        </p>

        {/* Input form */}
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 mb-5">
          <h2 className="text-sm font-semibold text-slate-200 mb-4">Configure Your Trade</h2>

          {/* Symbol */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Stock Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={e => setSymbol(e.target.value.toUpperCase())}
              placeholder="e.g. TCS, INFY, ACN"
              list="it-symbols"
              className="w-full py-2.5 px-3 bg-slate-900 border border-slate-600 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-red-500/50 transition-colors placeholder-slate-600"
            />
            <datalist id="it-symbols">
              {ALL_SYMBOLS.map(s => <option key={s} value={s} />)}
            </datalist>
          </div>

          {/* Conviction */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-slate-300 mb-2">Conviction Level</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {CONVICTION_OPTIONS.map(opt => (
                <RadioCard
                  key={opt.id}
                  selected={conviction === opt.id}
                  onClick={() => setConviction(opt.id)}
                  label={opt.label}
                  desc={opt.desc}
                />
              ))}
            </div>
          </div>

          {/* Horizon */}
          <div className="mb-5">
            <label className="block text-xs font-medium text-slate-300 mb-2">Trade Horizon</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {HORIZON_OPTIONS.map(opt => (
                <RadioCard
                  key={opt.id}
                  selected={horizonDays === opt.id}
                  onClick={() => setHorizonDays(opt.id)}
                  label={opt.label}
                  desc={opt.desc}
                />
              ))}
            </div>
          </div>

          <button
            onClick={fetchSuggestion}
            disabled={loading || !symbol.trim()}
            className="w-full py-3 text-sm font-bold rounded-xl border bg-red-500/20 border-red-500/40 text-red-300 hover:bg-red-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Fetching strategy suggestion…' : 'Get Strategy Suggestion'}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-5">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Loading spinner */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-7 h-7 border-2 border-slate-600 border-t-red-400 rounded-full animate-spin" />
            <p className="text-slate-500 text-sm ml-3">Analyzing IT bear signals…</p>
          </div>
        )}

        {/* Suggestion result */}
        {!loading && suggestion && (
          <div className="space-y-4">

            {/* Strategy header */}
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-5">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <p className="text-[10px] text-red-400/70 uppercase tracking-wider mb-1">Recommended Structure</p>
                  <h2 className="text-lg font-bold text-white">{suggestion.structure ?? 'Strategy Suggestion'}</h2>
                  <p className="text-xs text-slate-400 mt-1">{suggestion.strategy_type ?? ''}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[10px] text-slate-500 mb-0.5">Confidence</p>
                  <p className={`text-xl font-black tabular-nums ${
                    (suggestion.confidence ?? 0) >= 75 ? 'text-emerald-400'
                    : (suggestion.confidence ?? 0) >= 55 ? 'text-amber-400'
                    : 'text-red-400'
                  }`}>
                    {suggestion.confidence ?? '—'}%
                  </p>
                </div>
              </div>

              {/* Legs */}
              {(suggestion.legs ?? []).length > 0 && (
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">Strategy Legs</p>
                  <div className="flex flex-wrap gap-2">
                    {suggestion.legs.map((leg, i) => (
                      <LegBadge
                        key={i}
                        action={leg.action}
                        strike={leg.strike}
                        optionType={leg.option_type}
                        expiry={leg.expiry}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <MetricBox
                label="Max Profit"
                value={suggestion.max_profit !== undefined ? fmtINR(suggestion.max_profit) : '—'}
                valueClass="text-emerald-400"
              />
              <MetricBox
                label="Max Loss"
                value={suggestion.max_loss !== undefined ? fmtINR(suggestion.max_loss) : '—'}
                valueClass="text-red-400"
              />
              <MetricBox
                label="Breakeven"
                value={suggestion.breakeven !== undefined ? fmtNum(suggestion.breakeven, 0) : '—'}
                valueClass="text-amber-300"
              />
              <MetricBox
                label="Capital Required"
                value={suggestion.capital_required !== undefined ? fmtINR(suggestion.capital_required) : '—'}
                valueClass="text-white"
              />
            </div>

            {/* Position size */}
            {(suggestion.lots !== undefined || suggestion.quantity !== undefined) && (
              <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
                <h3 className="text-xs font-semibold text-slate-300 mb-2">Position Size</h3>
                <div className="flex gap-6">
                  {suggestion.lots !== undefined && (
                    <div>
                      <p className="text-[10px] text-slate-500">Lots</p>
                      <p className="text-base font-bold text-white tabular-nums">{suggestion.lots}</p>
                    </div>
                  )}
                  {suggestion.quantity !== undefined && (
                    <div>
                      <p className="text-[10px] text-slate-500">Quantity</p>
                      <p className="text-base font-bold text-white tabular-nums">{suggestion.quantity}</p>
                    </div>
                  )}
                  {suggestion.capital_required !== undefined && (
                    <div>
                      <p className="text-[10px] text-slate-500">Capital Required</p>
                      <p className="text-base font-bold text-amber-300 tabular-nums">{fmtINR(suggestion.capital_required)}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Reasoning */}
            {suggestion.reasoning && (
              <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
                <h3 className="text-xs font-semibold text-slate-300 mb-2">AI Reasoning</h3>
                <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                  {suggestion.reasoning}
                </p>
              </div>
            )}

            {/* Execute as Paper Trade */}
            {executed ? (
              <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
                <span className="text-emerald-300 font-bold text-sm">Trade submitted for approval</span>
                <span className="text-xs text-slate-500">—</span>
                <button
                  onClick={() => navigate('/trading')}
                  className="text-xs text-emerald-400 underline"
                >
                  View in Trading Dashboard
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3 p-5 bg-slate-800/80 border border-slate-700 rounded-xl">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-white">Execute as Paper Trade</p>
                  <p className="text-[11px] text-slate-500">
                    Submits this strategy as a pending proposal in the trading engine (paper mode — no real money).
                  </p>
                </div>
                <button
                  onClick={handleExecutePaperTrade}
                  disabled={executing}
                  className="px-5 py-2.5 text-sm font-bold rounded-xl border bg-emerald-500/20 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
                >
                  {executing ? 'Submitting…' : 'Execute as Paper Trade'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Empty state before first search */}
        {!loading && !suggestion && !error && (
          <div className="text-center py-12 text-slate-600">
            <p className="text-sm">Configure your trade parameters above and click</p>
            <p className="text-sm font-semibold text-slate-500 mt-1">"Get Strategy Suggestion"</p>
          </div>
        )}
      </main>
    </div>
  )
}
