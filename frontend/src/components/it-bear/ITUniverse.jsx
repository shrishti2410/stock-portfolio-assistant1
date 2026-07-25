/**
 * ITUniverse — full watchlist of 13 India + 8 US IT stocks.
 * Symbol, name, flag, price, 1d change, tier badge, segment, next earnings, View Details.
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import ITBearNav from './ITBearNav'
import { fmtNum, fmtPct, daysUntil, earningsDaysColor } from '../../utils/format'

const API_BASE = ''

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-7 h-7 border-2 border-slate-600 border-t-slate-300 rounded-full animate-spin" />
      <p className="text-slate-500 text-sm ml-3">Loading universe…</p>
    </div>
  )
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center my-6">
      <p className="text-red-400 text-sm mb-3">{message}</p>
      <button
        onClick={onRetry}
        className="px-4 py-2 text-xs font-medium rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors"
      >
        Retry
      </button>
    </div>
  )
}

function TierBadge({ tier }) {
  const cfg = {
    mega_cap: 'bg-purple-500/20 border-purple-500/30 text-purple-300',
    mid_cap: 'bg-blue-500/20 border-blue-500/30 text-blue-300',
    index: 'bg-slate-700 border-slate-600 text-slate-400',
  }
  const label = {
    mega_cap: 'Mega Cap',
    mid_cap: 'Mid Cap',
    index: 'Index',
  }
  const cls = cfg[tier] ?? cfg.index
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cls}`}>
      {label[tier] ?? tier}
    </span>
  )
}

function StockRow({ stock, onViewDetails }) {
  const chg = stock.change_1d ?? 0
  const chgCls = chg > 0 ? 'text-emerald-400' : chg < 0 ? 'text-red-400' : 'text-slate-400'
  const days = daysUntil(stock.next_earnings_date)
  const daysColor = earningsDaysColor(days)

  return (
    <tr className="border-b border-slate-700/40 last:border-0 hover:bg-slate-700/20 transition-colors">
      {/* Flag + Symbol + Name */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-base shrink-0">{stock.country === 'US' ? '🇺🇸' : '🇮🇳'}</span>
          <div>
            <p className="text-sm font-bold text-white">{stock.symbol}</p>
            <p className="text-[10px] text-slate-500 hidden sm:block">{stock.name}</p>
          </div>
        </div>
      </td>

      {/* Price + 1d change */}
      <td className="px-3 py-3 text-right tabular-nums">
        <p className="text-sm text-white font-medium">
          {stock.country === 'US'
            ? `$${fmtNum(stock.price, 2)}`
            : `₹${fmtNum(stock.price, 2)}`
          }
        </p>
        <p className={`text-[11px] tabular-nums ${chgCls}`}>{fmtPct(chg, 2)}</p>
      </td>

      {/* Tier */}
      <td className="px-3 py-3 hidden sm:table-cell">
        <TierBadge tier={stock.tier} />
      </td>

      {/* Segment */}
      <td className="px-3 py-3 hidden md:table-cell">
        <span className="text-[10px] text-slate-400">{stock.segment ?? '—'}</span>
      </td>

      {/* Next earnings */}
      <td className="px-3 py-3 text-right hidden lg:table-cell tabular-nums">
        <p className="text-xs text-slate-300">{stock.next_earnings_date ?? '—'}</p>
        {days !== null && (
          <p className={`text-[10px] ${daysColor}`}>
            {days === 0 ? 'Today' : days < 0 ? 'Past' : `${days}d away`}
          </p>
        )}
      </td>

      {/* View details */}
      <td className="px-4 py-3 text-right">
        <button
          onClick={() => onViewDetails(stock.symbol)}
          className="px-3 py-1 text-[11px] font-medium rounded-lg border bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600 hover:text-white transition-colors"
        >
          Details
        </button>
      </td>
    </tr>
  )
}

const COUNTRY_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'IN', label: 'India' },
  { id: 'US', label: 'US' },
]

const SORT_OPTIONS = [
  { id: 'symbol', label: 'Symbol' },
  { id: 'change_1d', label: '1D Change' },
  { id: 'price', label: 'Price' },
  { id: 'next_earnings', label: 'Next Earnings' },
]

export default function ITUniverse() {
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [countryFilter, setCountryFilter] = useState('all')
  const [sortBy, setSortBy] = useState('change_1d')
  const navigate = useNavigate()

  const fetchUniverse = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/it-bear/universe`)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const json = await res.json()
      setStocks(Array.isArray(json) ? json : json.stocks ?? [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchUniverse() }, [fetchUniverse])

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(fetchUniverse, 30000)
    return () => clearInterval(id)
  }, [fetchUniverse])

  function handleViewDetails(symbol) {
    navigate(`/it-bear/stock/${symbol}`)
  }

  const filtered = stocks.filter(s => {
    if (countryFilter === 'all') return true
    return s.country === countryFilter
  })

  const sorted = [...filtered].sort((a, b) => {
    switch (sortBy) {
      case 'symbol':
        return a.symbol.localeCompare(b.symbol)
      case 'change_1d':
        return (a.change_1d ?? 0) - (b.change_1d ?? 0) // weakest first
      case 'price':
        return (b.price ?? 0) - (a.price ?? 0)
      case 'next_earnings': {
        const da = daysUntil(a.next_earnings_date) ?? 9999
        const db = daysUntil(b.next_earnings_date) ?? 9999
        return da - db
      }
      default:
        return 0
    }
  })

  const indiaCount = stocks.filter(s => s.country === 'IN').length
  const usCount = stocks.filter(s => s.country === 'US').length

  return (
    <div>
      <ITBearNav />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

        <div className="flex items-start justify-between mb-5">
          <div>
            <h1 className="text-2xl font-black text-white">IT Universe</h1>
            <p className="text-slate-500 text-xs mt-1">
              {indiaCount} India stocks + {usCount} US stocks | IT services watchlist
            </p>
          </div>
        </div>

        {/* Filters + Sort */}
        <div className="flex flex-wrap items-center gap-2 mb-5">
          <div className="flex items-center gap-1">
            {COUNTRY_FILTERS.map(f => (
              <button
                key={f.id}
                onClick={() => setCountryFilter(f.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                  countryFilter === f.id
                    ? 'bg-red-500/20 border-red-500/30 text-red-300'
                    : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-[10px] text-slate-500">Sort:</span>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              className="py-1 px-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-red-500/50 transition-colors"
            >
              {SORT_OPTIONS.map(o => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {loading && <Spinner />}
        {!loading && error && <ErrorState message={error} onRetry={fetchUniverse} />}

        {!loading && !error && (
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              {sorted.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-slate-400 text-sm">No stocks found.</p>
                  <p className="text-slate-600 text-xs mt-1">Backend universe endpoint may not have data yet.</p>
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="text-[10px] text-slate-500 uppercase border-b border-slate-700 bg-slate-900/40">
                      <th className="px-4 py-2.5 text-left">Symbol / Name</th>
                      <th className="px-3 py-2.5 text-right">Price / 1D</th>
                      <th className="px-3 py-2.5 text-left hidden sm:table-cell">Tier</th>
                      <th className="px-3 py-2.5 text-left hidden md:table-cell">Segment</th>
                      <th className="px-3 py-2.5 text-right hidden lg:table-cell">Next Earnings</th>
                      <th className="px-4 py-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map(stock => (
                      <StockRow
                        key={stock.symbol}
                        stock={stock}
                        onViewDetails={handleViewDetails}
                      />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
