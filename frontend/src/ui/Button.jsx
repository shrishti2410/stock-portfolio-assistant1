/**
 * Button — variant-driven, matches DQH (blue primary, ghost, danger, success).
 */
const VARIANTS = {
  primary: 'bg-brand text-white hover:bg-blue-600 border border-transparent',
  secondary: 'bg-surface-2 text-ink border border-edge hover:border-edge-strong',
  ghost: 'bg-transparent text-ink-muted border border-transparent hover:bg-surface-2 hover:text-ink',
  danger: 'bg-red-500/15 text-red-500 dark:text-red-300 border border-red-500/30 hover:bg-red-500/25',
  success: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25',
  outline: 'bg-transparent text-brand border border-brand/40 hover:bg-brand-soft',
}

const SIZES = {
  sm: 'px-2.5 py-1 text-xs',
  md: 'px-3.5 py-2 text-sm',
  lg: 'px-5 py-2.5 text-sm',
}

export function Button({
  children, variant = 'primary', size = 'md', className = '',
  icon: Icon, loading = false, disabled = false, ...rest
}) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium
        transition-colors disabled:opacity-50 disabled:cursor-not-allowed
        ${VARIANTS[variant] ?? VARIANTS.primary} ${SIZES[size] ?? SIZES.md} ${className}`}
      {...rest}
    >
      {loading
        ? <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
        : Icon && <Icon className="w-4 h-4" />}
      {children}
    </button>
  )
}
