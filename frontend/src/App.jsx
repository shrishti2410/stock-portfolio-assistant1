import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppShell } from './shell/AppShell'

// Existing feature components (unchanged — reachable inside the new shell)
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
import TradingDashboard from './components/trading/TradingDashboard'
import TradeApproval from './components/trading/TradeApproval'
import TradingSettings from './components/trading/TradingSettings'
import TradeHistory from './components/trading/TradeHistory'
import PositionMonitor from './components/trading/PositionMonitor'

// New section hub pages (Phase A)
import StrategiesHub from './pages/StrategiesHub'
import Backtest from './pages/Backtest'
import MarketsHub from './pages/MarketsHub'
import SettingsHub from './pages/SettingsHub'
import LLMSettings from './pages/LLMSettings'

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

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          {/* ── Portfolio (was Dashboard + History) ── */}
          <Route path="/" element={<Dashboard />} />
          <Route path="/portfolio" element={<Dashboard />} />
          <Route path="/stock/:symbol" element={<StockAnalysis />} />
          <Route path="/history" element={<AnalysisHistory />} />

          {/* ── Strategies ── */}
          <Route path="/strategies" element={<StrategiesHub />} />
          <Route path="/strategies/custom" element={<StrategyList />} />
          <Route path="/strategies/new" element={<StrategyBuilder />} />
          <Route path="/strategies/:id" element={<StrategyBuilder />} />
          <Route path="/fo-strategies" element={<PredefinedStrategies />} />

          {/* ── Backtest (Phase C) ── */}
          <Route path="/backtest" element={<Backtest />} />

          {/* ── Trading ── */}
          <Route path="/trading" element={<TradingDashboard />} />
          <Route path="/trading/approve/:id" element={<TradeApproval />} />
          <Route path="/trading/settings" element={<TradingSettings />} />
          <Route path="/trading/history" element={<TradeHistory />} />
          <Route path="/trading/positions" element={<PositionMonitor />} />

          {/* ── Signals (was Alerts) ── */}
          <Route path="/signals" element={<AlertsPanel />} />
          <Route path="/alerts" element={<AlertsPanel />} />

          {/* ── Markets (Options + MCX + Earnings) ── */}
          <Route path="/markets" element={<MarketsHub />} />
          <Route path="/options" element={<OptionChain />} />
          <Route path="/mcx" element={<MCXCommodities />} />

          {/* ── Settings (Notifications + Glossary + LLM) ── */}
          <Route path="/settings" element={<SettingsHub />} />
          <Route path="/settings/llm" element={<LLMSettings />} />
          <Route path="/glossary" element={<IndicatorGlossary />} />

          {/* ── IT-Bear thesis ── */}
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
      </AppShell>
    </BrowserRouter>
  )
}
