/**
 * Backtest — the real backtesting workbench.
 * Pick an engine-ready strategy, ensure local historical data coverage,
 * replay bars through the engine, and inspect metrics / equity / trades.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  PageHeader, Card, CardHeader, Button, StatusBadge, MetricCard, DataTable,
  SegmentedControl, LoadingSpinner, EmptyState, ErrorState,
  fmtINR, fmtNum, fmtPct, pnlColor,
} from '../ui'
import { IconBacktest } from '../ui/icons'

const API_BASE = 'http://localhost:8000'

const QUICK_SYMBOLS = ['^NSEI', '^NSEBANK', 'GC=F', 'SI=F', 'CL=F', 'NG=F']
const TIMEFRAMES = [
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '1d', label: '1d' },
]

const INPUT_CLS = `w-full bg-surface-2 border border-edge rounded-lg px-3 py-2 text-sm text-ink
  placeholder:text-ink-subtle focus:outline-none focus:border-brand/60 transition-colors`
const LABEL_CLS = 'block text-[11px] font-semibold uppercase tracking-wide text-ink-subtle mb-1.5'

const sleep = ms => new Promise(r => setTimeout(r, ms))
const toISODate = d => d.toISOString().slice(0, 10)

function parseSymbolList(text) {
  return String(text || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
}

/** ISO-ish ts -> "MM-DD HH:mm" */
function fmtTs(ts) {
  const s = String(ts ?? '')
  if (s.length >= 16) return `${s.slice(5, 10)} ${s.slice(11, 16)}`
  return s || '—'
}

/** ts (ISO string or epoch s/ms) -> "YYYY-MM-DD" */
function tsToDate(ts) {
  if (ts === null || ts === undefined) return ''
  if (typeof ts === 'number' && Number.isFinite(ts)) {
    try {
      return new Date(ts > 1e12 ? ts : ts * 1000).toISOString().slice(0, 10)
    } catch {
      return String(ts)
    }
  }
  return String(ts).slice(0, 10)
}

function numOrNull(v) {
  const n = Number(v)
  return v === null || v === undefined || v === '' || Number.isNaN(n) ? null : n
}

/** First non-null metric among candidate keys. */
function pickMetric(m, keys) {
  for (const k of keys) {
    const v = m?.[k]
    if (v !== undefined && v !== null) return v
  }
  return null
}

function parseSymbolsField(v) {
  if (Array.isArray(v)) return v
  if (typeof v === 'string') {
    try {
      const j = JSON.parse(v)
      if (Array.isArray(j)) return j
    } catch { /* not JSON */ }
    return parseSymbolList(v)
  }
  return []
}

function deriveFetchDays(start, end, timeframe) {
  const ms = new Date(end) - new Date(start)
  let days = Math.ceil(ms / 86400000) + 1
  if (!Number.isFinite(days) || days < 7) days = 7
  if (timeframe !== '1d') days = Math.min(days, 59) // intraday provider window cap
  return Math.min(days, 3650)
}

const DIRECTION_TONE = { long: 'success', long_ce: 'success', short: 'danger', long_pe: 'danger' }

function reasonTone(reason) {
  const s = String(reason || '').toLowerCase()
  if (s.includes('target') || s.includes('tp')) return 'success'
  if (s.includes('stop') || s.includes('sl')) return 'danger'
  if (s.includes('time') || s.includes('eod')) return 'warning'
  if (s.includes('signal')) return 'info'
  return 'neutral'
}

function runStatusTone(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'done') return 'success'
  if (s === 'error') return 'danger'
  if (s === 'running' || s === 'pending' || s === 'queued') return 'warning'
  return 'neutral'
}

/* ---------------------------------------------------------------- */
/* Inline equity-curve chart                                         */
/* ---------------------------------------------------------------- */

