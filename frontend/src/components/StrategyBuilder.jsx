/**
 * StrategyBuilder — create or edit a trading strategy using natural language.
 *
 * POST /api/strategies with natural language text → backend parses into rules.
 * Shows parsed rules, allows adding symbols to watchlist, and saving.
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API_BASE = ''

const EXAMPLE_STRATEGIES = [
  'Buy when RSI drops below 30 and MACD crosses above signal line',
  'Sell when price drops 10% from 52-week high',
  'Buy when price crosses above 50-day EMA with volume above average',
  'Sell when RSI goes above 75 and ADX shows weak trend',
]

export default function StrategyBuilder() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEdit = !!id

  const [input, setInput] = useState('')
  const [symbols, setSymbols] = useState('')
  const [parsedRules, setParsedRules] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [strategy, setStrategy] = useState(null)

  // Load existing strategy if editing
  useEffect(() => {
    if (!isEdit) return
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/strategies/${id}`)
        if (res.ok) {
          const data = await res.json()
          setStrategy(data)
          setInput(data.raw_input ?? '')
          setSymbols(data.watchlist?.map(w => w.symbol).join(', ') ?? '')
          setParsedRules(data.rules ?? [])
        }
      } catch { /* ignore */ }
    }
    load()
  }, [id, isEdit])

  async function handleParse() {
    if (!input.trim()) return
    setParsing(true)
    setError('')
    setParsedRules(null)
    try {
      const res = await fetch(`${API_BASE}/api/strategies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input: input.trim(),
          symbols: symbols.split(',').map(s => s.trim()).filter(Boolean),
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      const data = await res.json()
      navigate(`/strategies/${data.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setParsing(false)
    }
  }

  async function handleToggleActive() {
    if (!strategy) return
    try {
      await fetch(`${API_BASE}/api/strategies/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !strategy.is_active }),
      })
      setStrategy(prev => ({ ...prev, is_active: !prev.is_active }))
    } catch { /* ignore */ }
  }

  async function handleRun() {
    if (!id) return
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/strategies/${id}/run`, { method: 'POST' })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const alerts = await res.json()
      if (alerts.length === 0) {
        setError('No alerts triggered — conditions not met for any watchlist stock')
      } else {
        navigate('/alerts')
      }
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleDelete() {
    if (!id || !confirm('Delete this strategy?')) return
    try {
      await fetch(`${API_BASE}/api/strategies/${id}`, { method: 'DELETE' })
      navigate('/strategies')
    } catch { /* ignore */ }
  }

  return (
    <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/strategies" className="text-slate-500 hover:text-slate-300 text-sm">← Strategies</Link>
        <h1 className="text-xl font-bold text-white">
          {isEdit ? (strategy?.name ?? 'Strategy') : 'New Strategy'}
        </h1>
      </div>

      {/* Strategy input */}
      {!isEdit && (
        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 mb-4">
          <label className="text-sm font-semibold text-slate-300 mb-2 block">
            Describe your strategy in natural language
          </label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={4}
            placeholder="e.g., Buy when RSI drops below 30 and MACD crosses above signal line"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm
                       text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-500
                       resize-none"
          />

          {/* Examples */}
          <div className="mt-2 flex flex-wrap gap-1">
            {EXAMPLE_STRATEGIES.map((ex, i) => (
              <button
                key={i}
                onClick={() => setInput(ex)}
                className="text-[10px] px-2 py-1 rounded bg-slate-700/50 text-slate-400
                           hover:bg-slate-700 hover:text-slate-300 transition-colors"
              >
                {ex.slice(0, 50)}…
              </button>
            ))}
          </div>

          {/* Watchlist symbols */}
          <label className="text-sm font-semibold text-slate-300 mt-4 mb-1 block">
            Watchlist symbols (comma-separated)
          </label>
          <input
            type="text"
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            placeholder="RELIANCE, TCS, INFY"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm
                       text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-500"
          />

          <button
            onClick={handleParse}
            disabled={parsing || !input.trim()}
            className="mt-4 w-full px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white
                       text-sm font-medium rounded-lg transition-colors disabled:opacity-50
                       disabled:cursor-not-allowed"
          >
            {parsing ? 'Parsing & Saving…' : 'Create Strategy'}
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Existing strategy details */}
      {isEdit && strategy && (
        <div className="space-y-4">
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-300">Strategy Details</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleToggleActive}
                  className={`px-2 py-1 rounded text-xs font-medium border transition-colors ${
                    strategy.is_active
                      ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                      : 'bg-slate-700 border-slate-600 text-slate-400'
                  }`}
                >
                  {strategy.is_active ? 'Active' : 'Paused'}
                </button>
                <button
                  onClick={handleRun}
                  className="px-2 py-1 rounded text-xs font-medium border bg-blue-500/20
                             border-blue-500/40 text-blue-300 hover:bg-blue-500/30 transition-colors"
                >
                  Run Now
                </button>
                <button
                  onClick={handleDelete}
                  className="px-2 py-1 rounded text-xs font-medium border bg-red-500/10
                             border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
            <p className="text-xs text-slate-400 mb-2">{strategy.description}</p>
            <p className="text-xs text-slate-500 italic">"{strategy.raw_input}"</p>
          </div>

          {/* Parsed rules */}
          {strategy.rules?.length > 0 && (
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-slate-300 mb-3">Rules</h2>
              <div className="space-y-2">
                {strategy.rules.map((rule, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2 bg-slate-900/50
                                          rounded-lg border border-slate-700/50">
                    <span className="text-xs font-bold text-blue-400">{rule.indicator}</span>
                    <span className="text-xs text-slate-500">{rule.operator}</span>
                    <span className="text-xs font-medium text-slate-300">
                      {rule.value ?? rule.value_text ?? '—'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Watchlist */}
          {strategy.watchlist?.length > 0 && (
            <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-slate-300 mb-3">Watchlist</h2>
              <div className="flex flex-wrap gap-2">
                {strategy.watchlist.map((w) => (
                  <Link
                    key={w.symbol}
                    to={`/stock/${w.symbol}`}
                    className="px-2 py-1 bg-slate-700 rounded text-xs font-medium text-slate-300
                               hover:bg-slate-600 transition-colors"
                  >
                    {w.symbol}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  )
}
