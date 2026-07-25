/**
 * ITBearNav — secondary navigation shown on all /it-bear/* pages.
 */
import { NavLink } from 'react-router-dom'

const SUB_LINKS = [
  { to: '/it-bear', label: 'Dashboard', end: true },
  { to: '/it-bear/earnings', label: 'Earnings' },
  { to: '/it-bear/universe', label: 'Universe' },
  { to: '/it-bear/scanner', label: 'Scanner' },
  { to: '/it-bear/us-signals', label: 'US Signals' },
  { to: '/it-bear/notifications', label: 'Notifications' },
]

export default function ITBearNav() {
  const linkClass = ({ isActive }) =>
    `px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
      isActive
        ? 'bg-red-500/20 border border-red-500/30 text-red-300'
        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
    }`

  return (
    <div className="border-b border-slate-800 bg-slate-900/60 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-1.5 flex items-center gap-1 overflow-x-auto">
        <span className="text-[10px] font-bold text-red-400 uppercase tracking-wider shrink-0 mr-2 border border-red-500/30 bg-red-500/10 px-2 py-1 rounded">
          IT BEAR
        </span>
        {SUB_LINKS.map(({ to, label, end }) => (
          <NavLink key={to} to={to} end={end} className={linkClass}>
            {label}
          </NavLink>
        ))}
      </div>
    </div>
  )
}
