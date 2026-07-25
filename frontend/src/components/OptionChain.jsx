/**
 * OptionChain — NSE option chain viewer for stocks and indices.
 */

import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'

const API_BASE = ''

function fmt(n) {
  if (n === undefined || n === null) return '—'
  return new Intl.NumberFormat('en-IN').format(n)
}

export default function OptionChain() {
  const [searchParams, setSearchParams] = useSearchParams()
  const symbol = searchParams.get('symbol') || 'NIFTY'

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [symbols, setSymbols] = useState([])
  const [selectedExpiry, setSelectedExpiry] = useState('')
  const [inputSymbol, setInputSymbol] = useState(symbol)

  // Load available symbols
  useEffect(() => {
    fetch(`${API_BASE}/api/options/symbols`)
      .then(r => r.json()).then(setSymbols).catch(() => {})
  }, [])

  // Fetch option chain
  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const res = await fetch(`${API_BASE}/api/options/${symbol}`)
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail ?? `Error ${res.status}`)
        }
        const d = await res.json()
        setData(d)
        if (d.expiry_dates?.length > 0 && !selectedExpiry) {
          setSelectedExpiry(d.expiry_dates[0])
        }
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [symbol])

  function handleSearch() {
    const s = inputSymbol.trim().toUpperCase()
    if (s) setSearchParams({ symbol: s })
  }

  // Filter strikes by selected expiry
  const filteredStrikes = data?.strikes?.filter(
    s => !selectedExpiry || s.expiryDate === selectedExpiry
  ) ?? []

  // Find ATM strike (closest to spot)
  const spot = data?.spot_price ?? 0
  const atmStrike = filteredStrikes.reduce((closest, s) => {
    return Math.abs(s.strikePrice - spot) < Math.abs(closest - spot) ? s.strikePrice : closest
  }, 0)

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-white">Option Chain</h1>
          <p className="text-xs text-slate-500">NSE derivatives — Call & Put options</p>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick symbol buttons */}
          {['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS'].map(s => (
            <button
              key={s}
              onClick={() => { setInputSymbol(s); setSearchParams({ symbol: s }); setSelectedExpiry('') }}
              className={`px-2 py-1 rounded text-xs font-medium border transition-colors ${
                symbol === s
                  ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                  : 'bg-slate-700 border-slate-600 text-slate-400 hover:text-slate-300'
              }`}
            >
              {s}
            </button>
          ))}

          <input
            type="text"
            value={inputSymbol}
            onChange={e => setInputSymbol(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="Symbol…"
            className="w-28 px-2 py-1 rounded-lg bg-slate-800 border border-slate-700
                       text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
          />
          <button onClick={handleSearch}
                  className="px-2 py-1 rounded-lg text-xs font-medium border bg-slate-700
                             border-slate-600 text-slate-300 hover:bg-slate-600">
            Go
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {loading ? (
        <p className="text-slate-500 text-sm animate-pulse py-8 text-center">Loading option chain…</p>
      ) : data ? (
        <>
          {/* Summary bar */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
            <div className="bg-slate-800/80 border border-slate-700 rounded-lg p-3">
              <p className="text-[10px] text-slate-500">Spot Price</p>
              <p className="text-lg font-bold text-white">₹{fmt(data.spot_price)}</p>
            </div>
            <div className="bg-slate-800/80 border border-slate-700 rounded-lg p-3">
              <p className="text-[10px] text-slate-500">Total CE OI</p>
              <p className="text-sm font-semibold text-emerald-400">{fmt(data.total_ce_oi)}</p>
            </div>
            <div className="bg-slate-800/80 border border-slate-700 rounded-lg p-3">
              <p className="text-[10px] text-slate-500">Total PE OI</p>
              <p className="text-sm font-semibold text-red-400">{fmt(data.total_pe_oi)}</p>
            </div>
            <div className="bg-slate-800/80 border border-slate-700 rounded-lg p-3">
              <p className="text-[10px] text-slate-500">PCR (Put/Call)</p>
              <p className={`text-sm font-semibold ${data.pcr > 1 ? 'text-emerald-400' : 'text-red-400'}`}>
                {data.pcr}
              </p>
            </div>
            <div className="bg-slate-800/80 border border-slate-700 rounded-lg p-3">
              <p className="text-[10px] text-slate-500">Strikes</p>
              <p className="text-sm font-semibold text-slate-300">{filteredStrikes.length}</p>
            </div>
          </div>

          {/* Expiry selector */}
          {data.expiry_dates?.length > 0 && (
            <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
              <span className="text-xs text-slate-500 shrink-0">Expiry:</span>
              {data.expiry_dates.slice(0, 6).map(exp => (
                <button
                  key={exp}
                  onClick={() => setSelectedExpiry(exp)}
                  className={`px-2 py-1 rounded text-[10px] font-medium border whitespace-nowrap transition-colors ${
                    selectedExpiry === exp
                      ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                      : 'bg-slate-700 border-slate-600 text-slate-400 hover:text-slate-300'
                  }`}
                >
                  {exp}
                </button>
              ))}
            </div>
          )}

          {/* Option chain table */}
          <div className="bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th colSpan={5} className="px-2 py-2 text-emerald-400 text-center bg-emerald-500/5 border-r border-slate-600">
                      CALLS (CE)
                    </th>
                    <th className="px-3 py-2 text-slate-300 text-center bg-slate-700/50">Strike</th>
                    <th colSpan={5} className="px-2 py-2 text-red-400 text-center bg-red-500/5 border-l border-slate-600">
                      PUTS (PE)
                    </th>
                  </tr>
                  <tr className="border-b border-slate-700 text-[10px] text-slate-500 uppercase">
                    <th className="px-2 py-1.5 text-right">OI</th>
                    <th className="px-2 py-1.5 text-right">Chg OI</th>
                    <th className="px-2 py-1.5 text-right">Vol</th>
                    <th className="px-2 py-1.5 text-right">IV</th>
                    <th className="px-2 py-1.5 text-right border-r border-slate-600">LTP</th>
                    <th className="px-3 py-1.5 text-center bg-slate-700/30">Price</th>
                    <th className="px-2 py-1.5 text-right border-l border-slate-600">LTP</th>
                    <th className="px-2 py-1.5 text-right">IV</th>
                    <th className="px-2 py-1.5 text-right">Vol</th>
                    <th className="px-2 py-1.5 text-right">Chg OI</th>
                    <th className="px-2 py-1.5 text-right">OI</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStrikes.map((s, i) => {
                    const isATM = s.strikePrice === atmStrike
                    const isITM_CE = s.strikePrice < spot
                    const isITM_PE = s.strikePrice > spot
                    const ce = s.CE || {}
                    const pe = s.PE || {}

                    return (
                      <tr
                        key={`${s.strikePrice}-${i}`}
                        className={`border-b border-slate-700/30 ${
                          isATM ? 'bg-amber-500/10 font-semibold' : ''
                        } ${i % 2 === 0 ? '' : 'bg-slate-700/10'}`}
                      >
                        {/* CE side */}
                        <td className={`px-2 py-1.5 text-right tabular-nums ${isITM_CE ? 'bg-emerald-500/5' : ''}`}>
                          {fmt(ce.oi)}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums ${
                          (ce.changeInOI || 0) > 0 ? 'text-emerald-400' : (ce.changeInOI || 0) < 0 ? 'text-red-400' : 'text-slate-400'
                        } ${isITM_CE ? 'bg-emerald-500/5' : ''}`}>
                          {fmt(ce.changeInOI)}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums text-slate-400 ${isITM_CE ? 'bg-emerald-500/5' : ''}`}>
                          {fmt(ce.volume)}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums text-slate-400 ${isITM_CE ? 'bg-emerald-500/5' : ''}`}>
                          {ce.iv || '—'}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums font-medium border-r border-slate-600 ${
                          isITM_CE ? 'text-emerald-300 bg-emerald-500/5' : 'text-slate-200'
                        }`}>
                          {ce.ltp || '—'}
                        </td>

                        {/* Strike */}
                        <td className={`px-3 py-1.5 text-center tabular-nums font-bold bg-slate-700/30 ${
                          isATM ? 'text-amber-300' : 'text-slate-200'
                        }`}>
                          {fmt(s.strikePrice)}
                        </td>

                        {/* PE side */}
                        <td className={`px-2 py-1.5 text-right tabular-nums font-medium border-l border-slate-600 ${
                          isITM_PE ? 'text-red-300 bg-red-500/5' : 'text-slate-200'
                        }`}>
                          {pe.ltp || '—'}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums text-slate-400 ${isITM_PE ? 'bg-red-500/5' : ''}`}>
                          {pe.iv || '—'}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums text-slate-400 ${isITM_PE ? 'bg-red-500/5' : ''}`}>
                          {fmt(pe.volume)}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums ${
                          (pe.changeInOI || 0) > 0 ? 'text-red-400' : (pe.changeInOI || 0) < 0 ? 'text-emerald-400' : 'text-slate-400'
                        } ${isITM_PE ? 'bg-red-500/5' : ''}`}>
                          {fmt(pe.changeInOI)}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums ${isITM_PE ? 'bg-red-500/5' : ''}`}>
                          {fmt(pe.oi)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </main>
  )
}
