/**
 * Tabs — sub-navigation within a section. Controlled.
 * tabs: [{ id, label, count? }]
 */
export function Tabs({ tabs, active, onChange, className = '' }) {
  return (
    <div className={`flex items-center gap-1 border-b border-edge ${className}`}>
      {tabs.map(tab => {
        const isActive = tab.id === active
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`relative px-3.5 py-2.5 text-sm font-medium transition-colors -mb-px
              ${isActive
                ? 'text-brand border-b-2 border-brand'
                : 'text-ink-muted border-b-2 border-transparent hover:text-ink'}`}
          >
            {tab.label}
            {tab.count !== undefined && tab.count !== null && (
              <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full tnum
                ${isActive ? 'bg-brand-soft text-brand' : 'bg-surface-2 text-ink-subtle'}`}>
                {tab.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/** Segmented pill toggle (e.g. All / India / US filters). */
export function SegmentedControl({ options, value, onChange, className = '' }) {
  return (
    <div className={`inline-flex items-center gap-1 p-1 bg-surface-2 border border-edge rounded-lg ${className}`}>
      {options.map(opt => {
        const val = typeof opt === 'string' ? opt : opt.value
        const label = typeof opt === 'string' ? opt : opt.label
        const isActive = val === value
        return (
          <button
            key={val}
            onClick={() => onChange(val)}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors
              ${isActive ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink'}`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
