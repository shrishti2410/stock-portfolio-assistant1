/**
 * PageHeader — title + icon + subtitle on the left, actions on the right.
 * Optional breadcrumb above the title.
 */
import { Link } from 'react-router-dom'

export function PageHeader({ title, subtitle, icon: Icon, actions, breadcrumb }) {
  return (
    <div className="mb-6">
      {breadcrumb && breadcrumb.length > 0 && (
        <nav className="flex items-center gap-1.5 text-xs text-ink-subtle mb-1.5">
          {breadcrumb.map((b, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {b.to ? (
                <Link to={b.to} className="hover:text-ink transition-colors">{b.label}</Link>
              ) : (
                <span className="text-ink-muted">{b.label}</span>
              )}
              {i < breadcrumb.length - 1 && <span className="text-edge-strong">/</span>}
            </span>
          ))}
        </nav>
      )}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="w-9 h-9 rounded-lg bg-brand-soft flex items-center justify-center shrink-0">
              <Icon className="w-5 h-5 text-brand" />
            </div>
          )}
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-ink">{title}</h1>
            {subtitle && <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>}
          </div>
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  )
}
