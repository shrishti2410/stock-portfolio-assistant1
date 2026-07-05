/**
 * StrategyDetail — view/edit one marketplace strategy.
 * Editable strategies (custom / llm / forks) get inline editors for entry+exit
 * conditions, config, and description. Built-ins are read-only until forked.
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  PageHeader, Card, CardHeader, Button, StatusBadge, LoadingSpinner, ErrorState,
} from '../ui'
import { IconStrategy } from '../ui/icons'

const API_BASE = 'http://localhost:8000'

const SOURCE_META = {
  predefined: { label: 'Predefined', tone: 'info' },
  it_bear:    { label: 'IT-Bear',    tone: 'danger' },
  custom:     { label: 'Custom',     tone: 'success' },
  llm:        { label: 'AI',         tone: 'brand' },
}

const OPERATORS = ['gt', 'lt', 'gte', 'lte', 'eq', 'between', 'raw', 'time_window']

const INPUT_CLS = `w-full bg-surface-2 border border-edge rounded-lg px-2.5 py-1.5 text-xs text-ink
  placeholder:text-ink-subtle focus:outline-none focus:border-brand/60`

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

/** Condition value → editable text. Objects/arrays render as JSON. */
function valueToText(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  try { return JSON.stringify(v) } catch { return String(v) }
}

/** Editable text → condition value. JSON-parse when it looks like a number/array/object. */
function parseValueText(t) {
  const s = String(t ?? '').trim()
  if (s === '') return ''
  if (/^-?\d+(\.\d+)?$/.test(s) || s.startsWith('[') || s.startsWith('{')) {
    try { return JSON.parse(s) } catch { return s }
  }
  if (s === 'true') return true
  if (s === 'false') return false
  return s
}

const toRow = c => ({
  indicator: c?.indicator ?? '',
  operator: c?.operator ?? 'gt',
  value: valueToText(c?.value),
  note: c?.note ?? '',
})

const fromRow = r => ({
  indicator: r.indicator,
  operator: r.operator,
  value: parseValueText(r.value),
  note: r.note,
})

/** Flatten config object into typed field descriptors for the editor. */
function buildConfigFields(config) {
  return Object.entries(config || {}).map(([key, val]) => {
    if (val !== null && typeof val === 'object') {
      return { key, kind: 'json', text: JSON.stringify(val, null, 2), invalid: false }
    }
    const kind = typeof val === 'boolean' ? 'bool' : typeof val === 'number' ? 'number' : 'text'
    return { key, kind, value: val ?? '' }
  })
}

