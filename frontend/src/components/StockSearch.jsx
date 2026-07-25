/**
 * StockSearch — autocomplete search input for any NSE stock.
 * Lives in the navigation bar. On selection, navigates to /stock/:symbol.
 */

import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const API_BASE = ''

export default function StockSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const wrapperRef = useRef(null)
  const timerRef = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function handleChange(e) {
    const val = e.target.value
    setQuery(val)

    if (timerRef.current) clearTimeout(timerRef.current)

    if (val.trim().length < 1) {
      setResults([])
      setOpen(false)
      return
    }

    timerRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetch(`${API_BASE}/api/search/stocks?q=${encodeURIComponent(val.trim())}`)
        if (res.ok) {
          const data = await res.json()
          setResults(data)
          setOpen(data.length > 0)
        }
      } catch {
        // silent
      } finally {
        setLoading(false)
      }
    }, 300)
  }

  function handleSelect(symbol) {
    setQuery('')
    setResults([])
    setOpen(false)
    navigate(`/stock/${symbol}`)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && query.trim().length >= 1) {
      // Navigate directly if user hits Enter
      setOpen(false)
      navigate(`/stock/${query.trim().toUpperCase()}`)
      setQuery('')
    }
    if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Search any stock…"
          className="w-48 sm:w-56 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700
                     text-sm text-slate-200 placeholder-slate-500 focus:outline-none
                     focus:border-slate-500 transition-colors"
        />
        {loading && (
          <span className="text-slate-500 text-xs animate-spin">↻</span>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-slate-800 border border-slate-700
                        rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto">
          {results.map((item) => (
            <button
              key={item.symbol}
              onClick={() => handleSelect(item.symbol)}
              className="w-full text-left px-3 py-2 hover:bg-slate-700 transition-colors
                         border-b border-slate-700/50 last:border-b-0"
            >
              <span className="text-sm font-semibold text-white">{item.symbol}</span>
              {item.name && (
                <span className="text-xs text-slate-400 ml-2 truncate">{item.name}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