function EquityCurve({ equity }) {
  const gradId = useMemo(() => `eqgrad-${Math.random().toString(36).slice(2, 9)}`, [])
  const pts = useMemo(
    () => (equity || []).filter(p => Array.isArray(p) && p.length >= 2 && numOrNull(p[1]) !== null),
    [equity],
  )

  if (pts.length < 2) {
    return <EmptyState title="No trades" description="Not enough equity points to draw a curve." icon={IconBacktest} />
  }

  const W = 720, H = 220, padL = 10, padR = 10, padT = 12, padB = 24
  const ys = pts.map(p => Number(p[1]))
  const rawMin = Math.min(...ys)
  const rawMax = Math.max(...ys)
  const span = (rawMax - rawMin) || Math.abs(rawMax) || 1
  const min = rawMin - span * 0.05
  const max = rawMax + span * 0.05
  const iw = W - padL - padR
  const ih = H - padT - padB
  const xAt = i => padL + (pts.length === 1 ? 0 : (i / (pts.length - 1)) * iw)
  const yAt = v => padT + (1 - (v - min) / (max - min)) * ih

  const line = pts.map((p, i) => `${xAt(i).toFixed(1)},${yAt(Number(p[1])).toFixed(1)}`).join(' ')
  const area = `${padL.toFixed(1)},${(padT + ih).toFixed(1)} ${line} ${(padL + iw).toFixed(1)},${(padT + ih).toFixed(1)}`

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto text-brand" role="img" aria-label="Equity curve">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      <polygon points={area} fill={`url(#${gradId})`} stroke="none" />
      <polyline
        points={line}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      <g className="text-ink-subtle" fontSize="10" style={{ fontFamily: 'var(--font-mono)' }}>
        {/* y-axis min / max */}
        <text x={padL} y={padT + 4} fill="currentColor">{fmtINR(rawMax)}</text>
        <text x={padL} y={padT + ih - 3} fill="currentColor">{fmtINR(rawMin)}</text>
        {/* x-axis first / last date */}
        <text x={padL} y={H - 8} fill="currentColor">{tsToDate(pts[0][0])}</text>
        <text x={padL + iw} y={H - 8} fill="currentColor" textAnchor="end">{tsToDate(pts[pts.length - 1][0])}</text>
      </g>
    </svg>
  )
}

/* ---------------------------------------------------------------- */
/* Page                                                              */
/* ---------------------------------------------------------------- */

