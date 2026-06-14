/**
 * StatusBadge — pill with a colored dot (DQH style).
 * tone: success | danger | warning | info | neutral | brand
 */
const TONES = {
  success: { dot: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-300', bg: 'bg-emerald-500/10 border-emerald-500/25' },
  danger:  { dot: 'bg-red-500',     text: 'text-red-600 dark:text-red-300',         bg: 'bg-red-500/10 border-red-500/25' },
  warning: { dot: 'bg-amber-500',   text: 'text-amber-600 dark:text-amber-300',     bg: 'bg-amber-500/10 border-amber-500/25' },
  info:    { dot: 'bg-blue-500',    text: 'text-blue-600 dark:text-blue-300',       bg: 'bg-blue-500/10 border-blue-500/25' },
  neutral: { dot: 'bg-slate-400',   text: 'text-ink-muted',                          bg: 'bg-surface-2 border-edge' },
  brand:   { dot: 'bg-brand',       text: 'text-brand',                              bg: 'bg-brand-soft border-brand/25' },
}

// Map common verdict words → tone
const VERDICT_TONE = {
  buy: 'success', 'strong buy': 'success', bullish: 'success', pass: 'success', open: 'success',
  sell: 'danger', 'strong sell': 'danger', bearish: 'danger', fail: 'danger', stopped_out: 'danger',
  hold: 'warning', neutral: 'warning', pending: 'warning',
}

export function StatusBadge({ label, tone, dot = true, className = '' }) {
  const resolvedTone = tone ?? VERDICT_TONE[String(label).toLowerCase()] ?? 'neutral'
  const t = TONES[resolvedTone] ?? TONES.neutral
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold ${t.bg} ${t.text} ${className}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />}
      {label}
    </span>
  )
}
