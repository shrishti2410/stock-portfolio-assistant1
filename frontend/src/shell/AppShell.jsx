/**
 * AppShell — overall layout: dark sidebar + scrollable content area with a
 * slim top bar (mobile menu button + global stock search).
 */
import { useState } from 'react'
import { Sidebar } from './Sidebar'
import { useTheme } from './useTheme'
import StockSearch from '../components/StockSearch'

function MenuButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="lg:hidden p-2 rounded-lg text-ink-muted hover:text-ink hover:bg-surface-2 transition-colors"
      aria-label="Open menu"
    >
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path d="M3 12h18M3 6h18M3 18h18" strokeLinecap="round" />
      </svg>
    </button>
  )
}

export function AppShell({ children }) {
  const [theme, toggleTheme] = useTheme()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-app text-ink">
      <Sidebar
        theme={theme}
        onToggleTheme={toggleTheme}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 px-4 sm:px-6 py-2.5
                           bg-app/80 backdrop-blur border-b border-edge">
          <MenuButton onClick={() => setMobileOpen(true)} />
          <div className="flex-1" />
          <StockSearch />
        </header>

        {/* Page content */}
        <main className="flex-1 min-w-0">
          {children}
        </main>
      </div>
    </div>
  )
}
