/**
 * Marketplace — unified strategy marketplace.
 * Browse every strategy (predefined, IT-Bear, custom, AI-authored), filter by
 * source/category, search, and click through to fork/edit in StrategyDetail.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PageHeader, Card, Button, StatusBadge, SegmentedControl,
  LoadingSpinner, EmptyState, ErrorState,
} from '../ui'
import { IconStrategy, IconSearch } from '../ui/icons'

const API_BASE = ''

const SOURCE_META = {
  predefined: { label: 'Predefined', tone: 'info' },
  it_bear:    { label: 'IT-Bear',    tone: 'danger' },
  custom:     { label: 'Custom',     tone: 'success' },
  llm:        { label: 'AI',         tone: 'brand' },
}

const SOURCE_FILTERS = [
  { value: 'all',        label: 'All' },
  { value: 'predefined', label: 'Predefined' },
  { value: 'it_bear',    label: 'IT-Bear' },
  { value: 'custom',     label: 'Custom' },
  { value: 'llm',        label: 'AI' },
]

function marketBadge(market) {
  const m = String(market || '').toUpperCase()
  if (m === 'IN') return '🇮🇳 IN'
  if (m === 'US') return '🇺🇸 US'
  if (m === 'BOTH') return '🇮🇳🇺🇸 Both'
  return market || '—'
}

function MiniBadge({ children }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-2 border border-edge text-ink-muted">
      {children}
    </span>
  )
}

function EngineReadyChip() {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-600 dark:text-emerald-300">
      Engine-ready
    </span>
  )
}

function StrategyCard({ s, onOpen }) {
  const src = SOURCE_META[s.source] ?? { label: s.source || 'Unknown', tone: 'neutral' }
  const entryN = s.entry_conditions?.length ?? 0
  const exitN = s.exit_conditions?.length ?? 0
  const engineReady = s.tags?.includes('backtestable')

  return (
    <Card hover padding="p-4" className="cursor-pointer flex flex-col" onClick={onOpen}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-ink leading-snug">{s.name}</p>
        <StatusBadge label={src.label} tone={src.tone} className="shrink-0" />
      </div>

      <div className="flex items-center gap-1.5 flex-wrap mt-2">
        {s.category && <MiniBadge>{s.category}</MiniBadge>}
        <MiniBadge>{marketBadge(s.market)}</MiniBadge>
        {s.risk && <MiniBadge>{s.risk} risk</MiniBadge>}
        {s.direction && <MiniBadge>{s.direction}</MiniBadge>}
      </div>

      <p className="text-xs text-ink-muted mt-2 leading-relaxed line-clamp-2 flex-1">
        {s.description || 'No description.'}
      </p>

      <div className="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-edge">
        <p className="text-[11px] text-ink-subtle tnum">
          {entryN} entry {entryN === 1 ? 'rule' : 'rules'} · {exitN} exit {exitN === 1 ? 'rule' : 'rules'}
        </p>
        {engineReady && <EngineReadyChip />}
      </div>
    </Card>
  )
}

export default function Marketplace() {
  const navigate = useNavigate()
  const [strategies, setStrategies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [source, setSource] = useState('all')
  const [category, setCategory] = useState('all')
  const [q, setQ] = useState('')
  const [seeding, setSeeding] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/strategies`)
      if (!res.ok) throw new Error(`Failed to load strategies (HTTP ${res.status})`)
      const data = await res.json()
      setStrategies(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(e.message || 'Failed to load strategies')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const seed = async () => {
    setSeeding(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/seed`, { method: 'POST' })
      if (!res.ok) throw new Error(`Seeding failed (HTTP ${res.status})`)
      await load()
    } catch (e) {
      setError(e.message || 'Seeding failed')
    } finally {
      setSeeding(false)
    }
  }

  const categories = useMemo(
    () => ['all', ...new Set(strategies.map(s => s.category).filter(Boolean))],
    [strategies],
  )

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return strategies.filter(s => {
      if (source !== 'all' && s.source !== source) return false
      if (category !== 'all' && s.category !== category) return false
      if (needle) {
        const hay = `${s.name || ''} ${s.description || ''}`.toLowerCase()
        if (!hay.includes(needle)) return false
      }
      return true
    })
  }, [strategies, source, category, q])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Strategy Marketplace"
        subtitle="Browse, fork, and edit every strategy — predefined, IT-Bear, custom, and AI-authored"
        icon={IconStrategy}
        actions={
          <>
            <Button variant="secondary" onClick={seed} loading={seeding}>Re-seed built-ins</Button>
            <Button onClick={() => navigate('/marketplace/chat')}>New with AI</Button>
          </>
        }
      />

      {loading ? (
        <LoadingSpinner message="Loading strategies…" />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : strategies.length === 0 ? (
        <EmptyState
          icon={IconStrategy}
          title="Marketplace is empty"
          description="Seed the built-in strategy library (F&O playbook, IT-Bear thesis, and more) to get started."
          action={<Button onClick={seed} loading={seeding}>Seed built-in strategies</Button>}
        />
      ) : (
        <>
          {/* Filters */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-3">
            <SegmentedControl options={SOURCE_FILTERS} value={source} onChange={setSource} />
            <div className="relative flex-1 sm:max-w-xs">
              <IconSearch className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-subtle pointer-events-none" />
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search strategies…"
                className="w-full bg-surface border border-edge rounded-lg pl-8 pr-3 py-1.5 text-sm text-ink
                           placeholder:text-ink-subtle focus:outline-none focus:border-brand/60"
              />
            </div>
            <p className="text-xs text-ink-subtle tnum sm:ml-auto">
              {filtered.length} of {strategies.length} strategies
            </p>
          </div>

          {/* Category pills */}
          {categories.length > 1 && (
            <div className="flex items-center gap-1.5 flex-wrap mb-5">
              {categories.map(c => (
                <button
                  key={c}
                  onClick={() => setCategory(c)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors
                    ${category === c
                      ? 'bg-brand-soft border-brand/40 text-brand'
                      : 'bg-surface border-edge text-ink-muted hover:text-ink hover:border-edge-strong'}`}
                >
                  {c === 'all' ? 'All categories' : c}
                </button>
              ))}
            </div>
          )}

          {filtered.length === 0 ? (
            <EmptyState
              icon={IconSearch}
              title="No strategies match"
              description="Try a different source, category, or search term."
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map(s => (
                <StrategyCard key={s.slug} s={s} onOpen={() => navigate(`/marketplace/${s.slug}`)} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
