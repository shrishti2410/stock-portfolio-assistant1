import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Dashboard from './components/Dashboard'
import StockAnalysis from './components/StockAnalysis'
import StrategyList from './components/StrategyList'
import StrategyBuilder from './components/StrategyBuilder'
import AlertsPanel from './components/AlertsPanel'
import AnalysisHistory from './components/AnalysisHistory'
import IndicatorGlossary from './components/IndicatorGlossary'
import OptionChain from './components/OptionChain'
import MCXCommodities from './components/MCXCommodities'
import PredefinedStrategies from './components/PredefinedStrategies'
import StockSearch from './components/StockSearch'
import TradingDashboard from './components/trading/TradingDashboard'
import TradeApproval from './components/trading/TradeApproval'
import TradingSettings from './components/trading/TradingSettings'
import TradeHistory from './components/trading/TradeHistory'
import PositionMonitor from './components/trading/PositionMonitor'

// IT-Bear components
import {
  SectorDashboard,
  EarningsCalendar,
  ITUniverse,
  StockDetail as ITStockDetail,
  StrategyBuilder as ITStrategyBuilder,
  Scanner,
  NotificationSettings,
  USSignals,
} from './components/it-bear'

const API_BASE = 'http://localhost:8000'

function TradingNavLink({ className }) {
  const [engineRunning, setEngineRunning] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function checkStatus() {
      try {
        const res = await fetch(`${API_BASE}/api/trading/status`)
        if (res.ok && !cancelled) {
          const data = await res.json()
          setEngineRunning(data.running ?? false)
        }
      } catch { /* ignore — backend may not be up */ }
    }

    checkStatus()
    // Poll every 30 seconds for engine status
    const interval = setInterval(checkStatus, 30000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  return (
    <NavLink to="/trading" className={className}>
      <span className="flex items-center gap-1.5">
        {engineRunning && (
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        )}
        Trading
      </span>
    </NavLink>
  )
}

function ITBearNavLink({ className }) {
  // Derive isActive ourselves so we can still apply className
  const location = useLocation()
  const isActive = location.pathname.startsWith('/it-bear')

  return (
    <NavLink
      to="/it-bear"
      className={({ isActive: routerActive }) => {
        const active = routerActive || isActive
        return `px-2.5 py-1.5 rounded-md text-sm font-medium transition-colors ${
          active
            ? 'bg-red-500/20 border border-red-500/30 text-red-300'
            : 'text-slate-400 hover:text-red-300 hover:bg-red-500/10 border border-transparent'
        }`
      }}
      end={false}
    >
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
        IT Bear
      </span>
    </NavLink>
  )
}

function NavBar() {
  const linkClass = ({ isActive }) =>
    `px-2.5 py-1.5 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? 'bg-slate-700 text-white'
        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
    }`

  return (
    <nav className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2 flex items-center justify-between">
        <div className="flex items-center gap-0.5 overflow-x-auto">
          <NavLink to="/" end className={linkClass}>Dashboard</NavLink>
          <TradingNavLink className={linkClass} />
          <ITBearNavLink />
          <NavLink to="/options" className={linkClass}>Options</NavLink>
          <NavLink to="/mcx" className={linkClass}>MCX</NavLink>
          <NavLink to="/history" className={linkClass}>History</NavLink>
          <NavLink to="/fo-strategies" className={linkClass}>F&O Playbook</NavLink>
          <NavLink to="/strategies" className={linkClass}>My Strategies</NavLink>
          <NavLink to="/alerts" className={linkClass}>Alerts</NavLink>
          <NavLink to="/glossary" className={linkClass}>Indicators</NavLink>
        </div>
        <StockSearch />
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans">
        <NavBar />
        <Routes>
          {/* Core routes */}
          <Route path="/" element={<Dashboard />} />
          <Route path="/stock/:symbol" element={<StockAnalysis />} />
          <Route path="/options" element={<OptionChain />} />
          <Route path="/mcx" element={<MCXCommodities />} />
          <Route path="/history" element={<AnalysisHistory />} />
          <Route path="/fo-strategies" element={<PredefinedStrategies />} />
          <Route path="/strategies" element={<StrategyList />} />
          <Route path="/strategies/new" element={<StrategyBuilder />} />
          <Route path="/strategies/:id" element={<StrategyBuilder />} />
          <Route path="/alerts" element={<AlertsPanel />} />
          <Route path="/glossary" element={<IndicatorGlossary />} />

          {/* Trading routes */}
          <Route path="/trading" element={<TradingDashboard />} />
          <Route path="/trading/approve/:id" element={<TradeApproval />} />
          <Route path="/trading/settings" element={<TradingSettings />} />
          <Route path="/trading/history" element={<TradeHistory />} />
          <Route path="/trading/positions" element={<PositionMonitor />} />

          {/* IT-Bear routes */}
          <Route path="/it-bear" element={<SectorDashboard />} />
          <Route path="/it-bear/earnings" element={<EarningsCalendar />} />
          <Route path="/it-bear/universe" element={<ITUniverse />} />
          <Route path="/it-bear/stock/:symbol" element={<ITStockDetail />} />
          <Route path="/it-bear/strategy-builder" element={<ITStrategyBuilder />} />
          <Route path="/it-bear/strategy-builder/:symbol" element={<ITStrategyBuilder />} />
          <Route path="/it-bear/scanner" element={<Scanner />} />
          <Route path="/it-bear/notifications" element={<NotificationSettings />} />
          <Route path="/it-bear/us-signals" element={<USSignals />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
