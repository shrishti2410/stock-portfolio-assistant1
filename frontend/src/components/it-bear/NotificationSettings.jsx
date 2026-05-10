/**
 * NotificationSettings — configure notification channels + auto-execution layers.
 * Route: /it-bear/notifications
 *
 * In-App, Email, Telegram channel cards with test buttons.
 * Auto-execution toggles per layer (Core, Tactical, US locked, Hedge).
 * Daily brief time selector.
 */

import { useState, useEffect, useCallback } from 'react'
import ITBearNav from './ITBearNav'

const API_BASE = 'http://localhost:8000'

function Toggle({ enabled, onChange, locked = false }) {
  return (
    <button
      onClick={() => !locked && onChange(!enabled)}
      disabled={locked}
      className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${
        locked
          ? 'opacity-50 cursor-not-allowed'
          : 'cursor-pointer'
      } ${enabled && !locked ? 'bg-emerald-500/60' : 'bg-slate-700'}`}
      aria-label={enabled ? 'Enabled' : 'Disabled'}
    >
      <div className={`absolute top-0.5 w-5 h-5 rounded-full transition-all ${
        enabled && !locked ? 'left-5 bg-emerald-300' : 'left-0.5 bg-slate-400'
      }`} />
    </button>
  )
}

// Auto-execution layer definitions
const LAYERS = [
  {
    id: 'core',
    label: 'Core Layer',
    desc: 'NIFTY IT index puts — main bearish position. High conviction only.',
    locked: false,
  },
  {
    id: 'tactical',
    label: 'Tactical Layer',
    desc: 'Individual stock shorts (TCS, INFY, etc.) on earnings/momentum signals.',
    locked: false,
  },
  {
    id: 'us',
    label: 'US Layer',
    desc: 'ACN, IBM, CTSH signals — always manual. Executed in eToro / IBKR.',
    locked: true,
    lockReason: 'Manual only — executed in eToro/IBKR',
  },
  {
    id: 'hedge',
    label: 'Hedge Layer',
    desc: 'Protective calls / reversal positions. Auto-execute when VIX spikes.',
    locked: false,
  },
]

function ChannelCard({ channel, config, onTest, testing }) {
  const isConfigured = config?.configured ?? false
  return (
    <div className={`bg-slate-800/80 border rounded-xl p-5 transition-colors ${
      isConfigured ? 'border-emerald-500/30' : 'border-slate-700'
    }`}>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="text-sm font-semibold text-white">{channel.label}</h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
              isConfigured
                ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300'
                : 'bg-slate-700 border-slate-600 text-slate-500'
            }`}>
              {isConfigured ? 'Configured' : 'Not configured'}
            </span>
          </div>
          <p className="text-[10px] text-slate-500">{channel.desc}</p>
        </div>
        <button
          onClick={() => onTest(channel.id)}
          disabled={testing === channel.id || !isConfigured}
          className="shrink-0 px-3 py-1.5 text-xs font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {testing === channel.id ? 'Sending…' : 'Test'}
        </button>
      </div>

      {/* Setup instructions */}
      <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700/50 text-[11px] text-slate-400 space-y-1.5">
        {channel.instructions.map((step, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-slate-600 shrink-0">{i + 1}.</span>
            <span className="leading-relaxed">{step}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const CHANNELS = [
  {
    id: 'websocket',
    label: 'In-App Notifications',
    desc: 'Real-time alerts inside this dashboard via WebSocket.',
    instructions: [
      'No configuration needed — works automatically when the backend is running.',
      'Notifications appear as toast alerts in the top-right of the page.',
      'Requires the trading engine to be running for live updates.',
    ],
  },
  {
    id: 'email',
    label: 'Email Notifications',
    desc: 'Daily briefings + urgent alerts sent to your email.',
    instructions: [
      'Add to backend/.env file:',
      'SMTP_HOST=smtp.gmail.com',
      'SMTP_PORT=587',
      'SMTP_USER=your-email@gmail.com',
      'SMTP_PASS=your-app-password (not your login password)',
      'ALERT_EMAIL_TO=rahul.taori@tomtom.com',
      'For Gmail: enable 2FA, then generate App Password at myaccount.google.com/apppasswords',
      'Restart the backend after saving .env changes.',
    ],
  },
  {
    id: 'telegram',
    label: 'Telegram Notifications',
    desc: 'Instant alerts to your Telegram chat — fastest channel.',
    instructions: [
      'Open Telegram, search for @BotFather',
      'Send /newbot — follow prompts to name your bot',
      'Copy the bot token (looks like 1234567890:ABC...)',
      'Add to backend/.env: TELEGRAM_BOT_TOKEN=your_token',
      'Open your new bot in Telegram, click Start / send /start',
      'Get your Chat ID: visit https://api.telegram.org/bot{TOKEN}/getUpdates',
      'Add to backend/.env: TELEGRAM_CHAT_ID=your_chat_id',
      'Restart the backend — test with the button above.',
    ],
  },
]

// Daily brief times
const BRIEF_TIMES = [
  '07:00', '07:30', '08:00', '08:30', '09:00', '09:15', '09:30', '10:00',
  '15:30', '16:00', '17:00', '18:00', '19:00', '20:00',
]

export default function NotificationSettings() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const [testing, setTesting] = useState(null) // channel id being tested
  const [testResult, setTestResult] = useState(null) // { channel, success, message }

  // Local layer toggles (not persisted to notifications/config, persisted separately)
  const [layerAutoExec, setLayerAutoExec] = useState({
    core: false,
    tactical: false,
    us: false, // always false, locked
    hedge: false,
  })

  const [briefTime, setBriefTime] = useState('09:00')

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/notifications/config`)
      if (res.ok) {
        const data = await res.json()
        setConfig(data)
        if (data.layer_auto_exec) setLayerAutoExec({ ...layerAutoExec, ...data.layer_auto_exec, us: false })
        if (data.daily_brief_time) setBriefTime(data.daily_brief_time)
      } else {
        // No config yet — show defaults
        setConfig({ channels: {} })
      }
    } catch {
      setConfig({ channels: {} })
    } finally {
      setLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchConfig() }, [fetchConfig])

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const payload = {
        layer_auto_exec: { ...layerAutoExec, us: false },
        daily_brief_time: briefTime,
      }
      const res = await fetch(`${API_BASE}/api/notifications/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Save failed (${res.status})`)
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleTest(channelId) {
    setTesting(channelId)
    setTestResult(null)
    try {
      const res = await fetch(`${API_BASE}/api/notifications/test/${channelId}`, { method: 'POST' })
      const body = await res.json().catch(() => ({}))
      setTestResult({
        channel: channelId,
        success: res.ok,
        message: body.message ?? (res.ok ? 'Test notification sent!' : 'Failed to send test.'),
      })
    } catch (err) {
      setTestResult({ channel: channelId, success: false, message: err.message })
    } finally {
      setTesting(null)
      setTimeout(() => setTestResult(null), 5000)
    }
  }

  function handleLayerToggle(layerId, value) {
    if (layerId === 'us') return // locked
    setLayerAutoExec(prev => ({ ...prev, [layerId]: value }))
  }

  if (loading) {
    return (
      <div>
        <ITBearNav />
        <div className="flex items-center justify-center py-24">
          <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
          <p className="text-slate-500 text-sm ml-3">Loading notification config…</p>
        </div>
      </div>
    )
  }

  const channels = config?.channels ?? {}

  return (
    <div>
      <ITBearNav />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-black text-white">Notification Settings</h1>
            <p className="text-slate-500 text-xs mt-1">
              Configure alert channels and auto-execution rules per layer.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {saved && <span className="text-xs text-emerald-400 font-medium">Saved!</span>}
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm font-semibold rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving…' : 'Save Settings'}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 mb-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {testResult && (
          <div className={`rounded-xl p-3 mb-4 text-sm border ${
            testResult.success
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}>
            {testResult.message}
          </div>
        )}

        <div className="space-y-5">

          {/* Notification Channels */}
          <section>
            <h2 className="text-sm font-semibold text-slate-200 mb-3">Notification Channels</h2>
            <div className="space-y-4">
              {CHANNELS.map(channel => (
                <ChannelCard
                  key={channel.id}
                  channel={channel}
                  config={channels[channel.id] ?? { configured: channel.id === 'websocket' }}
                  onTest={handleTest}
                  testing={testing}
                />
              ))}
            </div>
          </section>

          {/* Auto-Execution Layers */}
          <section>
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-slate-200 mb-1">
                Per-Layer Auto-Execution
              </h2>
              <p className="text-[10px] text-slate-500 mb-4">
                When enabled, signals from that layer are automatically submitted as paper trade proposals
                without requiring manual approval. US layer is always manual.
              </p>

              <div className="space-y-3">
                {LAYERS.map(layer => (
                  <div
                    key={layer.id}
                    className={`flex items-center justify-between p-3.5 rounded-xl border transition-colors ${
                      layer.locked
                        ? 'bg-slate-800/40 border-slate-700/50 opacity-60'
                        : layerAutoExec[layer.id]
                        ? 'bg-emerald-500/5 border-emerald-500/20'
                        : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex-1 mr-4">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-sm font-medium text-slate-200">{layer.label}</p>
                        {layer.locked && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 border border-slate-600 text-slate-500">
                            {layer.lockReason}
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-500">{layer.desc}</p>
                    </div>
                    <Toggle
                      enabled={layerAutoExec[layer.id]}
                      onChange={(v) => handleLayerToggle(layer.id, v)}
                      locked={layer.locked}
                    />
                  </div>
                ))}
              </div>

              <div className="mt-3 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                <p className="text-[11px] text-amber-300">
                  Auto-execution only works in paper trading mode. Live trading always requires manual approval.
                </p>
              </div>
            </div>
          </section>

          {/* Daily Brief Time */}
          <section>
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-slate-200 mb-1">Daily Brief</h2>
              <p className="text-[10px] text-slate-500 mb-4">
                Receive a daily market brief with IT sector summary, open positions,
                and upcoming earnings. Sent to all configured channels.
              </p>
              <div className="flex items-center gap-3">
                <label className="text-xs text-slate-400">Send at:</label>
                <select
                  value={briefTime}
                  onChange={e => setBriefTime(e.target.value)}
                  className="py-2 px-3 bg-slate-900 border border-slate-600 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500/50 transition-colors"
                >
                  {BRIEF_TIMES.map(t => (
                    <option key={t} value={t}>{t} IST</option>
                  ))}
                </select>
                <span className="text-[10px] text-slate-600">Indian Standard Time (UTC+5:30)</span>
              </div>
            </div>
          </section>

          {/* Test All */}
          <section>
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-slate-200 mb-3">Send Test to All Channels</h2>
              <p className="text-[11px] text-slate-500 mb-3">
                Sends a test notification to every configured channel simultaneously.
              </p>
              <button
                onClick={() => handleTest('all')}
                disabled={testing === 'all'}
                className="px-5 py-2.5 text-sm font-bold rounded-xl border bg-blue-500/20 border-blue-500/40 text-blue-300 hover:bg-blue-500/30 disabled:opacity-50 transition-colors"
              >
                {testing === 'all' ? 'Sending to all channels…' : 'Test All Channels'}
              </button>
            </div>
          </section>

        </div>

        {/* Bottom save */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 text-sm font-bold rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving…' : 'Save All Settings'}
          </button>
        </div>
      </main>
    </div>
  )
}
