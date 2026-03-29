/**
 * StockAnalysis — full-page analysis view for any NSE stock.
 *
 * Shows: price summary, technical screening signals, AI recommendation.
 * Accessed via /stock/:symbol route or clicking a stock in the portfolio table.
 */

import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'

const DIR_STYLE = {
  bullish: { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40' },
  bearish: { bg: 'bg-red-500/20', text: 'text-red-300', border: 'border-red-500/40' },
  neutral: { bg: 'bg-amber-500/20', text: 'text-amber-300', border: 'border-amber-500/40' },
}

const BADGE = {
  Buy:  { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40' },
  Sell: { bg: 'bg-red-500/20',     text: 'text-red-300',     border: 'border-red-500/40' },
  Hold: { bg: 'bg-amber-500/20',   text: 'text-amber-300',   border: 'border-amber-500/40' },
}

function SignalPill({ signal }) {
  const colors = DIR_STYLE[signal.direction] ?? DIR_STYLE.neutral
  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded-lg border ${colors.bg} ${colors.border}`}>
      <span className={`text-xs font-bold mt-0.5 ${colors.text}`}>
        {signal.direction === 'bullish' ? '▲' : signal.direction === 'bearish' ? '▼' : '●'}
      </span>
      <div>
        <p className={`text-xs font-semibold ${colors.text}`}>{signal.name.replace(/_/g, ' ')}</p>
        <p className="text-xs text-slate-400">{signal.description}</p>
      </div>
    </div>
  )
}

function IndicatorRow({ label, value, unit = '' }) {
  if (value === undefined || value === null || value === 'N/A') return null
  return (
    <div className="flex justify-between py-1.5 border-b border-slate-700/50">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="text-xs text-slate-200 font-medium tabular-nums">{value}{unit}</span>
    </div>
  )
}

export default function StockAnalysis() {
  const { symbol } = useParams()
  const [screening, setScreening] = useState(null)
  const [screenLoading, setScreenLoading] = useState(true)
  const [screenError, setScreenError] = useState('')

  const [aiResult, setAiResult] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState('')

  // Fetch screening + load last saved AI analysis on mount
  useEffect(() => {
    async function fetchScreening() {
      setScreenLoading(true)
      setScreenError('')
      try {
        const res = await fetch(`${API_BASE}/api/screen/${symbol}`)
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail ?? `Error ${res.status}`)
        }
        setScreening(await res.json())
      } catch (err) {
        setScreenError(err.message)
      } finally {
        setScreenLoading(false)
      }
    }

    async function loadLastAnalysis() {
      try {
        const res = await fetch(`${API_BASE}/api/history/${symbol}/latest`)
        if (res.ok) {
          const data = await res.json()
          setAiResult({
            recommendation: data.recommendation,
            reasoning: data.reasoning,
            trend: data.trend,
            confidence: data.confidence,
            source: data.source,
            saved_at: data.created_at,
          })
        }
      } catch { /* no saved analysis — that's fine */ }
    }

    fetchScreening()
    loadLastAnalysis()
  }, [symbol])

  async function runAI() {
    setAiLoading(true)
    setAiError('')
    try {
      const res = await fetch(`${API_BASE}/api/analysis/ai/${symbol}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      setAiResult(await res.json())
    } catch (err) {
      setAiError(err.message)
    } finally {
      setAiLoading(false)
    }
  }

  const ind = screening?.indicators ?? {}
  const dirStyle = DIR_STYLE[screening?.overall_direction] ?? DIR_STYLE.neutral
  const priceSummary = screening?.price_data_summary ?? {}

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      {/* Back link + header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-slate-500 hover:text-slate-300 text-sm">← Dashboard</Link>
        <h1 className="text-xl font-bold text-white tracking-tight">{symbol}</h1>
        {screening && (
          <span className={`text-xs px-2 py-0.5 rounded font-semibold border ${dirStyle.bg} ${dirStyle.text} ${dirStyle.border}`}>
            {screening.overall_direction?.toUpperCase()} ({screening.overall_score >= 0 ? '+' : ''}{screening.overall_score?.toFixed(2)})
          </span>
        )}
      </div>

      {screenError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6">
          <p className="text-red-400 text-sm">{screenError}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Screening signals */}
        <div className="lg:col-span-2 space-y-4">
          {/* Price summary */}
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
            <h2 className="text-sm font-semibold text-slate-300 mb-3">Price Summary</h2>
            {screenLoading ? (
              <p className="text-slate-500 text-sm animate-pulse">Loading…</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-slate-500">Current Price</p>
                  <p className="text-lg font-bold text-white tabular-nums">
                    ₹{ind.current_price?.toLocaleString('en-IN') ?? '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Day Change</p>
                  <p className={`text-lg font-bold tabular-nums ${(ind.change_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {(ind.change_pct ?? 0) >= 0 ? '+' : ''}{ind.change_pct?.toFixed(2) ?? '—'}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">90D High</p>
                  <p className="text-sm font-medium text-slate-200 tabular-nums">₹{priceSummary.high_90d ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">90D Low</p>
                  <p className="text-sm font-medium text-slate-200 tabular-nums">₹{priceSummary.low_90d ?? '—'}</p>
                </div>
              </div>
            )}
          </div>

          {/* Signals */}
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
            <h2 className="text-sm font-semibold text-slate-300 mb-3">Technical Signals</h2>
            {screenLoading ? (
              <p className="text-slate-500 text-sm animate-pulse">Screening…</p>
            ) : screening?.signals?.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {screening.signals.map((sig, i) => (
                  <SignalPill key={i} signal={sig} />
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-sm">No signals available</p>
            )}
          </div>

          {/* AI Analysis */}
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-300">AI Analysis</h2>
              <button
                onClick={runAI}
                disabled={aiLoading}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
                           bg-emerald-500/10 border-emerald-500/30 text-emerald-300
                           hover:bg-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {aiLoading ? (
                  <><span className="animate-spin inline-block mr-1">↻</span>Analyzing…</>
                ) : aiResult ? (
                  '↻ Re-run AI'
                ) : (
                  '✦ Run AI Analysis'
                )}
              </button>
            </div>

            {aiError && (
              <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-2 py-1.5 mb-3">
                {aiError}
              </p>
            )}

            {aiResult ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  {(() => {
                    const badge = BADGE[aiResult.recommendation] ?? BADGE.Hold
                    return (
                      <span className={`inline-block text-xl font-extrabold tracking-widest px-4 py-1.5
                                        rounded-lg border ${badge.bg} ${badge.text} ${badge.border}`}>
                        {aiResult.recommendation?.toUpperCase()}
                      </span>
                    )
                  })()}
                  {aiResult.saved_at && (
                    <span className="text-[10px] text-slate-500">
                      Saved {new Date(aiResult.saved_at).toLocaleString()}
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">
                  {aiResult.reasoning}
                </p>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-slate-500">
                    Source: {aiResult.source} | Confidence: {Math.round((aiResult.confidence ?? 0) * 100)}%
                  </p>
                  <Link
                    to={`/history?symbol=${symbol}`}
                    className="text-xs text-emerald-400 hover:text-emerald-300"
                  >
                    View history &rarr;
                  </Link>
                </div>
              </div>
            ) : !aiLoading ? (
              <p className="text-slate-500 text-sm">Click "Run AI Analysis" for a detailed recommendation</p>
            ) : null}
          </div>
        </div>

        {/* Right column: Indicators */}
        <div className="space-y-4">
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-300">Indicators</h2>
              <Link to="/glossary" className="text-[10px] text-emerald-400 hover:text-emerald-300">
                What do these mean?
              </Link>
            </div>
            {screenLoading ? (
              <p className="text-slate-500 text-sm animate-pulse">Loading…</p>
            ) : (
              <div>
                <IndicatorRow label="RSI (14)" value={ind.rsi} />
                <IndicatorRow label="MACD" value={ind.macd} />
                <IndicatorRow label="MACD Signal" value={ind.macd_signal} />
                <IndicatorRow label="MACD Histogram" value={ind.macd_hist} />
                <IndicatorRow label="EMA 10" value={ind.ema_10} />
                <IndicatorRow label="EMA 20" value={ind.ema_20} />
                <IndicatorRow label="EMA 50" value={ind.ema_50} />
                <IndicatorRow label="EMA 200" value={ind.ema_200} />
                <IndicatorRow label="Bollinger Upper" value={ind.bb_upper} />
                <IndicatorRow label="Bollinger Lower" value={ind.bb_lower} />
                <IndicatorRow label="ADX" value={ind.adx} />
                <IndicatorRow label="Stoch RSI %K" value={ind.stoch_rsi_k} />
                <IndicatorRow label="Stoch RSI %D" value={ind.stoch_rsi_d} />
                <IndicatorRow label="Volume Ratio" value={ind.volume_ratio} unit="x" />
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
