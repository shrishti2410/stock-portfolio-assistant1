/**
 * PredefinedStrategies — Browse and check 13 pre-built F&O strategies.
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'

const CAT_COLORS = {
  emerald: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  amber:   { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30' },
  red:     { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30' },
  blue:    { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/30' },
  purple:  { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/30' },
  cyan:    { bg: 'bg-cyan-500/15', text: 'text-cyan-400', border: 'border-cyan-500/30' },
  slate:   { bg: 'bg-slate-500/15', text: 'text-slate-400', border: 'border-slate-500/30' },
}

const RISK_COLORS = {
  low: 'text-emerald-400',
  medium: 'text-amber-400',
  'medium-high': 'text-orange-400',
  high: 'text-red-400',
}

const SIGNAL_STYLES = {
  strong_entry: { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40' },
  moderate_entry: { bg: 'bg-amber-500/20', text: 'text-amber-300', border: 'border-amber-500/40' },
  weak: { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/40' },
}

export default function PredefinedStrategies() {
  const [strategies, setStrategies] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [checkResult, setCheckResult] = useState(null)
  const [checking, setChecking] = useState(false)
  const [checkSymbol, setCheckSymbol] = useState('NIFTY')
  const [filterCat, setFilterCat] = useState('all')

  useEffect(() => {
    fetch(`${API_BASE}/api/predefined-strategies`)
      .then(r => r.json()).then(setStrategies).catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function checkStrategy(strategyId) {
    setChecking(true)
    setCheckResult(null)
    try {
      const res = await fetch(`${API_BASE}/api/predefined-strategies/${strategyId}/check/${checkSymbol}`)
      if (res.ok) setCheckResult(await res.json())
    } catch { /* ignore */ }
    setChecking(false)
  }

  const categories = [...new Set(strategies.map(s => s.category))]
  const filtered = filterCat === 'all' ? strategies : strategies.filter(s => s.category === filterCat)

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white">F&O Trading Strategies</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          13 proven strategies for NIFTY / BANKNIFTY options — from conservative to aggressive
        </p>
      </div>

      {/* Category filter */}
      <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
        <button
          onClick={() => setFilterCat('all')}
          className={`px-2.5 py-1 rounded text-xs font-medium border whitespace-nowrap transition-colors ${
            filterCat === 'all' ? 'bg-slate-700 text-white border-slate-600' : 'text-slate-400 border-slate-700 hover:text-slate-300'
          }`}
        >
          All ({strategies.length})
        </button>
        {categories.map(cat => {
          const first = strategies.find(s => s.category === cat)
          const count = strategies.filter(s => s.category === cat).length
          const c = CAT_COLORS[first?.category_color] ?? CAT_COLORS.slate
          return (
            <button
              key={cat}
              onClick={() => setFilterCat(cat)}
              className={`px-2.5 py-1 rounded text-xs font-medium border whitespace-nowrap transition-colors ${
                filterCat === cat ? `${c.bg} ${c.text} ${c.border}` : 'text-slate-400 border-slate-700 hover:text-slate-300'
              }`}
            >
              {first?.category_icon} {first?.category_label} ({count})
            </button>
          )
        })}
      </div>

      {loading ? (
        <p className="text-slate-500 text-sm animate-pulse py-8 text-center">Loading strategies…</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map(s => {
            const c = CAT_COLORS[s.category_color] ?? CAT_COLORS.slate
            const isSelected = selected === s.id

            return (
              <div
                key={s.id}
                className={`bg-slate-800/80 border rounded-xl p-4 transition-all cursor-pointer ${
                  isSelected ? `${c.border} ring-1 ring-${s.category_color}-500/20` : 'border-slate-700 hover:border-slate-600'
                }`}
                onClick={() => { setSelected(isSelected ? null : s.id); setCheckResult(null) }}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base">{s.category_icon}</span>
                    <h3 className="text-sm font-bold text-white">{s.name}</h3>
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${c.bg} ${c.text} ${c.border}`}>
                    {s.category_label}
                  </span>
                </div>

                <p className="text-xs text-slate-400 mb-3">{s.description}</p>

                {/* Quick stats */}
                <div className="grid grid-cols-4 gap-2 mb-3">
                  <div>
                    <p className="text-[10px] text-slate-500">Risk</p>
                    <p className={`text-xs font-semibold capitalize ${RISK_COLORS[s.risk] ?? 'text-slate-300'}`}>{s.risk}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500">Win Rate</p>
                    <p className="text-xs font-semibold text-slate-300">{s.win_rate}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500">Capital</p>
                    <p className="text-xs font-semibold text-slate-300">{s.capital}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500">Best For</p>
                    <p className="text-[10px] text-slate-400">{s.best_for}</p>
                  </div>
                </div>

                {/* Expanded details */}
                {isSelected && (
                  <div className="space-y-3 pt-3 border-t border-slate-700/50">
                    {/* Legs */}
                    <div>
                      <h4 className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Trade Legs</h4>
                      <div className="space-y-1">
                        {s.legs.map((leg, i) => (
                          <div key={i} className={`flex items-center gap-2 px-2 py-1 rounded text-xs ${
                            leg.action === 'buy' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300'
                          }`}>
                            <span className="font-bold uppercase text-[10px] w-8">{leg.action}</span>
                            <span>{leg.label}</span>
                            {leg.qty && <span className="text-slate-500">×{leg.qty}</span>}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Entry rules */}
                    <div>
                      <h4 className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Entry Conditions</h4>
                      {s.entry_rules.map((r, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs py-0.5">
                          <span className="text-blue-400 font-mono text-[10px] w-12 shrink-0">{r.indicator}</span>
                          <span className="text-slate-300">{r.description}</span>
                        </div>
                      ))}
                    </div>

                    {/* Exit rules */}
                    <div>
                      <h4 className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Exit Rules</h4>
                      {s.exit_rules.map((r, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs py-0.5">
                          <span className={`text-[10px] font-mono w-12 shrink-0 ${
                            r.type === 'profit' ? 'text-emerald-400' : r.type === 'stop_loss' ? 'text-red-400' : 'text-amber-400'
                          }`}>{r.type === 'stop_loss' ? 'SL' : r.type.toUpperCase()}</span>
                          <span className="text-slate-300">{r.value}</span>
                        </div>
                      ))}
                    </div>

                    {/* Max profit/loss */}
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-emerald-500/5 border border-emerald-500/20 rounded px-2 py-1.5">
                        <p className="text-[10px] text-emerald-400">Max Profit</p>
                        <p className="text-xs text-emerald-300">{s.max_profit}</p>
                      </div>
                      <div className="bg-red-500/5 border border-red-500/20 rounded px-2 py-1.5">
                        <p className="text-[10px] text-red-400">Max Loss</p>
                        <p className="text-xs text-red-300">{s.max_loss}</p>
                      </div>
                    </div>

                    {/* Check against live data */}
                    <div className="flex items-center gap-2 pt-2 border-t border-slate-700/50">
                      <span className="text-xs text-slate-500">Check for:</span>
                      {['NIFTY', 'BANKNIFTY'].map(sym => (
                        <button
                          key={sym}
                          onClick={(e) => { e.stopPropagation(); setCheckSymbol(sym) }}
                          className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-colors ${
                            checkSymbol === sym
                              ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                              : 'border-slate-600 text-slate-400 hover:text-slate-300'
                          }`}
                        >
                          {sym}
                        </button>
                      ))}
                      <button
                        onClick={(e) => { e.stopPropagation(); checkStrategy(s.id) }}
                        disabled={checking}
                        className="ml-auto px-3 py-1 rounded-lg text-xs font-medium border
                                   bg-emerald-500/10 border-emerald-500/30 text-emerald-300
                                   hover:bg-emerald-500/20 disabled:opacity-50 transition-colors"
                      >
                        {checking ? '↻ Checking…' : '▶ Check Now'}
                      </button>
                    </div>

                    {/* Check results */}
                    {checkResult && checkResult.strategy_id === s.id && (
                      <div className="space-y-2">
                        {/* Signal badge */}
                        {(() => {
                          const sig = SIGNAL_STYLES[checkResult.signal] ?? SIGNAL_STYLES.weak
                          return (
                            <div className={`px-3 py-2 rounded-lg border ${sig.bg} ${sig.border}`}>
                              <div className="flex items-center justify-between">
                                <span className={`text-sm font-bold ${sig.text}`}>
                                  {checkResult.signal_label}
                                </span>
                                <span className={`text-xs ${sig.text}`}>
                                  {checkResult.met_count}/{checkResult.total_rules} conditions met ({checkResult.met_percentage}%)
                                </span>
                              </div>
                              {checkResult.spot_price > 0 && (
                                <p className="text-xs text-slate-400 mt-1">
                                  Spot: ₹{checkResult.spot_price?.toLocaleString('en-IN')} | PCR: {checkResult.pcr}
                                </p>
                              )}
                            </div>
                          )
                        })()}

                        {/* Condition results */}
                        {checkResult.conditions?.map((cond, i) => (
                          <div key={i} className={`flex items-start gap-2 px-2 py-1.5 rounded text-xs ${
                            cond.met === true ? 'bg-emerald-500/10' : cond.met === false ? 'bg-red-500/10' : 'bg-slate-700/30'
                          }`}>
                            <span className="text-sm">
                              {cond.met === true ? '✅' : cond.met === false ? '❌' : '❓'}
                            </span>
                            <div>
                              <span className="font-medium text-slate-300">{cond.description}</span>
                              <p className="text-[10px] text-slate-500">{cond.indicator}: {cond.current_value}</p>
                            </div>
                          </div>
                        ))}

                        {/* Suggested strikes */}
                        {checkResult.suggested_legs?.length > 0 && checkResult.spot_price > 0 && (
                          <div>
                            <h4 className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Suggested Strikes</h4>
                            {checkResult.suggested_legs.map((leg, i) => (
                              <div key={i} className={`flex items-center justify-between px-2 py-1 rounded text-xs ${
                                leg.action === 'buy' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300'
                              }`}>
                                <span>{leg.action.toUpperCase()} {leg.type} — {leg.label}</span>
                                <span className="font-bold tabular-nums">₹{leg.suggested_strike}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </main>
  )
}
