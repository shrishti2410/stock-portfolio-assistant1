/**
 * USSignals — manual execution page for US IT short signals.
 * Route: /it-bear/us-signals
 *
 * Big banner, signal cards for ACN/IBM/CTSH etc., copy order details,
 * manual execution checklist tracking.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import ITBearNav from './ITBearNav'
import { fmtNum, fmtPct, pctColor } from '../../utils/format'

const API_BASE = ''

// US IT stocks we track
const US_SYMBOLS = ['ACN', 'IBM', 'CTSH', 'WIT', 'EPAM', 'GLOB', 'KFRC']

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback: select and copy
      const el = document.createElement('textarea')
      el.value = text
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
        copied
          ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300'
          : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
      }`}
    >
      {copied ? 'Copied!' : 'Copy Order Details'}
    </button>
  )
}

function ExecutedToggle({ symbol, executed, onToggle }) {
  return (
    <button
      onClick={() => onToggle(symbol)}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
        executed
          ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
          : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:border-slate-500'
      }`}
    >
      <div className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 ${
        executed ? 'bg-emerald-500/40 border-emerald-400' : 'border-slate-500'
      }`}>
        {executed && <span className="text-[10px] text-emerald-300 font-bold leading-none">✓</span>}
      </div>
      {executed ? 'Executed in broker' : 'Mark as executed in broker'}
    </button>
  )
}

function SignalCard({ signal, executed, onMarkExecuted }) {
  const chg = signal.change_1d ?? 0

  // Build order details string for clipboard
  const orderDetails = [
    `Symbol: ${signal.symbol}`,
    `Direction: SHORT / PUT`,
    signal.structure ? `Structure: ${signal.structure}` : null,
    signal.strike ? `Strike: ${signal.strike}` : null,
    signal.expiry ? `Expiry: ${signal.expiry}` : null,
    signal.price !== undefined ? `Current Price: $${fmtNum(signal.price, 2)}` : null,
    signal.target ? `Target: $${fmtNum(signal.target, 2)}` : null,
    signal.stop_loss ? `Stop Loss: $${fmtNum(signal.stop_loss, 2)}` : null,
    `Broker: eToro / IBKR`,
    `Note: Manual execution required — US trades not automated`,
  ].filter(Boolean).join('\n')

  return (
    <div className={`bg-slate-800/80 border rounded-xl p-4 transition-colors ${
      executed ? 'border-emerald-500/30' : 'border-slate-700'
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-lg">🇺🇸</span>
            <span className="text-base font-black text-white">{signal.symbol}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded border bg-blue-500/20 border-blue-500/30 text-blue-300">
              US
            </span>
          </div>
          <p className="text-xs text-slate-400">{signal.name}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-base font-bold text-white tabular-nums">
            ${fmtNum(signal.price, 2)}
          </p>
          <p className={`text-xs tabular-nums ${pctColor(chg)}`}>{fmtPct(chg, 2)}</p>
        </div>
      </div>

      {/* Signal details */}
      {signal.structure && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
          <p className="text-[10px] text-slate-500 uppercase mb-0.5">Signal Structure</p>
          <p className="text-sm font-semibold text-red-300">{signal.structure}</p>
        </div>
      )}

      {/* Strike/Expiry chips */}
      <div className="flex flex-wrap gap-2 mb-3">
        {signal.strike && (
          <span className="text-[11px] px-2 py-1 rounded border bg-red-500/10 border-red-500/20 text-red-300">
            Strike: {signal.strike}
          </span>
        )}
        {signal.expiry && (
          <span className="text-[11px] px-2 py-1 rounded border bg-slate-700 border-slate-600 text-slate-300">
            Expiry: {signal.expiry}
          </span>
        )}
        {signal.target && (
          <span className="text-[11px] px-2 py-1 rounded border bg-emerald-500/10 border-emerald-500/20 text-emerald-300">
            Target: ${fmtNum(signal.target, 2)}
          </span>
        )}
        {signal.stop_loss && (
          <span className="text-[11px] px-2 py-1 rounded border bg-red-500/10 border-red-500/20 text-red-300">
            Stop: ${fmtNum(signal.stop_loss, 2)}
          </span>
        )}
      </div>

      {/* Reasoning */}
      {signal.reasoning && (
        <p className="text-[11px] text-slate-400 mb-3 leading-relaxed line-clamp-3">
          {signal.reasoning}
        </p>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-slate-700/40">
        <CopyButton text={orderDetails} />
        <ExecutedToggle
          symbol={signal.symbol}
          executed={executed}
          onToggle={onMarkExecuted}
        />
        <Link
          to={`/it-bear/strategy-builder/${signal.symbol}`}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25 transition-colors"
        >
          Strategy Builder
        </Link>
      </div>
    </div>
  )
}

