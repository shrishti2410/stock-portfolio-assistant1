/**
 * Shared formatting utilities used across the app.
 */

export function fmtINR(n) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n)
}

export function fmtUSD(n) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(n)
}

export function fmtNum(n, decimals = 2) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: decimals }).format(n)
}

export function fmtPct(n, decimals = 2) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${fmtNum(n, decimals)}%`
}

export function pnlColor(val) {
  if (val > 0) return 'text-emerald-400'
  if (val < 0) return 'text-red-400'
  return 'text-slate-400'
}

export function pctColor(val) {
  if (val > 0) return 'text-emerald-400'
  if (val < 0) return 'text-red-400'
  return 'text-slate-400'
}

/**
 * Returns number of calendar days between now and a future date string.
 * Negative if in the past.
 */
export function daysUntil(dateStr) {
  if (!dateStr) return null
  const target = new Date(dateStr)
  const now = new Date()
  // zero out time for day-level comparison
  target.setHours(0, 0, 0, 0)
  now.setHours(0, 0, 0, 0)
  return Math.round((target - now) / (1000 * 60 * 60 * 24))
}

/**
 * Colour class for earnings countdown badge.
 */
export function earningsDaysColor(days) {
  if (days === null || days === undefined) return 'text-slate-400'
  if (days < 3) return 'text-red-400'
  if (days < 7) return 'text-amber-400'
  if (days <= 21) return 'text-emerald-400'
  return 'text-slate-400'
}

/**
 * Border class for rows within the 7-21 day pre-earnings sweet spot.
 */
export function earningsSweetSpotBorder(days) {
  if (days !== null && days >= 7 && days <= 21) return 'border-amber-500/40'
  return 'border-slate-700/50'
}
