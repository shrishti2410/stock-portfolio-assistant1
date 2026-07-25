/**
 * LLMSettings — cost observability + hard budget control for all LLM usage.
 * Lets the user paste a provider key, set daily/monthly caps, pick model,
 * and watch live spend / per-feature breakdown / recent calls.
 */
import { useState, useEffect, useCallback } from 'react'
import { PageHeader, Card, CardHeader, Button, MetricCard, StatusBadge, DataTable, LoadingSpinner } from '../ui'
import { IconSettings, IconRefresh } from '../ui/icons'

const API = ''

const MODELS = {
  anthropic: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-8'],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1'],
  groq: ['llama-3.3-70b-versatile'],
  gemini: ['gemini-2.0-flash', 'gemini-1.5-flash'],
}

const PROVIDER_LABEL = {
  anthropic: 'Anthropic (Claude)', openai: 'OpenAI', groq: 'Groq (free)', gemini: 'Google Gemini (free)',
}

function ProgressBar({ pct, tone }) {
  const color = pct >= 90 ? 'bg-red-500' : pct >= 60 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="h-2 bg-surface-2 rounded-full overflow-hidden mt-2">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  )
}

export default function LLMSettings() {
  const [usage, setUsage] = useState(null)
  const [config, setConfig] = useState(null)
  const [providers, setProviders] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')
  const [testMsg, setTestMsg] = useState(null)
  const [keyDraft, setKeyDraft] = useState({ provider: 'anthropic', api_key: '' })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [u, c, p] = await Promise.all([
        fetch(`${API}/api/llm/usage`).then(r => r.json()),
        fetch(`${API}/api/llm/config`).then(r => r.json()),
        fetch(`${API}/api/llm/providers`).then(r => r.json()),
      ])
      setUsage(u); setConfig(c); setProviders(p)
    } catch (e) { /* backend down */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  function setField(k, v) { setConfig(c => ({ ...c, [k]: v })) }

  async function saveConfig() {
    setSaving(true); setSavedMsg('')
    try {
      const res = await fetch(`${API}/api/llm/config`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: !!config.enabled,
          provider: config.provider,
          default_model: config.default_model,
          daily_limit_usd: Number(config.daily_limit_usd),
          monthly_limit_usd: Number(config.monthly_limit_usd),
          per_call_max_tokens: Number(config.per_call_max_tokens),
          calls_per_min: Number(config.calls_per_min),
          cache_enabled: !!config.cache_enabled,
        }),
      })
      if (res.ok) { setSavedMsg('Saved'); setTimeout(() => setSavedMsg(''), 2500); load() }
    } finally { setSaving(false) }
  }

  async function saveKey() {
    if (!keyDraft.api_key.trim()) return
    setSaving(true)
    try {
      await fetch(`${API}/api/llm/provider-key`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(keyDraft),
      })
      setKeyDraft({ ...keyDraft, api_key: '' })
      await load()
    } finally { setSaving(false) }
  }

  async function runTest() {
    setTestMsg({ pending: true })
    try {
      const res = await fetch(`${API}/api/llm/test`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      const data = await res.json()
      if (res.ok) setTestMsg({ ok: true, text: data.text, cost: data.cost_usd, model: data.model, inT: data.input_tokens, outT: data.output_tokens })
      else setTestMsg({ ok: false, message: data.detail?.message || data.detail || 'Test failed' })
    } catch (e) { setTestMsg({ ok: false, message: e.message }) }
    load()
  }

  if (loading || !config) return <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6"><LoadingSpinner message="Loading LLM settings…" /></div>

  const modelOptions = MODELS[config.provider] || []

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="LLM Cost Control"
        subtitle="Every AI call routes through one gateway with hard budget caps + full observability"
        icon={IconSettings}
        breadcrumb={[{ label: 'Settings', to: '/settings' }, { label: 'LLM' }]}
        actions={<Button variant="secondary" size="sm" icon={IconRefresh} onClick={load}>Refresh</Button>}
      />

      {/* Spend overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Card padding="p-4">
          <p className="text-[10px] uppercase tracking-wide text-ink-subtle mb-1">Spend Today</p>
          <p className="text-2xl font-bold tnum text-ink" style={{ fontFamily: 'var(--font-mono)' }}>${usage.spend_today_usd.toFixed(4)}</p>
          <p className="text-[10px] text-ink-muted mt-0.5">of ${usage.daily_limit_usd.toFixed(2)} cap</p>
          <ProgressBar pct={usage.daily_pct} />
        </Card>
        <Card padding="p-4">
          <p className="text-[10px] uppercase tracking-wide text-ink-subtle mb-1">Spend This Month</p>
          <p className="text-2xl font-bold tnum text-ink" style={{ fontFamily: 'var(--font-mono)' }}>${usage.spend_month_usd.toFixed(4)}</p>
          <p className="text-[10px] text-ink-muted mt-0.5">of ${usage.monthly_limit_usd.toFixed(2)} cap</p>
          <ProgressBar pct={usage.monthly_pct} />
        </Card>
        <MetricCard label="Total Calls" value={usage.totals?.calls ?? 0} sub={`${usage.totals?.cached_calls ?? 0} served from cache`} />
        <MetricCard label="Budget Blocks" value={usage.totals?.blocked ?? 0} variant={usage.totals?.blocked > 0 ? 'warning' : 'default'} sub="calls refused over-budget" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Provider + keys */}
        <Card>
          <CardHeader title="Provider & API Key" subtitle="Paste your Claude or OpenAI key — saved to .env, never exposed" />
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              {Object.keys(PROVIDER_LABEL).map(p => (
                <div key={p} className="flex items-center justify-between px-3 py-2 rounded-lg border border-edge bg-surface-2">
                  <span className="text-xs text-ink">{PROVIDER_LABEL[p]}</span>
                  <StatusBadge label={providers[p] ? 'Key set' : 'No key'} tone={providers[p] ? 'success' : 'neutral'} />
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <select
                value={keyDraft.provider}
                onChange={e => setKeyDraft({ ...keyDraft, provider: e.target.value })}
                className="px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink focus:outline-none focus:border-brand/50"
              >
                {Object.keys(PROVIDER_LABEL).map(p => <option key={p} value={p}>{PROVIDER_LABEL[p]}</option>)}
              </select>
              <input
                type="password"
                value={keyDraft.api_key}
                onChange={e => setKeyDraft({ ...keyDraft, api_key: e.target.value })}
                placeholder="Paste API key…"
                className="flex-1 px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:border-brand/50"
              />
              <Button onClick={saveKey} loading={saving} disabled={!keyDraft.api_key.trim()}>Save</Button>
            </div>
            <div className="pt-2">
              <Button variant="outline" size="sm" onClick={runTest}>Send test call (~$0.0001)</Button>
              {testMsg?.pending && <span className="text-xs text-ink-muted ml-2">Testing…</span>}
              {testMsg && !testMsg.pending && (
                <p className={`text-xs mt-2 ${testMsg.ok ? 'text-emerald-500' : 'text-red-500'}`}>
                  {testMsg.ok
                    ? `✓ ${testMsg.model}: "${testMsg.text?.slice(0, 40)}" — ${testMsg.inT}+${testMsg.outT} tok, $${testMsg.cost?.toFixed(5)}`
                    : `✗ ${testMsg.message}`}
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Budget + limits */}
        <Card>
          <CardHeader title="Budget & Limits" subtitle="Hard caps — calls are refused once exceeded" action={
            <label className="flex items-center gap-2 text-xs text-ink-muted cursor-pointer">
              <input type="checkbox" checked={!!config.enabled} onChange={e => setField('enabled', e.target.checked)} />
              LLM enabled
            </label>
          } />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Daily cap (USD)" value={config.daily_limit_usd} onChange={v => setField('daily_limit_usd', v)} step="0.5" />
            <Field label="Monthly cap (USD)" value={config.monthly_limit_usd} onChange={v => setField('monthly_limit_usd', v)} step="1" />
            <Field label="Max tokens / call" value={config.per_call_max_tokens} onChange={v => setField('per_call_max_tokens', v)} step="100" />
            <Field label="Calls / minute" value={config.calls_per_min} onChange={v => setField('calls_per_min', v)} step="1" />
            <div>
              <label className="block text-[11px] font-medium text-ink-muted mb-1">Provider</label>
              <select value={config.provider} onChange={e => { setField('provider', e.target.value); setField('default_model', (MODELS[e.target.value]||[])[0]) }}
                className="w-full px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink focus:outline-none focus:border-brand/50">
                {Object.keys(PROVIDER_LABEL).map(p => <option key={p} value={p}>{PROVIDER_LABEL[p]}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-ink-muted mb-1">Default model</label>
              <select value={config.default_model} onChange={e => setField('default_model', e.target.value)}
                className="w-full px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink focus:outline-none focus:border-brand/50">
                {modelOptions.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-edge">
            <label className="flex items-center gap-2 text-xs text-ink-muted cursor-pointer">
              <input type="checkbox" checked={!!config.cache_enabled} onChange={e => setField('cache_enabled', e.target.checked)} />
              Cache identical prompts (avoid double-charge)
            </label>
            <div className="flex items-center gap-2">
              {savedMsg && <span className="text-xs text-emerald-500">{savedMsg}</span>}
              <Button onClick={saveConfig} loading={saving}>Save limits</Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Per-feature breakdown */}
      <div className="mt-5">
        <Card padding="p-0">
          <div className="px-5 pt-4 pb-2"><h3 className="text-sm font-semibold text-ink">Spend by feature (this month)</h3></div>
          <DataTable
            searchable={false}
            pageSize={6}
            columns={[
              { key: 'feature', header: 'Feature' },
              { key: 'calls', header: 'Calls', align: 'right' },
              { key: 'in_tok', header: 'Input tok', align: 'right', render: r => (r.in_tok ?? 0).toLocaleString() },
              { key: 'out_tok', header: 'Output tok', align: 'right', render: r => (r.out_tok ?? 0).toLocaleString() },
              { key: 'cost', header: 'Cost', align: 'right', render: r => `$${(r.cost ?? 0).toFixed(5)}` },
            ]}
            rows={usage.by_feature || []}
            emptyMessage="No LLM calls yet this month."
          />
        </Card>
      </div>

      {/* Recent calls */}
      <div className="mt-5">
        <Card padding="p-0">
          <div className="px-5 pt-4 pb-2"><h3 className="text-sm font-semibold text-ink">Recent calls</h3></div>
          <DataTable
            searchable={false}
            pageSize={10}
            columns={[
              { key: 'created_at', header: 'Time', render: r => (r.created_at || '').slice(5, 16) },
              { key: 'feature', header: 'Feature' },
              { key: 'model', header: 'Model', render: r => (r.model || '').replace('claude-', '').replace('-20251001', '') },
              { key: 'input_tokens', header: 'In', align: 'right' },
              { key: 'output_tokens', header: 'Out', align: 'right' },
              { key: 'cost_usd', header: 'Cost', align: 'right', render: r => r.cached ? 'cached' : `$${(r.cost_usd ?? 0).toFixed(5)}` },
              { key: 'status', header: 'Status', align: 'center', render: r => <StatusBadge label={r.status} tone={r.status === 'ok' ? 'success' : r.status === 'budget_blocked' ? 'warning' : 'danger'} dot={false} /> },
            ]}
            rows={usage.recent || []}
            emptyMessage="No calls logged yet."
          />
        </Card>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, step = '1' }) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-ink-muted mb-1">{label}</label>
      <input
        type="number" step={step} value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-surface-2 border border-edge rounded-lg text-sm text-ink tnum focus:outline-none focus:border-brand/50"
      />
    </div>
  )
}