export default function USSignals() {
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Track which US trades the user has executed in their broker
  const [executedMap, setExecutedMap] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('us_executed_trades') ?? '{}')
    } catch {
      return {}
    }
  })

  const fetchUSSignals = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch from scanner and filter US stocks
      const [scanRes, universeRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/it-bear/scanner`),
        fetch(`${API_BASE}/api/it-bear/universe`),
      ])

      let usSignals = []

      if (scanRes.status === 'fulfilled' && scanRes.value.ok) {
        const json = await scanRes.value.json()
        const allSignals = Array.isArray(json) ? json : json.signals ?? []
        usSignals = allSignals.filter(s => s.layer?.toLowerCase() === 'us' || US_SYMBOLS.includes(s.symbol))
      }

      // Fill in price data from universe
      if (universeRes.status === 'fulfilled' && universeRes.value.ok) {
        const uJson = await universeRes.value.json()
        const uStocks = Array.isArray(uJson) ? uJson : uJson.stocks ?? []
        const priceMap = Object.fromEntries(uStocks.map(s => [s.symbol, s]))

        // Add any US stocks not already in signals
        US_SYMBOLS.forEach(sym => {
          if (!usSignals.find(s => s.symbol === sym)) {
            const stockData = priceMap[sym]
            if (stockData) {
              usSignals.push({
                symbol: sym,
                name: stockData.name,
                price: stockData.price,
                change_1d: stockData.change_1d,
                layer: 'us',
                structure: null,
                reasoning: null,
              })
            } else {
              usSignals.push({
                symbol: sym,
                name: sym,
                price: null,
                change_1d: null,
                layer: 'us',
              })
            }
          } else {
            // Merge price data
            const idx = usSignals.findIndex(s => s.symbol === sym)
            if (idx >= 0 && priceMap[sym]) {
              usSignals[idx] = { ...priceMap[sym], ...usSignals[idx] }
            }
          }
        })
      }

      setSignals(usSignals.sort((a, b) => a.symbol.localeCompare(b.symbol)))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchUSSignals() }, [fetchUSSignals])

  function handleMarkExecuted(symbol) {
    setExecutedMap(prev => {
      const next = { ...prev, [symbol]: !prev[symbol] }
      localStorage.setItem('us_executed_trades', JSON.stringify(next))
      return next
    })
  }

  const executedCount = Object.values(executedMap).filter(Boolean).length

  return (
    <div>
      <ITBearNav />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

        {/* Banner */}
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-5 mb-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center shrink-0">
              <span className="text-blue-300 font-bold text-lg">!</span>
            </div>
            <div>
              <h2 className="text-sm font-bold text-blue-300 mb-1">
                US Trades Execute Manually in eToro / IBKR
              </h2>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                US IT signals (ACN, IBM, CTSH, etc.) cannot be auto-executed — they require a US broker account.
                Use "Copy Order Details" to copy trade parameters, then execute manually in eToro, IBKR, or your US broker.
                Mark each trade as executed to track your manual positions.
              </p>
            </div>
          </div>
        </div>

        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <h1 className="text-2xl font-black text-white">US IT Signals</h1>
            <p className="text-slate-500 text-xs mt-1">
              ACN, IBM, CTSH and more — bearish signals for manual execution
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-sm font-bold text-white">{executedCount} / {US_SYMBOLS.length}</p>
            <p className="text-[10px] text-slate-500">trades marked executed</p>
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-7 h-7 border-2 border-slate-600 border-t-blue-400 rounded-full animate-spin" />
            <p className="text-slate-500 text-sm ml-3">Loading US signals…</p>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-5 mb-4 flex items-center justify-between">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={fetchUSSignals}
              className="px-4 py-2 text-xs font-medium rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Signal cards */}
        {!loading && !error && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {signals.map(signal => (
              <SignalCard
                key={signal.symbol}
                signal={signal}
                executed={executedMap[signal.symbol] ?? false}
                onMarkExecuted={handleMarkExecuted}
              />
            ))}
          </div>
        )}

        {/* Manual execution checklist summary */}
        {!loading && signals.length > 0 && (
          <div className="mt-6 bg-slate-800/80 border border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Manual Execution Checklist</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {US_SYMBOLS.map(sym => (
                <div
                  key={sym}
                  onClick={() => handleMarkExecuted(sym)}
                  className={`cursor-pointer flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-colors ${
                    executedMap[sym]
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 ${
                    executedMap[sym] ? 'bg-emerald-500/40 border-emerald-400' : 'border-slate-500'
                  }`}>
                    {executedMap[sym] && <span className="text-[10px] font-bold leading-none">✓</span>}
                  </div>
                  <span className="font-semibold">{sym}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-600 mt-3">
              Checklist is saved locally in your browser. Click any symbol to toggle its execution status.
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
