/**
 * TradingSettings — configuration page for the trading engine.
 *
 * Capital settings, position limits, strategy toggles, Paper/Live mode switch,
 * scan interval, engine control, and circuit breaker reset.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'

const API_BASE = ''

// The 3 core strategies (must match backend trading/strategies.py IDs)
const STRATEGY_DEFS = [
  { id: 'iron_condor', name: 'Iron Condor', description: 'Sell OTM CE+PE with protective wings. Range-bound, low VIX. Win rate 65-70%.' },
  { id: 'straddle_adjust', name: 'Straddle Sell + Adjust', description: 'Sell ATM CE+PE, adjust losing side. Elevated VIX premium. Win rate 60-65%.' },
  { id: 'directional_spread', name: 'Directional Spread', description: 'Bull Call or Bear Put spread based on strong technical signals. Win rate 45-55%.' },
]

function NumberInput({ label, name, value, onChange, min, max, prefix = '₹', helpText }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-300 mb-1.5">{label}</label>
      {helpText && <p className="text-[10px] text-slate-500 mb-1.5">{helpText}</p>}
      <div className="relative">
        {prefix && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm pointer-events-none">
            {prefix}
          </span>
        )}
        <input
          type="number"
          name={name}
          value={value}
          onChange={onChange}
          min={min}
          max={max}
          className={`w-full py-2 pr-3 bg-slate-800 border border-slate-600 rounded-lg text-sm text-slate-200
                      focus:outline-none focus:border-blue-500 transition-colors ${prefix ? 'pl-7' : 'pl-3'}`}
        />
      </div>
    </div>
  )
}

function SectionCard({ title, children }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4 pb-3 border-b border-slate-700">{title}</h3>
      {children}
    </div>
  )
}

export default function TradingSettings() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [engineRunning, setEngineRunning] = useState(false)
  const [engineLoading, setEngineLoading] = useState(false)
  const [cbResetting, setCbResetting] = useState(false)

  // Live mode confirmation modal
  const [showLiveModal, setShowLiveModal] = useState(false)
  const [liveConfirmText, setLiveConfirmText] = useState('')
  const REQUIRED_PHRASE = 'I UNDERSTAND THE RISKS'

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [configRes, statusRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/trading/config`),
        fetch(`${API_BASE}/api/trading/status`),
      ])

      if (configRes.status === 'fulfilled' && configRes.value.ok) {
        const data = await configRes.value.json()
        // Normalize: strategies_enabled comes as array from backend
        setConfig({
          max_capital: data.max_capital ?? 200000,
          max_loss_per_trade: data.max_loss_per_trade ?? 5000,
          max_daily_loss: data.max_daily_loss ?? 10000,
          max_positions: data.max_positions ?? 3,
          risk_per_trade_pct: data.risk_per_trade_pct ?? 2.0,
          scan_interval_min: data.scan_interval_min ?? 15,
          paper_mode: data.paper_mode ?? 1,
          engine_enabled: data.engine_enabled ?? 0,
          // strategies_enabled is a list of IDs like ["iron_condor", "straddle_adjust"]
          strategies_enabled: Array.isArray(data.strategies_enabled) ? data.strategies_enabled : [],
        })
      } else {
        setConfig({
          max_capital: 200000,
          max_loss_per_trade: 5000,
          max_daily_loss: 10000,
          max_positions: 3,
          risk_per_trade_pct: 2.0,
          scan_interval_min: 15,
          paper_mode: 1,
          engine_enabled: 0,
          strategies_enabled: [],
        })
      }

      if (statusRes.status === 'fulfilled' && statusRes.value.ok) {
        const s = await statusRes.value.json()
        setEngineRunning(s.running ?? false)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchConfig() }, [fetchConfig])

  function handleNumberChange(e) {
    const { name, value } = e.target
    setConfig(prev => ({ ...prev, [name]: parseFloat(value) || 0 }))
  }

  function handleStrategyToggle(strategyId) {
    setConfig(prev => {
      const list = prev.strategies_enabled ?? []
      const isEnabled = list.includes(strategyId)
      return {
        ...prev,
        strategies_enabled: isEnabled
          ? list.filter(id => id !== strategyId)
          : [...list, strategyId],
      }
    })
  }

  function handleModeChange(newMode) {
    if (newMode === 'live') {
      setShowLiveModal(true)
    } else {
      setConfig(prev => ({ ...prev, paper_mode: 1 }))
    }
  }

  function confirmLiveMode() {
    if (liveConfirmText !== REQUIRED_PHRASE) return
    setConfig(prev => ({ ...prev, paper_mode: 0 }))
    setShowLiveModal(false)
    setLiveConfirmText('')
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      // Send exactly the fields the backend expects
      const payload = {
        max_capital: config.max_capital,
        max_loss_per_trade: config.max_loss_per_trade,
        max_daily_loss: config.max_daily_loss,
        max_positions: config.max_positions,
        risk_per_trade_pct: config.risk_per_trade_pct,
        scan_interval_min: config.scan_interval_min,
        paper_mode: config.paper_mode,
        engine_enabled: config.engine_enabled,
        strategies_enabled: config.strategies_enabled,
      }

      const res = await fetch(`${API_BASE}/api/trading/config`, {
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

  async function toggleEngine() {
    setEngineLoading(true)
    try {
      if (!engineRunning) {
        // Before starting, ensure engine_enabled is true and save config
        const saveRes = await fetch(`${API_BASE}/api/trading/config`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            engine_enabled: true,
            strategies_enabled: config.strategies_enabled,
            paper_mode: config.paper_mode,
            scan_interval_min: config.scan_interval_min,
          }),
        })
        if (!saveRes.ok) throw new Error('Failed to save config')

        const res = await fetch(`${API_BASE}/api/trading/start`, { method: 'POST' })
        if (res.ok) {
          setEngineRunning(true)
          setConfig(prev => ({ ...prev, engine_enabled: 1 }))
        } else {
          const body = await res.json().catch(() => ({}))
          setError(body.detail ?? 'Failed to start engine')
        }
      } else {
        const res = await fetch(`${API_BASE}/api/trading/stop`, { method: 'POST' })
        if (res.ok) setEngineRunning(false)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setEngineLoading(false)
    }
  }

  async function resetCircuitBreaker() {
    if (!window.confirm('Reset the circuit breaker? This will allow the engine to resume trading after a daily loss limit breach.')) return
    setCbResetting(true)
    try {
      await fetch(`${API_BASE}/api/trading/circuit-breaker/reset`, { method: 'POST' })
    } catch { /* ignore */ }
    finally { setCbResetting(false) }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
        <p className="text-slate-500 text-sm ml-3">Loading settings…</p>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center">
        <p className="text-slate-400 text-sm">Failed to load configuration.</p>
        <button onClick={fetchConfig} className="text-blue-400 underline text-sm mt-2">Retry</button>
      </div>
    )
  }

  const enabledStrategies = config.strategies_enabled ?? []
  const isLive = !config.paper_mode
  const noStrategiesEnabled = enabledStrategies.length === 0

  return (
    <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 text-sm mb-1">
            <Link to="/trading" className="text-slate-500 hover:text-slate-300 transition-colors">Trading</Link>
            <span className="text-slate-600">/</span>
            <span className="text-slate-300">Settings</span>
          </div>
          <h1 className="text-xl font-bold text-white">Trading Settings</h1>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="text-xs text-emerald-400 font-medium">Saved!</span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-semibold rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 mb-4 text-sm text-red-400">
          {error}
        </div>
      )}

      <div className="space-y-5">

        {/* ── Capital Settings ──────────────────────────────────────────── */}
        <SectionCard title="Capital Settings">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <NumberInput
              label="Maximum Capital"
              name="max_capital"
              value={config.max_capital ?? ''}
              onChange={handleNumberChange}
              min={10000}
              helpText="Total capital allocated to options trading"
            />
            <NumberInput
              label="Max Loss Per Trade"
              name="max_loss_per_trade"
              value={config.max_loss_per_trade ?? ''}
              onChange={handleNumberChange}
              min={1000}
              helpText="Maximum allowable loss per individual trade"
            />
            <NumberInput
              label="Max Daily Loss"
              name="max_daily_loss"
              value={config.max_daily_loss ?? ''}
              onChange={handleNumberChange}
              min={1000}
              helpText="Circuit breaker triggers when daily loss exceeds this"
            />
            <NumberInput
              label="Risk Per Trade %"
              name="risk_per_trade_pct"
              value={config.risk_per_trade_pct ?? ''}
              onChange={handleNumberChange}
              min={0.5}
              max={10}
              prefix="%"
              helpText="Percentage of capital at risk per trade (2% recommended)"
            />
          </div>
        </SectionCard>

        {/* ── Position Settings ─────────────────────────────────────────── */}
        <SectionCard title="Position Settings">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <NumberInput
              label="Max Open Positions"
              name="max_positions"
              value={config.max_positions ?? ''}
              onChange={handleNumberChange}
              min={1}
              max={10}
              prefix=""
              helpText="Maximum simultaneously open positions"
            />
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Scan Interval</label>
              <p className="text-[10px] text-slate-500 mb-1.5">How often the engine scans for opportunities</p>
              <select
                value={config.scan_interval_min ?? 15}
                onChange={e => setConfig(prev => ({ ...prev, scan_interval_min: parseInt(e.target.value) }))}
                className="w-full py-2 px-3 bg-slate-800 border border-slate-600 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
              >
                <option value={5}>Every 5 minutes</option>
                <option value={10}>Every 10 minutes</option>
                <option value={15}>Every 15 minutes</option>
                <option value={30}>Every 30 minutes</option>
              </select>
            </div>
          </div>
        </SectionCard>

        {/* ── Strategy Toggles ──────────────────────────────────────────── */}
        <SectionCard title="Strategy Toggles">
          <p className="text-[10px] text-slate-500 mb-3">
            Enable the strategies you want the engine to evaluate. At least one must be enabled to start trading.
          </p>
          <div className="space-y-3">
            {STRATEGY_DEFS.map(strat => {
              const isEnabled = enabledStrategies.includes(strat.id)
              return (
                <div key={strat.id}
                     className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-colors ${
                       isEnabled
                         ? 'bg-emerald-500/5 border-emerald-500/30'
                         : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                     }`}
                     onClick={() => handleStrategyToggle(strat.id)}
                >
                  <div className="flex-1 mr-4">
                    <p className="text-sm font-medium text-slate-200">{strat.name}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{strat.description}</p>
                  </div>
                  <div className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${
                    isEnabled ? 'bg-emerald-500/60' : 'bg-slate-700'
                  }`}>
                    <div className={`absolute top-0.5 w-5 h-5 rounded-full transition-all ${
                      isEnabled ? 'left-5 bg-emerald-300' : 'left-0.5 bg-slate-400'
                    }`} />
                  </div>
                </div>
              )
            })}
          </div>
          {noStrategiesEnabled && (
            <p className="text-amber-400 text-xs mt-3">
              ⚠ No strategies enabled. Enable at least one strategy before starting the engine.
            </p>
          )}
        </SectionCard>

        {/* ── Mode Toggle ───────────────────────────────────────────────── */}
        <SectionCard title="Trading Mode">
          <div className="space-y-4">
            <div className="flex gap-3">
              <button
                onClick={() => handleModeChange('paper')}
                className={`flex-1 py-3 rounded-xl text-sm font-semibold border transition-colors ${
                  !isLive
                    ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                    : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:bg-slate-700'
                }`}
              >
                📝 Paper Trading
              </button>
              <button
                onClick={() => handleModeChange('live')}
                className={`flex-1 py-3 rounded-xl text-sm font-bold border transition-colors ${
                  isLive
                    ? 'bg-red-500/20 border-red-500/40 text-red-300'
                    : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:border-red-500/30 hover:text-red-400'
                }`}
              >
                💰 Live Trading
              </button>
            </div>

            {isLive ? (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                <p className="text-sm font-bold text-red-300 mb-1">⚠ LIVE MODE ACTIVE</p>
                <p className="text-xs text-red-400">
                  Real money will be used. All approved proposals will place actual orders through Zerodha.
                  Requires Kite Connect API key configured in backend .env file.
                </p>
              </div>
            ) : (
              <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl p-4">
                <p className="text-sm font-medium text-blue-300 mb-1">📝 Paper Trading Mode</p>
                <p className="text-xs text-slate-400">
                  All trades are simulated. No real orders placed. Perfect for testing and building confidence.
                </p>
              </div>
            )}
          </div>
        </SectionCard>

        {/* ── Engine Control ────────────────────────────────────────────── */}
        <SectionCard title="Engine Control">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-200">Trading Engine</p>
              <p className={`text-xs mt-0.5 ${engineRunning ? 'text-emerald-400' : 'text-slate-500'}`}>
                {engineRunning ? 'Engine is running and scanning for opportunities' : 'Engine is stopped'}
              </p>
              {noStrategiesEnabled && !engineRunning && (
                <p className="text-[10px] text-amber-400 mt-1">Enable at least one strategy above and save before starting</p>
              )}
            </div>
            <button
              onClick={toggleEngine}
              disabled={engineLoading || (!engineRunning && noStrategiesEnabled)}
              className={`px-5 py-2.5 text-sm font-bold rounded-xl border transition-colors disabled:opacity-50 ${
                engineRunning
                  ? 'bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25'
                  : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/25'
              }`}
            >
              {engineLoading ? '…' : engineRunning ? 'Stop Engine' : 'Start Engine'}
            </button>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-200">Circuit Breaker</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Reset after daily loss limit is hit and trading is paused
                </p>
              </div>
              <button
                onClick={resetCircuitBreaker}
                disabled={cbResetting}
                className="px-4 py-2 text-xs font-medium rounded-lg border bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20 disabled:opacity-50 transition-colors"
              >
                {cbResetting ? 'Resetting…' : 'Reset Circuit Breaker'}
              </button>
            </div>
          </div>
        </SectionCard>

        {/* ── Zerodha API Info ────────────────────────────────────────────── */}
        <SectionCard title="Zerodha API Setup">
          <div className="space-y-3">
            <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700/50">
              <p className="text-sm font-medium text-slate-200 mb-2">For Paper Trading (Current)</p>
              <p className="text-xs text-slate-400">
                No Zerodha API key needed. Paper mode simulates all orders with virtual money.
                Your existing Zerodha login (Console API) is used only for portfolio holdings.
              </p>
            </div>
            <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700/50">
              <p className="text-sm font-medium text-slate-200 mb-2">For Live Trading (When Ready)</p>
              <ul className="text-xs text-slate-400 space-y-1.5">
                <li>1. Purchase Kite Connect API at <span className="text-blue-400">kite.trade</span> (₹2,000 one-time)</li>
                <li>2. Add to <code className="text-amber-300 bg-slate-800 px-1 rounded">backend/.env</code>:</li>
                <li className="pl-4">
                  <code className="text-emerald-300 text-[10px]">ZERODHA_API_KEY=your_api_key</code><br/>
                  <code className="text-emerald-300 text-[10px]">ZERODHA_API_SECRET=your_api_secret</code>
                </li>
                <li>3. Login via Dashboard → the access token auto-refreshes daily</li>
                <li>4. Switch to Live mode above and restart the engine</li>
              </ul>
            </div>
          </div>
        </SectionCard>

      </div>

      {/* Bottom save button */}
      <div className="mt-6 flex items-center justify-between">
        <Link
          to="/trading"
          className="px-4 py-2 text-sm font-medium rounded-xl bg-slate-800 border border-slate-700 text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
        >
          Back to Dashboard
        </Link>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 text-sm font-bold rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving…' : 'Save All Changes'}
        </button>
      </div>

      {/* ── Live Mode Confirmation Modal ──────────────────────────────────── */}
      {showLiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-red-500/40 rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center">
                <span className="text-red-400 text-lg font-bold">!</span>
              </div>
              <h3 className="text-lg font-bold text-red-300">Enable Live Trading</h3>
            </div>

            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
              <p className="text-sm font-semibold text-red-300 mb-2">WARNING: Real Money at Risk</p>
              <ul className="text-xs text-red-400 space-y-1">
                <li>All approved trades will place real orders through Zerodha</li>
                <li>Actual money will be debited from your trading account</li>
                <li>Options trading involves risk of total loss of capital</li>
                <li>Ensure Kite Connect API key is configured in .env</li>
              </ul>
            </div>

            <div className="mb-4">
              <label className="block text-xs font-medium text-slate-400 mb-2">
                Type <span className="text-red-300 font-bold">{REQUIRED_PHRASE}</span> to confirm:
              </label>
              <input
                type="text"
                value={liveConfirmText}
                onChange={e => setLiveConfirmText(e.target.value)}
                placeholder={REQUIRED_PHRASE}
                className="w-full px-3 py-2.5 bg-slate-800 border border-slate-600 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-red-500 transition-colors"
                autoFocus
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => { setShowLiveModal(false); setLiveConfirmText('') }}
                className="flex-1 py-2.5 text-sm font-medium rounded-xl bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmLiveMode}
                disabled={liveConfirmText !== REQUIRED_PHRASE}
                className="flex-1 py-2.5 text-sm font-bold rounded-xl bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Enable Live Trading
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