/* ---------------------------------------------------------------- */
/* Conditions card (entry / exit)                                    */
/* ---------------------------------------------------------------- */
function ConditionsCard({ title, rows, onChange, editable }) {
  const update = (i, field, val) =>
    onChange(rows.map((r, idx) => (idx === i ? { ...r, [field]: val } : r)))
  const remove = i => onChange(rows.filter((_, idx) => idx !== i))
  const add = () => onChange([...rows, { indicator: '', operator: 'gt', value: '', note: '' }])

  const headerCls = 'text-[10px] font-semibold uppercase tracking-wider text-ink-subtle'

  return (
    <Card>
      <CardHeader
        title={title}
        subtitle={editable ? 'Rules the engine evaluates in order' : 'Read-only — fork to edit'}
        action={editable && (
          <Button size="sm" variant="secondary" onClick={add}>+ Add condition</Button>
        )}
      />
      {rows.length === 0 ? (
        <p className="text-xs text-ink-subtle py-2">No conditions defined.</p>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-2 px-0.5">
            <span className={`col-span-3 ${headerCls}`}>Indicator</span>
            <span className={`col-span-2 ${headerCls}`}>Operator</span>
            <span className={`col-span-3 ${headerCls}`}>Value</span>
            <span className={`col-span-3 ${headerCls}`}>Note</span>
            <span className="col-span-1" />
          </div>
          {rows.map((r, i) => (
            editable ? (
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
                <input
                  className={`col-span-3 ${INPUT_CLS}`}
                  value={r.indicator}
                  placeholder="e.g. rsi_14"
                  onChange={e => update(i, 'indicator', e.target.value)}
                />
                <select
                  className={`col-span-2 ${INPUT_CLS}`}
                  value={OPERATORS.includes(r.operator) ? r.operator : 'raw'}
                  onChange={e => update(i, 'operator', e.target.value)}
                >
                  {OPERATORS.map(op => <option key={op} value={op}>{op}</option>)}
                </select>
                <input
                  className={`col-span-3 ${INPUT_CLS} tnum`}
                  value={r.value}
                  placeholder='30, [20, 80], "09:15-15:30"'
                  onChange={e => update(i, 'value', e.target.value)}
                />
                <input
                  className={`col-span-3 ${INPUT_CLS}`}
                  value={r.note}
                  placeholder="optional note"
                  onChange={e => update(i, 'note', e.target.value)}
                />
                <button
                  onClick={() => remove(i)}
                  title="Remove condition"
                  className="col-span-1 flex items-center justify-center h-7 rounded-lg text-ink-subtle
                             hover:text-red-500 hover:bg-red-500/10 transition-colors text-sm"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div key={i} className="grid grid-cols-12 gap-2 items-center py-1.5 border-b border-edge last:border-0">
                <span className="col-span-3 text-xs font-medium text-ink break-words">{r.indicator || '—'}</span>
                <span className="col-span-2"><MiniBadge>{r.operator}</MiniBadge></span>
                <span className="col-span-3 text-xs text-ink tnum break-words">{r.value || '—'}</span>
                <span className="col-span-4 text-xs text-ink-muted break-words">{r.note || ''}</span>
              </div>
            )
          ))}
        </div>
      )}
    </Card>
  )
}

