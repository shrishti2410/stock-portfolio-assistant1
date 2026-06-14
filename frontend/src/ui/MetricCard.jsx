/**
 * MetricCard — KPI tile (DQH style).
 * Large mono number, label, optional delta badge + sub text.
 * variant: default | success | danger | warning | brand
 */
const VARIANTS = {
  default: 'bg-surface border-edge',
  success: 'bg-emerald-500/5 border-emerald-500/20',
  danger:  'bg-red-500/5 border-red-500/20',
  warning: 'bg-amber-500/5 border-amber-500/20',
  brand:   'bg-brand-soft border-brand/20',
}

const VALUE_COLOR = {
  default: 'text-ink',
  success: 'text-emerald-600 dark:text-emerald-400',
  danger:  'text-red-600 dark:text-red-400',
  warning: 'text-amber-600 dark:text-amber-400',
  brand:   'text-brand',
}

export function MetricCard({ label, value, sub, delta, variant = 'default', icon: Icon, className = '' }) {
  const deltaPositive = typeof delta === 'number' ? delta >= 0 : null
  return (
    <div className={`rounded-xl border p-4 transition-all duration-200 hover:shadow-md ${VARIANTS[variant] ?? VARIANTS.default} ${className}`}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] font-medium uppercase tracking-wide text-ink-subtle">{label}</p>
        {Icon && <Icon className="w-3.5 h-3.5 text-ink-subtle" />}
      </div>
      <p className={`text-2xl font-bold tnum leading-tight ${VALUE_COLOR[variant] ?? VALUE_COLOR.default}`}
         style={{ fontFamily: 'var(--font-mono)' }}>
        {value ?? '—'}
      </p>
      <div className="flex items-center gap-2 mt-1">
        {delta !== undefined && delta !== null && (
          <span className={`text-[10px] font-semibold tnum ${deltaPositive ? 'text-emerald-500' : 'text-red-500'}`}>
            {deltaPositive ? '▲' : '▼'} {typeof delta === 'number' ? `${Math.abs(delta).toFixed(1)}%` : delta}
          </span>
        )}
        {sub && <p className="text-[10px] text-ink-muted">{sub}</p>}
      </div>
    </div>
  )
}
