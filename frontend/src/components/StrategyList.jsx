/**
 * StrategyList — list all saved strategies with status and controls.
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = ''

export default function StrategyList() {
  const [strategies, setStrategies] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStrategies()
  }, [])

  async function fetchStrategies() {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/strategies`)
      if (res.ok) setStrategies(await res.json())
    } catch { /* ignore */ }
    setLoading(false)
  }

  async function toggleActive(id, currentActive) {
    try {
      await fetch(`${API_BASE}/api/strategies/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !currentActive }),
      })
      setStrategies(prev =>
        prev.map(s => s.id === id ? { ...s, is_active: !currentActive } : s)
      )
    } catch { /* ignore */ }
  }

  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Strategies</h1>
        <Link
          to="/strategies/new"
          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm
                     font-medium rounded-lg transition-colors"
        >
          + New Strategy
        </Link>
      </div>

      {loading ? (
        <p className="text-slate-500 text-sm animate-pulse">Loading…</p>
      ) : strategies.length === 0 ? (
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-8 text-center">
          <p className="text-slate-400 text-sm mb-4">No strategies yet.</p>
          <Link
            to="/strategies/new"
            className="text-emerald-400 hover:text-emerald-300 text-sm font-medium"
          >
            Create your first strategy →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {strategies.map((s) => (
            <div
              key={s.id}
              className="bg-slate-800/80 border border-slate-700 rounded-xl p-4
                         hover:border-slate-600 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <Link
                  to={`/strategies/${s.id}`}
                  className="text-sm font-semibold text-white hover:text-emerald-300 transition-colors"
                >
                  {s.name}
                </Link>
                <div className="flex items-center gap-2">
                  {s.rule_count > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded">
                      {s.rule_count} rules
                    </span>
                  )}
                  {s.watchlist_count > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded">
                      {s.watchlist_count} stocks
                    </span>
                  )}
                  <button
                    onClick={() => toggleActive(s.id, s.is_active)}
                    className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-colors ${
                      s.is_active
                        ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                        : 'bg-slate-700 border-slate-600 text-slate-400'
                    }`}
                  >
                    {s.is_active ? 'Active' : 'Paused'}
                  </button>
                </div>
              </div>
              <p className="text-xs text-slate-400">{s.description}</p>
              <p className="text-[10px] text-slate-600 mt-1">
                Created {new Date(s.created_at).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
