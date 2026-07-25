/**
 * HubCard — a clickable navigation card used on section hub pages.
 * Icon square + title + description + animated arrow.
 */
import { Link } from 'react-router-dom'

export function HubCard({ to, icon: Icon, title, description, tone = 'brand', badge, disabled }) {
  const tones = {
    brand:   'bg-brand-soft text-brand',
    emerald: 'bg-emerald-500/15 text-emerald-500 dark:text-emerald-400',
    amber:   'bg-amber-500/15 text-amber-500 dark:text-amber-400',
    red:     'bg-red-500/15 text-red-500 dark:text-red-400',
    purple:  'bg-purple-500/15 text-purple-500 dark:text-purple-400',
    slate:   'bg-surface-2 text-ink-muted',
  }

  const inner = (
    <>
      <div className="flex items-start justify-between">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${tones[tone] ?? tones.brand}`}>
          {Icon && <Icon className="w-5 h-5" />}
        </div>
        {badge && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-2 border border-edge text-ink-muted">
            {badge}
          </span>
        )}
      </div>
      <div className="mt-3">
        <div className="flex items-center gap-1.5">
          <p className="text-sm font-semibold text-ink">{title}</p>
          {!disabled && (
            <span className="text-ink-subtle group-hover:translate-x-0.5 transition-transform">→</span>
          )}
        </div>
        <p className="text-xs text-ink-muted mt-1 leading-relaxed">{description}</p>
      </div>
    </>
  )

  if (disabled) {
    return (
      <div className="bg-surface border border-edge rounded-xl p-4 opacity-50 cursor-not-allowed">
        {inner}
      </div>
    )
  }

  return (
    <Link
      to={to}
      className="group bg-surface border border-edge rounded-xl p-4 block
                 transition-all duration-200 hover:shadow-md hover:border-edge-strong"
    >
      {inner}
    </Link>
  )
}
