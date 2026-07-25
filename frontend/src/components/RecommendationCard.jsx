/**
 * RecommendationCard — compact card for one stock's recommendation.
 *
 * Props:
 *   item             Single dashboard row:
 *                    { symbol, recommendation, reasoning, trend, confidence, pnl_pct }
 *   externalAiResult Optional AI result injected by parent (e.g. "Run All").
 *                    When provided it seeds the card's AI state.
 *   onAiResult       Optional callback(symbol, result) — called when this card
 *                    completes its own AI fetch, so Dashboard can track results.
 *
 * "Run AI Analysis" button calls GET /api/analysis/ai/{symbol}.
 * The card swaps to the AI result when it arrives (keeps rule-based
 * result until then).  AI results are NOT persisted — they reset on
 * page refresh, but the backend cache means the second click is instant.
 */

import { useEffect, useState } from 'react'

const API_BASE = ''

const BADGE = {
  Buy:  { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40', label: 'BUY'  },
  Sell: { bg: 'bg-red-500/20',     text: 'text-red-300',     border: 'border-red-500/40',     label: 'SELL' },
  Hold: { bg: 'bg-amber-500/20',   text: 'text-amber-300',   border: 'border-amber-500/40',   label: 'HOLD' },
}

const TREND = {
  Bullish: { icon: '▲', color: 'text-emerald-400' },
  Bearish: { icon: '▼', color: 'text-red-400'     },
  Neutral: { icon: '●', color: 'text-slate-400'   },
}

const SOURCE_LABEL = {
  multi_agent_groq:     'AI Analysis',
  gemini:               'AI Analysis',
  tradingagents_ollama: 'AI Analysis',
  rule_based:           'Rule-based',
}

export default function RecommendationCard({ item, externalAiResult = null, screeningData = null, onAiResult }) {
  const [aiResult,  setAiResult]  = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError,   setAiError]   = useState('')

  // Accept result injected by Dashboard's "Run All"
  useEffect(() => {
    if (externalAiResult) setAiResult(externalAiResult)
  }, [externalAiResult])

  const display = aiResult ?? item
  const isAI    = aiResult !== null
  const hasScreening = screeningData !== null

  const badge         = BADGE[display.recommendation] ?? BADGE.Hold
  const trend         = TREND[display.trend]          ?? TREND.Neutral
  const confidencePct = Math.round((display.confidence ?? 0) * 100)
  const sourceLabel   = SOURCE_LABEL[display.source]  ?? null

  async function runAIAnalysis() {
    setAiLoading(true)
    setAiError('')
    try {
      const res = await fetch(`${API_BASE}/api/analysis/ai/${item.symbol}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Server error ${res.status}`)
      }
      const data = await res.json()
      setAiResult(data)
      onAiResult?.(item.symbol, data)
    } catch (err) {
      setAiError(err.message ?? 'Analysis failed')
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <div className={`bg-slate-800/80 border rounded-xl p-4 flex flex-col gap-3 transition-colors
                     ${isAI ? 'border-emerald-500/30' : 'border-slate-700 hover:border-slate-500'}`}>

      {/* Header — symbol + source badge + trend */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-white tracking-widest">
            {item.symbol}
          </span>
          {isAI && sourceLabel && (
            <span className="text-[10px] px-1.5 py-0.5 bg-emerald-500/20 border border-emerald-500/40
                             text-emerald-300 rounded font-medium tracking-wide">
              {sourceLabel}
            </span>
          )}
        </div>
        <span className={`text-xs font-medium flex items-center gap-1 ${trend.color}`}>
          <span>{trend.icon}</span>
          <span>{display.trend}</span>
        </span>
      </div>

      {/* Large recommendation badge */}
      <div className="flex justify-center">
        <span className={`text-2xl font-extrabold tracking-widest px-6 py-2
                          rounded-lg border ${badge.bg} ${badge.text} ${badge.border}`}>
          {badge.label}
        </span>
      </div>

      {/* Reasoning — full text, no truncation */}
      <p className={`text-xs text-slate-400 leading-relaxed ${isAI ? '' : 'line-clamp-3'}`}>
        {display.reasoning}
      </p>

      {/* Screening signal pills */}
      {hasScreening && screeningData.signals && (
        <div className="flex flex-wrap gap-1">
          {screeningData.signals.slice(0, 4).map((sig, i) => {
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
          {screeningData.signals.length > 4 && (
            <span className="text-[10px] px-1.5 py-0.5 text-slate-500">
              +{screeningData.signals.length - 4} more
            </span>
          )}
        </div>
      )}

      {/* Error message */}
      {aiError && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20
                      rounded px-2 py-1.5 leading-relaxed">
          {aiError}
        </p>
      )}

      {/* Footer — confidence bar + p&l + AI button */}
      <div className="flex flex-col gap-2 pt-1 border-t border-slate-700/60">
        <div className="flex items-center justify-between">
          {/* Confidence bar */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Confidence</span>
            <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${badge.bg.replace('/20', '/80')}`}
                style={{ width: `${confidencePct}%` }}
              />
            </div>
            <span className={`text-xs font-medium ${badge.text}`}>
              {confidencePct}%
            </span>
          </div>

          {/* P&L % */}
          <span className={`text-xs font-semibold tabular-nums
                            ${item.pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {item.pnl_pct >= 0 ? '+' : ''}{item.pnl_pct.toFixed(2)}%
          </span>
        </div>

        {/* Run AI Analysis button */}
        <button
          onClick={runAIAnalysis}
          disabled={aiLoading}
          className={`w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg
                      text-xs font-medium transition-colors border disabled:opacity-50
                      disabled:cursor-not-allowed
                      ${isAI
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20'
                        : 'bg-slate-700/60 border-slate-600 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                      }`}
        >
          {aiLoading ? (
            <>
              <span className="animate-spin inline-block">↻</span>
              Analyzing…
            </>
          ) : isAI ? (
            <>✦ Re-run AI Analysis</>
          ) : (
            <>✦ Run AI Analysis</>
          )}
        </button>
      </div>
    </div>
  )
}
