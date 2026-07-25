/**
 * Loading / Empty / Error state components (DQH style).
 */
export function LoadingSpinner({ message = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center justify-center py-16 ${className}`}>
      <div className="w-7 h-7 border-2 border-edge border-t-brand rounded-full animate-spin" />
      {message && <p className="text-ink-muted text-sm ml-3">{message}</p>}
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', description, icon: Icon, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center py-16 px-4 ${className}`}>
      {Icon && (
        <div className="w-12 h-12 rounded-xl bg-surface-2 border border-edge flex items-center justify-center mb-3">
          <Icon className="w-6 h-6 text-ink-subtle" />
        </div>
      )}
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description && <p className="text-xs text-ink-muted mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ message = 'Something went wrong', onRetry, className = '' }) {
  return (
    <div className={`bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center my-4 ${className}`}>
      <p className="text-red-500 dark:text-red-400 text-sm mb-3">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-xs font-medium rounded-lg bg-red-500/20 border border-red-500/30 text-red-500 dark:text-red-300 hover:bg-red-500/30 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}
