/**
 * BrokerSettings — per-user Zerodha connection ("/settings/broker").
 *
 * Credentials are stored encrypted server-side, scoped to the logged-in
 * user only. Backend contract (backend/routers/broker_api.py):
 *   GET    /api/broker/status  -> {configured, fields:[{key,encrypted,updated_at,preview}], source}
 *   PUT    /api/broker/zerodha -> body {user_id_field?, password?, totp_secret?} (only filled fields sent)
 *   DELETE /api/broker/zerodha
 *   POST   /api/broker/test   -> {ok, holdings_count} | {ok:false, error}
 *
 * Note: the PUT body keys (user_id_field / password / totp_secret) differ
 * from the *stored* field keys returned by GET status
 * (zerodha_user_id / zerodha_password / zerodha_totp_secret) — this file
 * keeps the two mappings explicit below.
 */
import { useState, useEffect, useCallback } from 'react'
import { PageHeader, Card, CardHeader, Button, StatusBadge, LoadingSpinner, ErrorState } from '../ui'
import { IconLink, IconRefresh, IconEye, IconEyeOff } from '../ui/icons'
import { useAuth } from '../shell/useAuth'

const API_BASE = ''

const FIELD_LABELS = {
  zerodha_user_id: 'Zerodha User ID',
  zerodha_password: 'Password',
  zerodha_totp_secret: 'TOTP Secret',
}

function fmtDateTime(iso) {
  if (!iso) return null
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function PasswordField({ label, value, onChange, help, placeholder }) {
  const [show, setShow] = useState(false)
  return (
    <div>
      <label className="block text-[11px] font-medium text-ink-muted mb-1">{label}</label>
      <div className="relative">
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className="w-full px-3 py-2 pr-9 bg-surface-2 border border-edge rounded-lg text-sm text-ink
                     placeholder:text-ink-subtle focus:outline-none focus:border-brand/50 transition-colors"
        />
        <button
          type="button"
          onClick={() => setShow(s => !s)}
          tabIndex={-1}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-ink-subtle hover:text-ink transition-colors"
          aria-label={show ? `Hide ${label}` : `Show ${label}`}
        >
          {show ? <IconEyeOff className="w-4 h-4" /> : <IconEye className="w-4 h-4" />}
        </button>
      </div>
      {help && <p className="text-[10px] text-ink-subtle mt-1">{help}</p>}
    </div>
  )
}

function FieldRow({ field }) {
  const label = FIELD_LABELS[field.key] || field.key
  const updated = fmtDateTime(field.updated_at)
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-edge last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm text-ink truncate">{label}</span>
        {field.encrypted && (
          <span className="shrink-0 text-[9px] px-1.5 py-0.5 rounded-full bg-surface-2 border border-edge text-ink-subtle">
            encrypted
          </span>
        )}
      </div>
      <div className="text-right shrink-0">
        <p className="text-xs font-mono text-ink-muted tnum">{field.preview || '—'}</p>
        {updated && <p className="text-[10px] text-ink-subtle mt-0.5">Updated {updated}</p>}
      </div>
    </div>
  )
}

const EMPTY_DRAFT = { zerodha_user_id: '', zerodha_password: '', zerodha_totp_secret: '' }