/* ---------------------------------------------------------------- */
/* Config card                                                       */
/* ---------------------------------------------------------------- */
function ConfigCard({ fields, onChange, editable }) {
  const update = (i, patch) =>
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)))

  return (
    <Card className="mt-4">
      <CardHeader
        title="Config"
        subtitle={editable ? 'Strategy parameters — JSON fields are validated on save' : 'Read-only — fork to edit'}
      />
      {fields.length === 0 ? (
        <p className="text-xs text-ink-subtle py-2">No config parameters.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {fields.map((f, i) => (
            <div key={f.key} className={f.kind === 'json' ? 'sm:col-span-2' : ''}>
              <label className="block text-[11px] font-medium text-ink-muted mb-1">{f.key}</label>
              {f.kind === 'json' ? (
                editable ? (
                  <>
                    <textarea
                      rows={4}
                      value={f.text}
                      onChange={e => update(i, { text: e.target.value, invalid: false })}
                      className={`${INPUT_CLS} font-mono resize-y leading-relaxed
                        ${f.invalid ? 'border-red-500 focus:border-red-500' : ''}`}
                      spellCheck={false}
                    />
                    {f.invalid && (
                      <p className="text-[11px] text-red-500 dark:text-red-400 mt-1">
                        Invalid JSON — fix before saving
                      </p>
                    )}
                  </>
                ) : (
                  <pre className="text-xs font-mono bg-surface-2 border border-edge rounded-lg p-2.5 overflow-x-auto text-ink-muted max-h-48">
                    {f.text}
                  </pre>
                )
              ) : f.kind === 'bool' ? (
                <label className="inline-flex items-center gap-2 py-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    className="w-4 h-4"
                    checked={!!f.value}
                    disabled={!editable}
                    onChange={e => update(i, { value: e.target.checked })}
                  />
                  <span className="text-xs text-ink-muted">{f.value ? 'enabled' : 'disabled'}</span>
                </label>
              ) : (
                <input
                  type={f.kind === 'number' ? 'number' : 'text'}
                  value={f.value ?? ''}
                  disabled={!editable}
                  onChange={e => update(i, { value: e.target.value })}
                  className={`${INPUT_CLS} ${f.kind === 'number' ? 'tnum' : ''} disabled:opacity-60`}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

/* ---------------------------------------------------------------- */
/* Legs card (read-only)                                             */
/* ---------------------------------------------------------------- */
function LegsCard({ legs }) {
  const headerCls = 'text-[10px] font-semibold uppercase tracking-wider text-ink-subtle'
  return (
    <Card className="mt-4">
      <CardHeader title={`Legs (${legs.length})`} subtitle="Structural option legs — read-only" />
      <div className="space-y-1">
        <div className="grid grid-cols-4 gap-2 px-0.5">
          <span className={headerCls}>Action</span>
          <span className={headerCls}>Type</span>
          <span className={headerCls}>Strike offset</span>
          <span className={headerCls}>Qty</span>
        </div>
        {legs.map((leg, i) => (
          <div key={i} className="grid grid-cols-4 gap-2 items-center py-1.5 border-b border-edge last:border-0">
            <span>
              <StatusBadge label={String(leg.action ?? '—').toUpperCase()} className="!px-2 !py-0.5" />
            </span>
            <span className="text-xs text-ink">{leg.type ?? leg.option_type ?? '—'}</span>
            <span className="text-xs text-ink tnum">
              {leg.strike_offset ?? leg.strike ?? leg.offset ?? '—'}
            </span>
            <span className="text-xs text-ink tnum">{leg.qty ?? leg.quantity ?? leg.lots ?? '—'}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}

/* ---------------------------------------------------------------- */
/* Page                                                              */
/* ---------------------------------------------------------------- */
export default function StrategyDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()

  const [strategy, setStrategy] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Editable drafts
  const [description, setDescription] = useState('')
  const [entryRows, setEntryRows] = useState([])
  const [exitRows, setExitRows] = useState([])
  const [configFields, setConfigFields] = useState([])

  // Action states
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [forking, setForking] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const hydrate = useCallback(s => {
    setStrategy(s)
    setDescription(s?.description ?? '')
    setEntryRows((s?.entry_conditions ?? []).map(toRow))
    setExitRows((s?.exit_conditions ?? []).map(toRow))
    setConfigFields(buildConfigFields(s?.config))
    setSaveError(null)
    setSaved(false)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/strategies/${encodeURIComponent(slug)}`)
      if (!res.ok) {
        throw new Error(res.status === 404 ? 'Strategy not found' : `Failed to load strategy (HTTP ${res.status})`)
      }
      hydrate(await res.json())
    } catch (e) {
      setError(e.message || 'Failed to load strategy')
    } finally {
      setLoading(false)
    }
  }, [slug, hydrate])

  useEffect(() => { load() }, [load])

  /** Validate + assemble the PUT payload; returns null (and flags fields) on invalid JSON. */
  const buildPayload = () => {
    const config = {}
    const invalidKeys = []
    const nextFields = configFields.map(f => {
      if (f.kind === 'json') {
        try {
          config[f.key] = JSON.parse(f.text)
          return { ...f, invalid: false }
        } catch {
          invalidKeys.push(f.key)
          return { ...f, invalid: true }
        }
      }
      if (f.kind === 'number') {
        const n = Number(f.value)
        config[f.key] = f.value === '' || Number.isNaN(n) ? f.value : n
      } else if (f.kind === 'bool') {
        config[f.key] = !!f.value
      } else {
        config[f.key] = f.value
      }
      return f
    })
    setConfigFields(nextFields)
    if (invalidKeys.length) {
      setSaveError(`Invalid JSON in config: ${invalidKeys.join(', ')}`)
      return null
    }
    return {
      description,
      entry_conditions: entryRows.map(fromRow),
      exit_conditions: exitRows.map(fromRow),
      config,
    }
  }

  const save = async () => {
    setSaveError(null)
    const payload = buildPayload()
    if (!payload) return
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/strategies/${encodeURIComponent(slug)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(`Save failed (HTTP ${res.status})`)
      hydrate(await res.json())
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setSaveError(e.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const del = async () => {
    if (!window.confirm(`Delete "${strategy?.name ?? slug}"? This cannot be undone.`)) return
    setDeleting(true)
    setSaveError(null)
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/strategies/${encodeURIComponent(slug)}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error(`Delete failed (HTTP ${res.status})`)
      navigate('/marketplace')
    } catch (e) {
      setSaveError(e.message || 'Delete failed')
      setDeleting(false)
    }
  }

  const fork = async () => {
    setForking(true)
    setSaveError(null)
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/strategies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ forked_from: slug }),
      })
      if (!res.ok) throw new Error(`Fork failed (HTTP ${res.status})`)
      const data = await res.json()
      if (!data?.slug) throw new Error('Fork failed — no slug returned')
      navigate(`/marketplace/${data.slug}`)
    } catch (e) {
      setSaveError(e.message || 'Fork failed')
    } finally {
      setForking(false)
    }
  }

  const breadcrumb = [
    { label: 'Strategies', to: '/strategies' },
    { label: 'Marketplace', to: '/marketplace' },
    { label: strategy?.name ?? slug },
  ]

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        <LoadingSpinner message="Loading strategy…" />
      </div>
    )
  }

  if (error || !strategy) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        <PageHeader breadcrumb={breadcrumb} title="Strategy" icon={IconStrategy} />
        <ErrorState message={error || 'Strategy not found'} onRetry={load} />
      </div>
    )
  }

  const src = SOURCE_META[strategy.source] ?? { label: strategy.source || 'Unknown', tone: 'neutral' }
  const engineReady = strategy.tags?.includes('backtestable')
  const editable = !!strategy.is_editable

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        breadcrumb={breadcrumb}
        title={strategy.name}
        subtitle={editable ? 'Editable strategy — changes save to the marketplace' : 'Built-in strategy — fork to make it yours'}
        icon={IconStrategy}
        actions={
          <>
            {engineReady && (
              <Button variant="outline" onClick={() => navigate(`/backtest?strategy=${encodeURIComponent(slug)}`)}>
                Backtest this
              </Button>
            )}
            <Button variant="secondary" onClick={fork} loading={forking}>Fork to edit</Button>
            {editable && (
              <>
                <Button onClick={save} loading={saving} variant={saved ? 'success' : 'primary'}>
                  {saved ? 'Saved ✓' : 'Save changes'}
                </Button>
                <Button variant="danger" onClick={del} loading={deleting}>Delete</Button>
              </>
            )}
          </>
        }
      />

      {/* Badges row */}
      <div className="flex items-center gap-2 flex-wrap mb-5 -mt-2">
        <StatusBadge label={src.label} tone={src.tone} />
        {strategy.category && <MiniBadge>{strategy.category}</MiniBadge>}
        <MiniBadge>{marketBadge(strategy.market)}</MiniBadge>
        {strategy.risk && <MiniBadge>{strategy.risk} risk</MiniBadge>}
        {strategy.direction && <MiniBadge>{strategy.direction}</MiniBadge>}
        {engineReady && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-600 dark:text-emerald-300">
            Engine-ready
          </span>
        )}
        {strategy.forked_from && <MiniBadge>forked from {strategy.forked_from}</MiniBadge>}
      </div>

      {saveError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 mb-4">
          <p className="text-xs text-red-500 dark:text-red-400">{saveError}</p>
        </div>
      )}

      {/* Entry / Exit conditions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ConditionsCard title="Entry Conditions" rows={entryRows} onChange={setEntryRows} editable={editable} />
        <ConditionsCard title="Exit Conditions" rows={exitRows} onChange={setExitRows} editable={editable} />
      </div>

      {/* Config */}
      <ConfigCard fields={configFields} onChange={setConfigFields} editable={editable} />

      {/* Legs */}
      {strategy.legs?.length > 0 && <LegsCard legs={strategy.legs} />}

      {/* Description */}
      <Card className="mt-4">
        <CardHeader title="Description" subtitle={editable ? undefined : 'Read-only — fork to edit'} />
        {editable ? (
          <textarea
            rows={4}
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="What this strategy does, when it works, when it doesn't…"
            className={`${INPUT_CLS} !text-sm resize-y leading-relaxed`}
          />
        ) : (
          <p className="text-sm text-ink-muted leading-relaxed whitespace-pre-wrap">
            {strategy.description || 'No description.'}
          </p>
        )}
      </Card>
    </div>
  )
}
