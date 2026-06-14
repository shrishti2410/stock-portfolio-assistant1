/**
 * Card — the base surface used across all pages (DQH style).
 * Surface bg, edge border, rounded-xl, subtle hover lift when `hover`.
 */
export function Card({ children, className = '', hover = false, padding = 'p-5', ...rest }) {
  return (
    <div
      className={`bg-surface border border-edge rounded-xl ${padding}
        ${hover ? 'transition-all duration-200 hover:shadow-md hover:border-edge-strong' : ''}
        ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action, className = '' }) {
  return (
    <div className={`flex items-start justify-between gap-3 mb-4 pb-3 border-b border-edge ${className}`}>
      <div>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {subtitle && <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

/** A small uppercase section label used in sidebars + groupings. */
export function SectionLabel({ children, className = '' }) {
  return (
    <p className={`text-[10px] font-semibold uppercase tracking-wider text-ink-subtle ${className}`}>
      {children}
    </p>
  )
}
