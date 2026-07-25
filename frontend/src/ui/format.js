// Shared formatting helpers for the UI kit.

export function fmtINR(n, decimals = 0) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: decimals,
  }).format(n)
}

export function fmtUSD(n, decimals = 2) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: decimals,
  }).format(n)
}

export function fmtMoney(n, currency = 'INR', decimals = 0) {
  return currency === 'USD' ? fmtUSD(n, decimals) : fmtINR(n, decimals)
}

export function fmtNum(n, decimals = 2) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: decimals }).format(n)
}

export function fmtPct(n, decimals = 1) {
  if (n === undefined || n === null || isNaN(n)) return '—'
  const v = Number(n)
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`
}

export function pnlColor(v) {
  if (v > 0) return 'text-emerald-500 dark:text-emerald-400'
  if (v < 0) return 'text-red-500 dark:text-red-400'
  return 'text-ink-muted'
}

export function pctColor(v) {
  return pnlColor(v)
}

export function daysUntil(dateStr) {
  if (!dateStr) return null
  try {
    const target = new Date(dateStr)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    target.setHours(0, 0, 0, 0)
    return Math.round((target - today) / 86400000)
  } catch {
    return null
  }
}
