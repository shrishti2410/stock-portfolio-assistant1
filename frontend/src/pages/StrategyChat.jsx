/**
 * StrategyChat — author a strategy by chatting with the LLM (route /marketplace/chat).
 * Left: conversation thread. Right: live strategy draft that refines every turn,
 * with one-click "Save to Marketplace". Per-reply token/cost usage stays visible
 * so spend is never a surprise.
 */
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  PageHeader, Card, Button, StatusBadge, EmptyState, ErrorState,
} from '../ui'
import { IconStrategy } from '../ui/icons'

const API_BASE = ''

const newSessionId = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  ).replace(/[^a-zA-Z0-9]/g, '')

const RISK_TONE = { low: 'success', medium: 'warning', high: 'danger' }

function UsageLine({ usage }) {
  if (!usage) return null
  const detail = usage.cached
    ? 'cached'
    : `${(usage.input_tokens || 0) + (usage.output_tokens || 0)} tokens · $${Number(usage.cost_usd || 0).toFixed(4)}`
  return (
    <p className="text-[10px] text-ink-subtle mt-1 tnum">
      {usage.model} · {detail}
    </p>
  )
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] ${isUser ? 'text-right' : 'text-left'}`}>
        <div
          className={`inline-block px-3 py-2 rounded-xl text-sm text-ink text-left whitespace-pre-wrap leading-relaxed
            ${isUser
              ? 'bg-brand-soft border border-brand/25 rounded-br-sm'
              : 'bg-surface-2 border border-edge rounded-bl-sm'}`}
        >
          {msg.content}
        </div>
        {!isUser && <UsageLine usage={msg.usage} />}
      </div>
    </div>
  )
}

function TypingRow() {
  return (
    <div className="flex justify-start">
      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-xl rounded-bl-sm bg-surface-2 border border-edge">
        <span className="w-3.5 h-3.5 border-2 border-edge-strong border-t-brand rounded-full animate-spin" />
        <span className="text-xs text-ink-muted">Drafting…</span>
      </div>
    </div>
  )
}

function ConditionRow({ c }) {
  const value = Array.isArray(c.value) ? c.value.join(' – ') : String(c.value ?? '')
  return (
    <div className="px-2.5 py-2 rounded-lg bg-surface-2 border border-edge">
      <p className="text-xs text-ink">
        <span className="font-semibold">{c.indicator || 'condition'}</span>{' '}
        <span className="font-mono text-[11px] text-ink-muted">{c.operator} {value}</span>
      </p>
      {c.note && <p className="text-[11px] text-ink-muted mt-0.5">{c.note}</p>}
    </div>
  )
}

function ConditionList({ label, items }) {
  if (!items?.length) return null
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-subtle mb-1.5">{label}</p>
      <div className="space-y-1.5">
        {items.map((c, i) => <ConditionRow key={i} c={c} />)}
      </div>
    </div>
  )
}

function DraftPanel({ draft, onSave, saving, onReset }) {
  if (!draft) {
    return (
      <EmptyState
        icon={IconStrategy}
        title="Describe your strategy to start"
        description="Tell the assistant what you want to trade — market, direction, indicators, risk. A structured draft will appear here and refine with every message."
      />
    )
  }
  const hasConfig = draft.config && Object.keys(draft.config).length > 0
  return (
    <div className="space-y-4">
      <div>
        <p className="text-base font-bold text-ink leading-snug">{draft.name || 'Untitled strategy'}</p>
        <div className="flex items-center gap-1.5 flex-wrap mt-2">
          {draft.category && <StatusBadge label={draft.category} tone="info" />}
          {draft.market && <StatusBadge label={draft.market} tone="brand" />}
          {draft.direction && <StatusBadge label={draft.direction} />}
          {draft.risk && <StatusBadge label={`${draft.risk} risk`} tone={RISK_TONE[draft.risk] || 'neutral'} />}
        </div>
      </div>

      {draft.description && (
        <p className="text-xs text-ink-muted leading-relaxed">{draft.description}</p>
      )}

      <ConditionList label="Entry conditions" items={draft.entry_conditions} />
      <ConditionList label="Exit conditions" items={draft.exit_conditions} />

      {hasConfig && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-subtle mb-1.5">Config</p>
          <pre className="text-xs font-mono bg-surface-2 border border-edge rounded-lg p-2.5 overflow-x-auto text-ink-muted">
            {JSON.stringify(draft.config, null, 2)}
          </pre>
        </div>
      )}

      <div className="flex items-center gap-2 pt-3 border-t border-edge">
        <Button onClick={onSave} loading={saving} className="flex-1">Save to Marketplace</Button>
        <Button variant="secondary" onClick={onReset}>Start over</Button>
      </div>
    </div>
  )
}

export default function StrategyChat() {
  const navigate = useNavigate()
  const [sessionId, setSessionId] = useState(newSessionId)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState(null)
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null) // {status, message}
  const threadRef = useRef(null)

  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, pending])

  const sessionCost = messages.reduce(
    (sum, m) => sum + (m.usage?.cost_usd || 0), 0,
  )

  async function send() {
    const message = input.trim()
    if (!message || pending) return
    setInput('')
    setError(null)
    setMessages(prev => [...prev, { role: 'user', content: message }])
    setPending(true)
    try {
      const res = await fetch(`${API_BASE}/api/marketplace/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) {
        const detail = data?.detail
        const status = typeof detail === 'object' ? detail?.status : null
        const msg = (typeof detail === 'object' ? detail?.message : detail)
          || `Request failed (HTTP ${res.status})`
        setError({ status: status || 'error', message: msg })
        return
      }
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: data.reply || '(no reply)', usage: data.usage },
      ])
      if (data.draft) setDraft(data.draft)
    } catch (e) {
      setError({ status: 'error', message: e.message || 'Backend unreachable' })
    } finally {
      setPending(false)
    }
  }

  async function saveToMarketplace() {
    if (!draft || saving) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE}/api/marketplace/chat/${encodeURIComponent(sessionId)}/save`,
        { method: 'POST' },
      )
      const data = await res.json().catch(() => null)
      if (!res.ok) {
        const detail = data?.detail
        const msg = (typeof detail === 'object' ? detail?.message : detail) || 'Save failed'
        setError({ status: 'error', message: msg })
        return
      }
      navigate(`/marketplace/${data.slug}`)
    } catch (e) {
      setError({ status: 'error', message: e.message || 'Save failed' })
    } finally {
      setSaving(false)
    }
  }

  function startOver() {
    setSessionId(newSessionId())
    setMessages([])
    setDraft(null)
    setError(null)
    setInput('')
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="New Strategy with AI"
        subtitle="Describe what you want to trade — the assistant drafts a structured strategy you can refine and save"
        icon={IconStrategy}
        breadcrumb={[{ label: 'Marketplace', to: '/marketplace' }, { label: 'New with AI' }]}
        actions={
          <p className="text-xs text-ink-muted tnum">
            Session cost: <span className="font-semibold text-ink">${sessionCost.toFixed(4)}</span>
          </p>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-start">
        {/* ── Chat panel ── */}
        <Card padding="p-0" className="lg:col-span-3 flex flex-col h-[70vh]">
          <div ref={threadRef} className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && !pending && (
              <EmptyState
                title="Start the conversation"
                description={'e.g. "RSI oversold mean-reversion buy on NIFTY stocks, 5-minute timeframe, tight stops."'}
              />
            )}
            {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
            {pending && <TypingRow />}
          </div>

          {/* Error banners */}
          {error && (
            <div className="px-4 pb-2">
              {error.status === 'budget_blocked' ? (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3">
                  <p className="text-xs text-amber-600 dark:text-amber-300 leading-relaxed">
                    {error.message}{' '}
                    <Link to="/settings/llm" className="font-semibold underline underline-offset-2">
                      Open LLM settings
                    </Link>
                  </p>
                </div>
              ) : (
                <ErrorState message={error.message} className="my-0 p-3" />
              )}
            </div>
          )}

          <div className="border-t border-edge p-3 flex items-end gap-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              placeholder="Describe or refine your strategy… (Enter to send, Shift+Enter for a new line)"
              className="flex-1 bg-surface-2 border border-edge rounded-lg px-3 py-2 text-sm text-ink
                         placeholder:text-ink-subtle resize-none focus:outline-none focus:border-brand/60"
            />
            <Button onClick={send} disabled={pending || !input.trim()} loading={pending}>
              Send
            </Button>
          </div>
        </Card>

        {/* ── Draft panel ── */}
        <Card className="lg:col-span-2 lg:sticky lg:top-6">
          <DraftPanel
            draft={draft}
            onSave={saveToMarketplace}
            saving={saving}
            onReset={startOver}
          />
        </Card>
      </div>
    </div>
  )
}
