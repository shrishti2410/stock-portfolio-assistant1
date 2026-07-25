/**
 * Sidebar — dark left navigation (DQH style).
 * Sectioned: Workspace / Thesis / Reference, with brand header + footer controls.
 */
import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  IconPortfolio, IconStrategy, IconBacktest, IconTrading, IconSignal,
  IconBear, IconMarkets, IconSettings, IconSun, IconMoon, IconLogout,
} from '../ui/icons'
import { useAuth } from './useAuth'

const API_BASE = ''

const SECTIONS = [
  {
    label: 'Workspace',
    items: [
      { to: '/portfolio', label: 'Portfolio', icon: IconPortfolio, match: ['/portfolio', '/', '/stock', '/history'] },
      { to: '/strategies', label: 'Strategies', icon: IconStrategy, match: ['/strategies', '/fo-strategies'] },
      { to: '/backtest', label: 'Backtest', icon: IconBacktest, match: ['/backtest'] },
      { to: '/trading', label: 'Trading', icon: IconTrading, match: ['/trading'], engineDot: true },
      { to: '/signals', label: 'Signals', icon: IconSignal, match: ['/signals', '/alerts'] },
    ],
  },
  {
    label: 'Thesis',
    items: [
      { to: '/it-bear', label: 'IT-Bear', icon: IconBear, match: ['/it-bear'], redDot: true },
    ],
  },
  {
    label: 'Reference',
    items: [
      { to: '/markets', label: 'Markets', icon: IconMarkets, match: ['/markets', '/options', '/mcx'] },
      { to: '/settings', label: 'Settings', icon: IconSettings, match: ['/settings', '/glossary'] },
    ],
  },
]

function useEngineStatus() {
  const [running, setRunning] = useState(false)
  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/trading/status`)
        if (res.ok && !cancelled) setRunning((await res.json()).running ?? false)
      } catch { /* backend may be down */ }
    }
    check()
    const id = setInterval(check, 30000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])
  return running
}

function NavItem({ item, engineRunning, onNavigate }) {
  const location = useLocation()
  const active = item.match.some(m =>
    m === '/' ? location.pathname === '/' : location.pathname.startsWith(m)
  )
  const Icon = item.icon

  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors group
        ${active
          ? 'bg-brand/15 text-blue-300'
          : 'text-slate-400 hover:text-slate-100 hover:bg-white/5'}`}
    >
      <Icon className="w-[18px] h-[18px] shrink-0" />
      <span className="flex-1">{item.label}</span>
      {item.engineDot && engineRunning && (
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" title="Engine running" />
      )}
      {item.redDot && (
        <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
      )}
    </NavLink>
  )
}

function UserBlock() {
  const { user, logout } = useAuth()
  if (!user) return null

  const initial = (user.display_name || user.username || '?').charAt(0).toUpperCase()

  return (
    <div className="px-4 py-3 border-b border-white/5 flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center shrink-0">
        <span className="text-xs font-bold text-slate-200">{initial}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="text-xs font-semibold text-slate-100 truncate">{user.display_name || user.username}</p>
          {user.is_admin && (
            <span className="shrink-0 text-[9px] px-1.5 py-0.5 rounded-full bg-brand/20 text-blue-300 font-semibold">
              Admin
            </span>
          )}
        </div>
        <p className="text-[10px] text-slate-500 truncate">@{user.username}</p>
      </div>
      <button
        onClick={logout}
        title="Log out"
        aria-label="Log out"
        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors shrink-0"
      >
        <IconLogout className="w-4 h-4" />
      </button>
    </div>
  )
}

export function Sidebar({ theme, onToggleTheme, mobileOpen, onClose }) {
  const engineRunning = useEngineStatus()

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={onClose} />
      )}

      <aside
        className={`bg-sidebar text-sidebar-ink border-r border-white/5 flex flex-col
          w-60 shrink-0 z-40
          fixed inset-y-0 left-0 transition-transform lg:translate-x-0 lg:static
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Brand */}
        <div className="px-4 py-4 border-b border-white/5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand flex items-center justify-center shrink-0">
              <span className="text-white font-bold text-sm">TD</span>
            </div>
            <div>
              <p className="text-sm font-bold text-white leading-tight">Trading Desk</p>
              <p className="text-[10px] text-slate-500">India + US markets</p>
            </div>
          </div>
        </div>

        <UserBlock />

        {/* Nav sections */}
        <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-5">
          {SECTIONS.map(section => (
            <div key={section.label}>
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                {section.label}
              </p>
              <div className="space-y-0.5">
                {section.items.map(item => (
                  <NavItem key={item.to} item={item} engineRunning={engineRunning} onNavigate={onClose} />
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-3 py-3 border-t border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
            <span className={`w-1.5 h-1.5 rounded-full ${engineRunning ? 'bg-emerald-400' : 'bg-slate-600'}`} />
            Engine {engineRunning ? 'on' : 'off'}
          </div>
          <button
            onClick={onToggleTheme}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
            title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
          >
            {theme === 'dark' ? <IconSun className="w-4 h-4" /> : <IconMoon className="w-4 h-4" />}
          </button>
        </div>
      </aside>
    </>
  )
}