export default function BrokerSettings() {
  const { authFetch } = useAuth()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [draft, setDraft] = useState(EMPTY_DRAFT)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [disconnecting, setDisconnecting] = useState(false)

  const loadStatus = useCallback(async () => {
    setLoading(true)
    try {
      const res = await authFetch(`${API_BASE}/api/broker/status`)
      setStatus(res.ok ? await res.json() : null)
    } catch {
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }, [authFetch])

  useEffect(() => { loadStatus() }, [loadStatus])

  function setField(k, v) { setDraft(d => ({ ...d, [k]: v })) }

  const hasDraft = Boolean(draft.zerodha_user_id.trim() || draft.zerodha_password || draft.zerodha_totp_secret.trim())

  async function save() {
    // NOTE: backend PUT body keys are user_id_field / password / totp_secret —
    // distinct from the zerodha_* keys the status endpoint reports back.
    const body = {}
    if (draft.zerodha_user_id.trim()) body.user_id_field = draft.zerodha_user_id.trim()
    if (draft.zerodha_password) body.password = draft.zerodha_password
    if (draft.zerodha_totp_secret.trim()) body.totp_secret = draft.zerodha_totp_secret.trim()
    if (Object.keys(body).length === 0) return

    setSaving(true); setSaveMsg(null)
    try {
      const res = await authFetch(`${API_BASE}/api/broker/zerodha`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => null)
      if (res.ok) {
        setSaveMsg({ ok: true, text: 'Saved' })
        setDraft(EMPTY_DRAFT)
        await loadStatus()
      } else {
        setSaveMsg({ ok: false, text: data?.detail?.message || data?.detail || 'Failed to save credentials' })
      }
    } catch {
      setSaveMsg({ ok: false, text: 'Network error — please try again' })
    } finally {
      setSaving(false)
      setTimeout(() => setSaveMsg(null), 4000)
    }
  }

  async function runTest() {
    setTesting(true); setTestResult(null)
    try {
      const res = await authFetch(`${API_BASE}/api/broker/test`, { method: 'POST' })
      const data = await res.json().catch(() => null)
      if (res.ok && data?.ok) {
        setTestResult({ ok: true, text: `Connected — ${data.holdings_count ?? 0} holdings` })
      } else {
        setTestResult({ ok: false, text: data?.error || data?.detail?.message || data?.detail || 'Connection test failed' })
      }
    } catch {
      setTestResult({ ok: false, text: 'Network error — please try again' })
    } finally {
      setTesting(false)
    }
  }

  async function disconnect() {
    if (!window.confirm('Disconnect your Zerodha account? Saved credentials will be removed.')) return
    setDisconnecting(true)
    try {
      await authFetch(`${API_BASE}/api/broker/zerodha`, { method: 'DELETE' })
      setTestResult(null)
      await loadStatus()
    } finally {
      setDisconnecting(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Broker Connection"
        subtitle="Your personal Zerodha link — credentials are encrypted and visible only to your login"
        icon={IconLink}
        breadcrumb={[{ label: 'Settings', to: '/settings' }, { label: 'Broker' }]}
        actions={<Button variant="secondary" size="sm" icon={IconRefresh} onClick={loadStatus}>Refresh</Button>}
      />

      {loading ? (
        <LoadingSpinner message="Loading broker status…" />
      ) : (
        <div className="space-y-5">
          <Card>
            <CardHeader title="Connection status" subtitle="What's saved for your account right now" />
            <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
              <StatusBadge
                label={status?.configured ? 'Connected' : 'Not connected'}
                tone={status?.configured ? 'success' : 'neutral'}
              />
              {status?.source === 'env-admin' && (
                <span className="text-xs text-ink-muted">Using server-level credentials (admin fallback)</span>
              )}
            </div>
            {status?.fields?.length > 0 ? (
              <div className="mt-3">
                {status.fields.map(f => <FieldRow key={f.key} field={f} />)}
              </div>
            ) : (
              <p className="text-xs text-ink-muted mt-3">No credentials saved yet — add them below to connect your account.</p>
            )}
          </Card>

          <Card>
            <CardHeader title="Connect / update credentials" subtitle="Only the fields you fill in will be updated" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <PasswordField
                label="Zerodha User ID"
                value={draft.zerodha_user_id}
                onChange={v => setField('zerodha_user_id', v)}
                placeholder="e.g. AB1234"
              />
              <PasswordField
                label="Zerodha Password"
                value={draft.zerodha_password}
                onChange={v => setField('zerodha_password', v)}
                placeholder="Your Kite login password"
              />
              <PasswordField
                label="TOTP Secret"
                value={draft.zerodha_totp_secret}
                onChange={v => setField('zerodha_totp_secret', v)}
                placeholder="Base32 secret"
                help="The Base32 secret from Zerodha 2FA setup, not the 6-digit code."
              />
            </div>

            <div className="flex items-center flex-wrap gap-2 mt-5 pt-4 border-t border-edge">
              <Button onClick={save} loading={saving} disabled={!hasDraft}>Save</Button>
              <Button variant="secondary" onClick={runTest} loading={testing}>Test connection</Button>
              <Button variant="danger" onClick={disconnect} loading={disconnecting} disabled={!status?.configured}>
                Disconnect
              </Button>
              {saveMsg && (
                <span className={`text-xs ${saveMsg.ok ? 'text-emerald-500' : 'text-red-500'}`}>{saveMsg.text}</span>
              )}
            </div>

            {testResult?.ok && (
              <div className="mt-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2.5 text-xs font-medium text-emerald-600 dark:text-emerald-300">
                ✓ {testResult.text}
              </div>
            )}
            {testResult && !testResult.ok && (
              <ErrorState message={testResult.text} onRetry={runTest} className="mt-3" />
            )}
          </Card>

          <Card className="bg-surface-2/50">
            <p className="text-xs text-ink-muted leading-relaxed">
              Paper trading and dashboards work fine without connecting a broker. Connect your Zerodha
              account only when you want to see your <span className="text-ink">live portfolio</span> and
              place real trades.
            </p>
          </Card>
        </div>
      )}
    </div>
  )
}
