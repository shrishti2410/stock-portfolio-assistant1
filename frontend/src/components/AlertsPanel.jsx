/**
 * AlertsPanel — notification-style list of triggered strategy alerts.
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = ''

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('unread') // 'unread' | 'all'

  useEffect(() => {
    fetchAlerts()
  }, [filter])

  async function fetchAlerts() {
    setLoading(true)
    try {
      const unread = filter === 'unread' ? 'true' : 'false'
      const res = await fetch(`${API_BASE}/api/alerts?unread=${unread}`)
      if (res.ok) setAlerts(await res.json())
    } catch { /* ignore */ }
    setLoading(false)
  }

  async function markRead(alertId) {
    try {
      await fetch(`${API_BASE}/api/alerts/${alertId}/read`, { method: 'PUT' })
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, is_read: 1 } : a))
    } catch { /* ignore */ }
  }

  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Alerts</h1>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setFilter('unread')}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              filter === 'unread'
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Unread
          </button>
          <button
            onClick={() => setFilter('all')}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              filter === 'all'
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            All
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-slate-500 text-sm animate-pulse">Loading…</p>
      ) : alerts.length === 0 ? (
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-8 text-center">
          <p className="text-slate-400 text-sm mb-2">No alerts yet.</p>
          <p className="text-slate-500 text-xs">
            Alerts are triggered when a strategy's rules match on a watchlist stock.
          </p>
          <Link
            to="/strategies/new"
            className="inline-block mt-4 text-emerald-400 hover:text-emerald-300 text-sm font-medium"
          >
            Create a strategy →
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => {
            const signalData = (() => {
              try { return JSON.parse(alert.signal_data || '{}') } catch { return {} }
            })()

            return (
              <div
                key={alert.id}
                className={`bg-slate-800/80 border rounded-xl p-4 transition-colors ${
                  alert.is_read
                    ? 'border-slate-700/50 opacity-60'
                    : 'border-amber-500/30 bg-amber-500/5'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/stock/${alert.symbol}`}
                      className="text-sm font-bold text-white hover:text-emerald-300 transition-colors"
                    >
                      {alert.symbol}
                    </Link>
                    {alert.strategy_name && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded">
                        {alert.strategy_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-500">
                      {new Date(alert.triggered_at).toLocaleString()}
                    </span>
                    {!alert.is_read && (
                      <button
                        onClick={() => markRead(alert.id)}
                        className="text-[10px] px-1.5 py-0.5 rounded border bg-slate-700
                                   border-slate-600 text-slate-400 hover:text-slate-300 transition-colors"
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                </div>

                {/* Signal details */}
                {signalData.triggered_rules && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {signalData.triggered_rules.map((rule, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded border
                                               bg-amber-500/15 border-amber-500/30 text-amber-300">
                        {rule.indicator} {rule.operator} {rule.value ?? rule.value_text}
                      </span>
                    ))}
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