export default function Backtest() {
  const [searchParams] = useSearchParams()

  // --- setup form state
  const [strategies, setStrategies] = useState([])
  const [engineSlugs, setEngineSlugs] = useState(() => new Set())
  const [setupError, setSetupError] = useState(null)
  const [strategySlug, setStrategySlug] = useState(() => searchParams.get('strategy') || '')
  const [symbols, setSymbols] = useState([])
  const [symbolInput, setSymbolInput] = useState('')
  const [timeframe, setTimeframe] = useState('5m')
  const [start, setStart] = useState(() => toISODate(new Date(Date.now() - 45 * 86400000)))
  const [end, setEnd] = useState(() => toISODate(new Date()))
  const [initialCapital, setInitialCapital] = useState(100000)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [overridesText, setOverridesText] = useState('')
  const [overridesError, setOverridesError] = useState(null)
  const [formError, setFormError] = useState(null)

  // --- data coverage state
  const [coverage, setCoverage] = useState([])
  const [coverageLoading, setCoverageLoading] = useState(true)
  const [fetching, setFetching] = useState(false)
  const [fetchResults, setFetchResults] = useState(null) // array | null
  const [fetchError, setFetchError] = useState(null)

  // --- run state
  const [starting, setStarting] = useState(false)
  const [polling, setPolling] = useState(false)
  const [activeRunId, setActiveRunId] = useState(null)
  const [runError, setRunError] = useState(null)
  const [result, setResult] = useState(null)

  // --- past runs
  const [runs, setRuns] = useState([])

  const pollSeq = useRef(0)
  useEffect(() => () => { pollSeq.current += 1 }, []) // cancel polling on unmount

  /* ------------------------- loaders ------------------------- */

  const loadStrategies = useCallback(async () => {
    setSetupError(null)
    try {
      const [mkRes, engRes] = await Promise.all([
        fetch(`${API_BASE}/api/marketplace/strategies`),
        fetch(`${API_BASE}/api/backtest/engine-strategies`),
      ])
      if (!mkRes.ok) throw new Error(`Failed to load strategies (HTTP ${mkRes.status})`)
      const mkData = await mkRes.json()
      setStrategies(Array.isArray(mkData) ? mkData : [])
      if (engRes.ok) {
        const engData = await engRes.json()
        const slugs = Array.isArray(engData) ? engData : (engData?.slugs ?? [])
        setEngineSlugs(new Set(Array.isArray(slugs) ? slugs : []))
      }
    } catch (e) {
      setSetupError(e.message || 'Failed to load strategies')
    }
  }, [])

  const loadCoverage = useCallback(async () => {
    setCoverageLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/data/coverage`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setCoverage(Array.isArray(data) ? data : [])
    } catch {
      setCoverage([])
    } finally {
      setCoverageLoading(false)
    }
  }, [])

  const loadRuns = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/backtest/runs`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setRuns(Array.isArray(data) ? data : (data?.runs ?? []))
    } catch {
      /* past runs are non-critical */
    }
  }, [])

  useEffect(() => {
    loadStrategies()
    loadCoverage()
    loadRuns()
  }, [loadStrategies, loadCoverage, loadRuns])

  /* ------------------------- symbols ------------------------- */

  /** Merge any pending free-text into the chip list; returns the merged list. */
  const commitSymbols = useCallback(() => {
    const pending = parseSymbolList(symbolInput)
    let merged = symbols
    if (pending.length) {
      merged = [...symbols]
      for (const p of pending) if (!merged.includes(p)) merged.push(p)
      setSymbols(merged)
      setSymbolInput('')
    }
    return merged
  }, [symbolInput, symbols])

  const addSymbol = useCallback(sym => {
    setSymbols(prev => (prev.includes(sym) ? prev : [...prev, sym]))
  }, [])

  const removeSymbol = useCallback(sym => {
    setSymbols(prev => prev.filter(s => s !== sym))
  }, [])

  /* ------------------------- data fetch ------------------------- */

  const fetchData = useCallback(async () => {
    const syms = commitSymbols()
    setFetchError(null)
    setFetchResults(null)
    if (syms.length === 0) {
      setFetchError('Add at least one symbol first.')
      return
    }
    setFetching(true)
    try {
      const res = await fetch(`${API_BASE}/api/data/fetch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: syms,
          timeframe,
          days: deriveFetchDays(start, end, timeframe),
          source: 'auto',
        }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const j = await res.json()
          msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
        } catch { /* keep msg */ }
        throw new Error(msg)
      }
      const data = await res.json()
      setFetchResults(Array.isArray(data) ? data : [])
      await loadCoverage()
    } catch (e) {
      setFetchError(e.message || 'Fetch failed')
    } finally {
      setFetching(false)
    }
  }, [commitSymbols, timeframe, start, end, loadCoverage])

  /* ------------------------- run + poll ------------------------- */

  const pollRun = useCallback(async runId => {
    const token = ++pollSeq.current
    setPolling(true)
    setRunError(null)
    setResult(null)
    setActiveRunId(runId)
    try {
      for (let i = 0; i < 120; i++) {
        let run
        try {
          const res = await fetch(`${API_BASE}/api/backtest/runs/${runId}`)
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          run = await res.json()
        } catch (e) {
          if (pollSeq.current !== token) return
          setRunError(e.message || 'Failed to poll run')
          return
        }
        if (pollSeq.current !== token) return
        const status = String(run.status || '').toLowerCase()
        if (status === 'done') {
          setResult(run)
          loadRuns()
          return
        }
        if (status === 'error') {
          setRunError(run.error || run.detail || 'Backtest failed')
          loadRuns()
          return
        }
        await sleep(1500)
        if (pollSeq.current !== token) return
      }
      setRunError('Timed out waiting for the backtest to finish (120 polls).')
    } finally {
      if (pollSeq.current === token) setPolling(false)
    }
  }, [loadRuns])

  const runBacktest = useCallback(async () => {
    setFormError(null)
    setOverridesError(null)
    setRunError(null)

    const syms = commitSymbols()
    if (!strategySlug) { setFormError('Pick a strategy first.'); return }
    if (syms.length === 0) { setFormError('Add at least one symbol.'); return }
    if (!start || !end || new Date(start) > new Date(end)) {
      setFormError('Pick a valid start/end date range.')
      return
    }

    let overrides = {}
    if (overridesText.trim()) {
      try {
        overrides = JSON.parse(overridesText)
        if (typeof overrides !== 'object' || overrides === null || Array.isArray(overrides)) {
          throw new Error('must be a JSON object')
        }
      } catch (e) {
        setShowAdvanced(true)
        setOverridesError(`Invalid JSON: ${e.message}`)
        return
      }
    }

    setStarting(true)
    try {
      const res = await fetch(`${API_BASE}/api/backtest/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_slug: strategySlug,
          symbols: syms,
          timeframe,
          start,
          end,
          initial_capital: Number(initialCapital) || 100000,
          config_overrides: overrides,
        }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const j = await res.json()
          msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
        } catch { /* keep msg */ }
        throw new Error(msg)
      }
      const data = await res.json()
      if (!data?.run_id && data?.run_id !== 0) throw new Error('Backend did not return a run_id')
      pollRun(data.run_id)
    } catch (e) {
      setRunError(e.message || 'Failed to start backtest')
    } finally {
      setStarting(false)
    }
  }, [commitSymbols, strategySlug, start, end, overridesText, timeframe, initialCapital, pollRun])

  /* ------------------------- derived ------------------------- */

  const strategyOptions = useMemo(() => {
    const anyEngine = engineSlugs.size > 0
    const opts = strategies.map(s => ({
      slug: s.slug,
      name: s.name || s.slug,
      engineReady: engineSlugs.has(s.slug),
      enabled: !anyEngine || engineSlugs.has(s.slug),
    }))
    opts.sort((a, b) => (a.engineReady === b.engineReady
      ? a.name.localeCompare(b.name)
      : a.engineReady ? -1 : 1))
    return opts
  }, [strategies, engineSlugs])

  const coverageRows = useMemo(() => coverage.map((c, i) => ({
    id: `${c.symbol}-${c.timeframe}-${i}`,
    symbol: c.symbol,
    timeframe: c.timeframe,
    bar_count: numOrNull(c.bar_count),
    first: tsToDate(c.first_ts),
    last: tsToDate(c.last_ts),
    source: c.source ?? '—',
  })), [coverage])

  const metrics = result?.metrics ?? {}
  const netPnl = numOrNull(pickMetric(metrics, ['net_pnl', 'net_profit', 'total_pnl', 'pnl']))
  const winRate = numOrNull(pickMetric(metrics, ['win_rate', 'win_rate_pct', 'winrate']))
  const tradeCount = numOrNull(pickMetric(metrics, ['trades', 'num_trades', 'total_trades', 'trade_count']))
    ?? (Array.isArray(result?.trades) ? result.trades.length : null)
  const profitFactor = numOrNull(pickMetric(metrics, ['profit_factor']))
  const maxDD = numOrNull(pickMetric(metrics, ['max_drawdown_pct', 'max_drawdown', 'max_dd_pct']))
  const sharpe = numOrNull(pickMetric(metrics, ['sharpe', 'sharpe_ratio']))
  const assumptions = Array.isArray(metrics.assumptions) ? metrics.assumptions : []

  const tradeRows = useMemo(() => (result?.trades ?? []).map((t, i) => ({
    id: i,
    entry_ts: t.entry_ts ?? t.entry_time ?? t.entry_date ?? '',
    exit_ts: t.exit_ts ?? t.exit_time ?? t.exit_date ?? '',
    symbol: t.symbol ?? '—',
    direction: t.direction ?? t.side ?? '—',
    entry_price: numOrNull(t.entry_price ?? t.entry_px ?? t.entry),
    exit_price: numOrNull(t.exit_price ?? t.exit_px ?? t.exit),
    pnl: numOrNull(t.pnl ?? t.net_pnl),
    pnl_pct: numOrNull(t.pnl_pct ?? t.pct ?? t.return_pct),
    reason: t.exit_reason ?? t.reason ?? '—',
  })), [result])

  const monthlyRows = useMemo(() => {
    const monthly = metrics?.monthly
    if (!monthly) return []
    if (Array.isArray(monthly)) {
      return monthly.map(m => ({
        month: m.month ?? m.period ?? '—',
        pnl: numOrNull(m.pnl ?? m.net_pnl),
        trades: numOrNull(m.trades ?? m.count ?? m.num_trades),
        win_rate: numOrNull(m.win_rate),
      }))
    }
    if (typeof monthly === 'object') {
      return Object.entries(monthly).map(([month, v]) => (
        typeof v === 'object' && v !== null
          ? {
              month,
              pnl: numOrNull(v.pnl ?? v.net_pnl),
              trades: numOrNull(v.trades ?? v.count),
              win_rate: numOrNull(v.win_rate),
            }
          : { month, pnl: numOrNull(v), trades: null, win_rate: null }
      ))
    }
    return []
  }, [metrics])

  const runRows = useMemo(() => runs.map(r => {
    const syms = parseSymbolsField(r.symbols)
    return {
      ...r,
      id: r.id ?? r.run_id,
      strategy: r.strategy_slug ?? r.strategy ?? '—',
      symbols_str: syms.join(', ') || '—',
      dates_str: `${tsToDate(r.start) || '—'} → ${tsToDate(r.end) || '—'}`,
      net_pnl: numOrNull(pickMetric(r.metrics ?? {}, ['net_pnl', 'net_profit', 'total_pnl', 'pnl'])),
    }
  }), [runs])

  /* ------------------------- render ------------------------- */

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Backtest"
        subtitle="Replay any engine-ready strategy over your local historical database"
        icon={IconBacktest}
      />

      {setupError && <ErrorState message={setupError} onRetry={loadStrategies} />}

      {/* ---------------- Setup ---------------- */}
      <Card className="mb-4">
        <CardHeader title="Setup" subtitle="Strategy, universe, window, and capital" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Strategy */}
          <div>
            <label className={LABEL_CLS}>Strategy</label>
            <select
              value={strategySlug}
              onChange={e => setStrategySlug(e.target.value)}
              className={INPUT_CLS}
            >
              <option value="">Select a strategy…</option>
              {strategyOptions.map(o => (
                <option key={o.slug} value={o.slug} disabled={!o.enabled}>
                  {o.name}{o.engineReady ? ' · engine-ready' : ''}
                </option>
              ))}
              {strategySlug && !strategies.some(s => s.slug === strategySlug) && (
                <option value={strategySlug}>{strategySlug}</option>
              )}
            </select>
            <p className="text-[11px] text-ink-subtle mt-1.5">
              {engineSlugs.size > 0
                ? `${engineSlugs.size} engine-ready ${engineSlugs.size === 1 ? 'strategy' : 'strategies'} available`
                : 'Engine-ready list unavailable — all strategies enabled'}
            </p>
          </div>

          {/* Timeframe */}
          <div>
            <label className={LABEL_CLS}>Timeframe</label>
            <SegmentedControl options={TIMEFRAMES} value={timeframe} onChange={setTimeframe} />
          </div>

          {/* Symbols */}
          <div className="md:col-span-2">
            <label className={LABEL_CLS}>Symbols</label>
            <div className="flex gap-2">
              <input
                value={symbolInput}
                onChange={e => setSymbolInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); commitSymbols() } }}
                onBlur={commitSymbols}
                placeholder="Comma separated, e.g. ^NSEI, GC=F"
                className={INPUT_CLS}
              />
              <Button variant="secondary" onClick={commitSymbols}>Add</Button>
            </div>

            <div className="flex items-center gap-1.5 flex-wrap mt-2">
              {QUICK_SYMBOLS.map(s => (
                <button
                  key={s}
                  type="button"
                  onClick={() => addSymbol(s)}
                  disabled={symbols.includes(s)}
                  className="px-2 py-0.5 rounded-full text-[11px] font-medium tnum bg-surface-2 border border-edge
                             text-ink-muted hover:text-ink hover:border-edge-strong transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  + {s}
                </button>
              ))}
            </div>

            {symbols.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap mt-2.5">
                {symbols.map(s => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold tnum
                               bg-brand-soft border border-brand/25 text-brand"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => removeSymbol(s)}
                      className="hover:text-red-500 transition-colors leading-none"
                      aria-label={`Remove ${s}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Dates */}
          <div>
            <label className={LABEL_CLS}>Start date</label>
            <input type="date" value={start} onChange={e => setStart(e.target.value)} className={INPUT_CLS} />
          </div>
          <div>
            <label className={LABEL_CLS}>End date</label>
            <input type="date" value={end} onChange={e => setEnd(e.target.value)} className={INPUT_CLS} />
          </div>

          {/* Capital */}
          <div>
            <label className={LABEL_CLS}>Initial capital (₹)</label>
            <input
              type="number"
              min="1000"
              step="1000"
              value={initialCapital}
              onChange={e => setInitialCapital(e.target.value)}
              className={`${INPUT_CLS} tnum`}
            />
          </div>

          {/* Advanced overrides */}
          <div className="md:col-span-2">
            <button
              type="button"
              onClick={() => setShowAdvanced(v => !v)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted hover:text-ink transition-colors"
            >
              <span className={`inline-block transition-transform ${showAdvanced ? 'rotate-90' : ''}`}>▸</span>
              Advanced: config overrides (JSON)
            </button>
            {showAdvanced && (
              <div className="mt-2">
                <textarea
                  value={overridesText}
                  onChange={e => { setOverridesText(e.target.value); setOverridesError(null) }}
                  rows={5}
                  spellCheck={false}
                  placeholder='{"target_pct": 1.5, "stop_pct": 0.75}'
                  className={`w-full bg-surface-2 border rounded-lg px-3 py-2 text-sm text-ink tnum
                    placeholder:text-ink-subtle focus:outline-none transition-colors
                    ${overridesError ? 'border-red-500 focus:border-red-500' : 'border-edge focus:border-brand/60'}`}
                  style={{ fontFamily: 'var(--font-mono)' }}
                />
                {overridesError && <p className="text-xs text-red-500 mt-1">{overridesError}</p>}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* ---------------- Data coverage ---------------- */}
      <Card className="mb-4">
        <CardHeader
          title="Local data"
          subtitle="What the engine can replay right now — fetch anything missing"
          action={
            <Button variant="secondary" onClick={fetchData} loading={fetching}>
              Fetch / refresh selected symbols
            </Button>
          }
        />

        {fetchError && <p className="text-xs text-red-500 mb-3">{fetchError}</p>}
        {fetchResults && (
          <div className="mb-3 space-y-1">
            {fetchResults.map((r, i) => (
              <p key={`${r.symbol}-${i}`} className="text-xs">
                <span className="font-semibold tnum text-ink">{r.symbol}</span>
                {' — '}
                {r.error
                  ? <span className="text-red-500">{r.error}</span>
                  : (
                    <span className="text-ink-muted">
                      stored <span className="tnum text-emerald-500">{fmtNum(r.stored, 0)}</span> bars
                      {r.fetched !== undefined && <> of {fmtNum(r.fetched, 0)} fetched</>}
                      {r.source && <> · source {r.source}</>}
                    </span>
                  )}
              </p>
            ))}
          </div>
        )}

        {coverageLoading ? (
          <LoadingSpinner message="Loading coverage…" className="py-8" />
        ) : (
          <DataTable
            dense
            pageSize={8}
            columns={[
              { key: 'symbol', header: 'Symbol', className: 'font-medium tnum' },
              { key: 'timeframe', header: 'Timeframe' },
              { key: 'bar_count', header: 'Bars', align: 'right', render: r => fmtNum(r.bar_count, 0) },
              { key: 'first', header: 'First', className: 'tnum text-ink-muted' },
              { key: 'last', header: 'Last', className: 'tnum text-ink-muted' },
              { key: 'source', header: 'Source', className: 'text-ink-muted' },
            ]}
            rows={coverageRows}
            emptyMessage="No local data yet. Add symbols above and fetch."
          />
        )}
      </Card>

      {/* ---------------- Run ---------------- */}
      <div className="flex items-center gap-3 mb-6">
        <Button size="lg" onClick={runBacktest} loading={starting} disabled={polling}>
          Run backtest
        </Button>
        {formError && <p className="text-xs text-red-500">{formError}</p>}
        {activeRunId !== null && !polling && !runError && result && (
          <p className="text-xs text-ink-subtle tnum">Run #{activeRunId} finished</p>
        )}
      </div>

      {polling && <LoadingSpinner message="Replaying bars…" />}
      {runError && <ErrorState message={runError} />}

      {/* ---------------- Results ---------------- */}
      {!polling && result && String(result.status).toLowerCase() === 'done' && (
        <div className="mb-6">
          {assumptions.length > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/25 rounded-xl p-4 mb-4">
              <p className="text-xs font-semibold text-amber-600 dark:text-amber-300 mb-1.5">
                Assumptions baked into this run
              </p>
              <ul className="list-disc list-inside space-y-0.5">
                {assumptions.map((a, i) => (
                  <li key={i} className="text-xs text-ink-muted leading-relaxed">{String(a)}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
            <MetricCard
              label="Net P&L"
              value={fmtINR(netPnl)}
              variant={netPnl === null ? 'default' : netPnl >= 0 ? 'success' : 'danger'}
            />
            <MetricCard label="Win rate" value={winRate === null ? '—' : `${fmtNum(winRate, 1)}%`} />
            <MetricCard label="Trades" value={tradeCount === null ? '—' : fmtNum(tradeCount, 0)} />
            <MetricCard label="Profit factor" value={profitFactor === null ? '—' : fmtNum(profitFactor, 2)} />
            <MetricCard label="Max drawdown" value={maxDD === null ? '—' : `${fmtNum(maxDD, 1)}%`} />
            <MetricCard label="Sharpe" value={sharpe === null ? '—' : fmtNum(sharpe, 2)} />
          </div>

          <Card className="mb-4">
            <CardHeader title="Equity curve" subtitle={`Starting capital ${fmtINR(Number(initialCapital) || null)}`} />
            <EquityCurve equity={result.equity_curve} />
          </Card>

          <div className="mb-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-subtle mb-2">
              Trades ({tradeRows.length})
            </p>
            <DataTable
              dense
              pageSize={15}
              searchKeys={['symbol', 'direction', 'reason']}
              columns={[
                { key: 'entry_ts', header: 'Entry', className: 'tnum text-ink-muted', render: r => fmtTs(r.entry_ts) },
                { key: 'exit_ts', header: 'Exit', className: 'tnum text-ink-muted', render: r => fmtTs(r.exit_ts) },
                { key: 'symbol', header: 'Symbol', className: 'font-medium tnum' },
                {
                  key: 'direction', header: 'Direction',
                  render: r => (
                    <StatusBadge
                      label={r.direction}
                      tone={DIRECTION_TONE[String(r.direction).toLowerCase()] ?? 'neutral'}
                      dot={false}
                    />
                  ),
                },
                { key: 'entry_price', header: 'Entry px', align: 'right', render: r => fmtNum(r.entry_price, 2) },
                { key: 'exit_price', header: 'Exit px', align: 'right', render: r => fmtNum(r.exit_price, 2) },
                {
                  key: 'pnl', header: 'P&L', align: 'right',
                  render: r => <span className={`tnum ${pnlColor(r.pnl)}`}>{fmtNum(r.pnl, 2)}</span>,
                },
                {
                  key: 'pnl_pct', header: '%', align: 'right',
                  render: r => <span className={`tnum ${pnlColor(r.pnl_pct)}`}>{fmtPct(r.pnl_pct, 2)}</span>,
                },
                {
                  key: 'reason', header: 'Reason',
                  render: r => <StatusBadge label={r.reason} tone={reasonTone(r.reason)} dot={false} />,
                },
              ]}
              rows={tradeRows}
              emptyMessage="No trades were taken in this window."
            />
          </div>

          {monthlyRows.length > 0 && (
            <Card padding="p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-subtle mb-3">
                Monthly breakdown
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wide text-ink-subtle border-b border-edge">
                      <th className="text-left px-3 py-1.5 font-semibold">Month</th>
                      <th className="text-right px-3 py-1.5 font-semibold">P&L</th>
                      <th className="text-right px-3 py-1.5 font-semibold">Trades</th>
                      <th className="text-right px-3 py-1.5 font-semibold">Win rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthlyRows.map(m => (
                      <tr key={m.month} className="border-b border-edge/60 last:border-0">
                        <td className="px-3 py-1.5 text-ink tnum">{m.month}</td>
                        <td className={`px-3 py-1.5 text-right tnum ${pnlColor(m.pnl)}`}>{fmtINR(m.pnl)}</td>
                        <td className="px-3 py-1.5 text-right tnum text-ink-muted">
                          {m.trades === null ? '—' : fmtNum(m.trades, 0)}
                        </td>
                        <td className="px-3 py-1.5 text-right tnum text-ink-muted">
                          {m.win_rate === null ? '—' : `${fmtNum(m.win_rate, 1)}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ---------------- Past runs ---------------- */}
      <Card>
        <CardHeader
          title="Past runs"
          subtitle="Click a row to load its results"
          action={<Button variant="ghost" size="sm" onClick={loadRuns}>Refresh</Button>}
        />
        <DataTable
          dense
          pageSize={10}
          searchKeys={['id', 'strategy', 'symbols_str', 'status']}
          columns={[
            {
              key: 'id', header: 'ID', className: 'tnum text-ink-muted',
              render: r => String(r.id ?? '—').slice(0, 8),
            },
            { key: 'strategy', header: 'Strategy', className: 'font-medium' },
            { key: 'symbols_str', header: 'Symbols', className: 'tnum text-ink-muted' },
            { key: 'dates_str', header: 'Dates', className: 'tnum text-ink-muted' },
            {
              key: 'status', header: 'Status',
              render: r => <StatusBadge label={r.status ?? '—'} tone={runStatusTone(r.status)} />,
            },
            {
              key: 'net_pnl', header: 'Net P&L', align: 'right',
              render: r => r.net_pnl === null
                ? <span className="text-ink-subtle">—</span>
                : <span className={`tnum ${pnlColor(r.net_pnl)}`}>{fmtINR(r.net_pnl)}</span>,
            },
          ]}
          rows={runRows}
          onRowClick={r => { if (r.id !== null && r.id !== undefined) pollRun(r.id) }}
          emptyMessage="No backtests run yet."
        />
      </Card>
    </div>
  )
}
