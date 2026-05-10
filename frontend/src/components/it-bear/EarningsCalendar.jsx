/**
 * EarningsCalendar — upcoming earnings for IT stocks.
 *
 * Countdown, historical beat/miss, 7-21 day sweet spot highlight,
 * expandable rows, filter by India/US, "Suggest Strategy" button.
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import ITBearNav from './ITBearNav'
import { fmtNum, fmtPct, daysUntil, earningsDaysColor, earningsSweetSpotBorder } from '../../utils/format'

const API_BASE = 'http://localhost:8000'

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
      <p className="text-slate-500 text-sm ml-3">Loading earnings data…</p>
    </div>
  )
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center my-6">
      <p className="text-red-400 text-sm mb-3">{message}</p>
      <button
        onClick={onRetry}
        className="px-4 py-2 text-xs font-medium rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors"
      >
        Retry
      </button>
    </div>
  )
}

function BeatMissChip({ result }) {
  if (!result) return <span className="text-slate-600">—</span>
  const cfg = {
    beat: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    miss: 'bg-red-500/15 text-red-300 border-red-500/30',
    'in-line': 'bg-slate-700 text-slate-400 border-slate-600',
  }
  const label = {
    beat: 'Beat',
    miss: 'Miss',
    'in-line': 'In-line',
  }
  const cls = cfg[result] ?? cfg['in-line']
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cls}`}>
      {label[result] ?? result}
    </span>
  )
}

function QuarterRow({ q }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-xs border-b border-slate-700/40 last:border-0">
      <span className="text-slate-400 w-16 shrink-0">{q.period}</span>
      <span className="text-slate-300 tabular-nums w-24 text-right">
        {q.revenue ? fmtNum(q.revenue, 0) : '—'}
      </span>
      <span className={`tabular-nums w-16 text-right ${
        (q.revenue_yoy ?? 0) < 0 ? 'text-red-400' : 'text-emerald-400'
      }`}>
        {q.revenue_yoy !== undefined ? fmtPct(q.revenue_yoy, 1) : '—'}
      </span>
      <span className="tabular-nums w-14 text-right text-slate-300">
        {q.eps !== undefined ? fmtNum(q.eps, 2) : '—'}
      </span>
      <span className="w-16 text-right">
        <BeatMissChip result={q.beat_miss} />
      </span>
    </div>
  )
}

function EarningsRow({ item, isExpanded, onToggle, onSuggestStrategy }) {
  const days = daysUntil(item.earnings_date)
  const daysColor = earningsDaysColor(days)
  const sweetSpot = days !== null && days >= 7 && days <= 21
  const borderClass = sweetSpot ? 'border-amber-500/40' : 'border-slate-700/40'
  const quarters = item.recent_quarters ?? []

  const daysLabel = days === null ? '—'
    : days < 0 ? 'Past'
    : days === 0 ? 'Today'
    : `${days}d`

  return (
    <div className={`border-b ${borderClass} transition-colors ${sweetSpot ? 'bg-amber-500/5' : ''}`}>
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-700/20 transition-colors"
        onClick={onToggle}
      >
        {/* Flag + Symbol */}
        <span className="text-base shrink-0">{item.country === 'US' ? '🇺🇸' : '🇮🇳'}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white">{item.symbol}</span>
            <span className="text-[10px] text-slate-500 truncate hidden sm:block">{item.name}</span>
            {sweetSpot && (
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-amber-500/20 border-amber-500/40 text-amber-300 shrink-0">
                Sweet Spot
              </span>
            )}
          </div>
        </div>

        {/* Date */}
        <div className="text-right shrink-0 w-28">
          <p className="text-xs text-slate-300 tabular-nums">{item.earnings_date ?? '—'}</p>
        </div>

        {/* Days away */}
        <div className="text-right shrink-0 w-16">
          <p className={`text-sm font-bold tabular-nums ${daysColor}`}>{daysLabel}</p>
        </div>

        {/* Last quarter result */}
        <div className="hidden sm:block shrink-0 w-16 text-right">
          {quarters.length > 0
            ? <BeatMissChip result={quarters[0]?.beat_miss} />
            : <span className="text-slate-600 text-xs">—</span>
          }
        </div>

        {/* Strategy button */}
        <button
          onClick={e => { e.stopPropagation(); onSuggestStrategy(item.symbol) }}
          className="shrink-0 px-2 py-1 text-[10px] font-medium rounded border bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25 transition-colors"
        >
          Strategy
        </button>

        {/* Expand chevron */}
        <span className={`text-slate-500 text-xs transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
          &rsaquo;
        </span>
      </div>

      {/* Expanded quarterly details */}
      {isExpanded && (
        <div className="px-4 pb-4 bg-slate-900/30">
          {quarters.length === 0 ? (
            <p className="text-xs text-slate-500 py-2">No quarterly data available.</p>
          ) : (
            <>
              <div className="flex items-center justify-between py-1.5 text-[10px] text-slate-500 uppercase border-b border-slate-700/50 mb-1">
                <span className="w-16">Period</span>
                <span className="w-24 text-right">Revenue</span>
                <span className="w-16 text-right">YoY %</span>
                <span className="w-14 text-right">EPS</span>
                <span className="w-16 text-right">Result</span>
              </div>
              {quarters.slice(0, 4).map((q, i) => (
                <QuarterRow key={i} q={q} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'IN', label: 'India' },
  { id: 'US', label: 'US' },
]

export default function EarningsCalendar() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')
  const [expanded, setExpanded] = useState(new Set())
  const navigate = useNavigate()

  const fetchEarnings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/it-bear/earnings?days_ahead=90`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const json = await res.json()
      setData(Array.isArray(json) ? json : json.earnings ?? [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchEarnings() }, [fetchEarnings])

  function toggleExpand(symbol) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(symbol) ? next.delete(symbol) : next.add(symbol)
      return next
    })
  }

  function handleSuggestStrategy(symbol) {
    navigate(`/it-bear/strategy-builder/${symbol}`)
  }

  const filtered = data.filter(item => {
    if (filter === 'all') return true
    return item.country === filter
  })

  // Sort by earnings date ascending (nearest first)
  const sorted = [...filtered].sort((a, b) => {
    const da = daysUntil(a.earnings_date) ?? 9999
    const db = daysUntil(b.earnings_date) ?? 9999
    return da - db
  })

  const sweetSpotCount = sorted.filter(s => {
    const d = daysUntil(s.earnings_date)
    return d !== null && d >= 7 && d <= 21
  }).length

  return (
    <div>
      <ITBearNav />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <h1 className="text-2xl font-black text-white">Earnings Calendar</h1>
            <p className="text-slate-500 text-xs mt-1">
              IT stock earnings — pre-earnings options plays (7-21 day window)
            </p>
          </div>
          {sweetSpotCount > 0 && (
            <div className="shrink-0 px-3 py-2 rounded-xl bg-amber-500/15 border border-amber-500/30 text-center">
              <p className="text-xs font-bold text-amber-300">{sweetSpotCount}</p>
              <p className="text-[10px] text-amber-400">Sweet Spot</p>
            </div>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-2 mb-5">
          {FILTERS.map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                filter === f.id
                  ? 'bg-red-500/20 border-red-500/30 text-red-300'
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600'
              }`}
            >
              {f.label}
            </button>
          ))}
          <span className="text-[10px] text-slate-600 ml-2">{sorted.length} stocks</span>
        </div>

        {loading && <Spinner />}
        {!loading && error && <ErrorState message={error} onRetry={fetchEarnings} />}

        {!loading && !error && (
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
            {/* Sticky table header */}
            <div className="flex items-center gap-3 px-4 py-2 bg-slate-900/60 border-b border-slate-700 sticky top-0 z-10">
              <span className="text-[10px] text-slate-500 uppercase w-6">Mkt</span>
              <span className="flex-1 text-[10px] text-slate-500 uppercase">Stock</span>
              <span className="text-[10px] text-slate-500 uppercase w-28 text-right">Earnings Date</span>
              <span className="text-[10px] text-slate-500 uppercase w-16 text-right">Days Away</span>
              <span className="text-[10px] text-slate-500 uppercase hidden sm:block w-16 text-right">Last Q</span>
              <span className="text-[10px] text-slate-500 uppercase w-16 text-right">Action</span>
              <span className="w-4" />
            </div>

            {sorted.length === 0 ? (
              <div className="text-center py-10">
                <p className="text-slate-400 text-sm">No upcoming earnings found.</p>
                <p className="text-slate-600 text-xs mt-1">
                  {filter !== 'all' ? 'Try changing the filter.' : 'Backend earnings endpoint may not have data yet.'}
                </p>
              </div>
            ) : (
              sorted.map(item => (
                <EarningsRow
                  key={item.symbol}
                  item={item}
                  isExpanded={expanded.has(item.symbol)}
                  onToggle={() => toggleExpand(item.symbol)}
                  onSuggestStrategy={handleSuggestStrategy}
                />
              ))
            )}
          </div>
        )}

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-4 text-[10px] text-slate-500">
          <span><span className="text-red-400 font-bold">Red</span> = &lt;3 days (too close)</span>
          <span><span className="text-amber-400 font-bold">Amber</span> = 3-7 days (entry risk)</span>
          <span><span className="text-emerald-400 font-bold">Emerald</span> = 7-21 days (sweet spot)</span>
          <span><span className="text-slate-400 font-bold">Slate</span> = &gt;21 days (too early)</span>
          <span>
            <span className="px-1 rounded border bg-amber-500/20 border-amber-500/40 text-amber-300">Sweet Spot</span>
            {' '} = ideal pre-earnings window
          </span>
        </div>
      </main>
    </div>
  )
}
