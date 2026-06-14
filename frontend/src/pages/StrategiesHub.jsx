/**
 * StrategiesHub — landing for the Strategies section.
 * Phase A: routes to the 3 existing strategy systems + previews the unified
 * marketplace coming in Phase B.
 */
import { PageHeader, Card } from '../ui'
import { IconStrategy, IconLayers, IconBear, IconBacktest } from '../ui/icons'
import { HubCard } from './HubCard'

export default function StrategiesHub() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Strategies"
        subtitle="Browse, configure, and author trading strategies for India + US markets"
        icon={IconStrategy}
      />

      <div className="bg-brand-soft border border-brand/20 rounded-xl p-4 mb-6">
        <p className="text-sm font-semibold text-ink">Unified strategy marketplace — coming in Phase B</p>
        <p className="text-xs text-ink-muted mt-1 leading-relaxed">
          Soon: one place to browse all strategies, fork &amp; edit their trigger conditions in plain
          English, and author brand-new ones by chatting with an LLM. For now, the three existing
          systems are linked below.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <HubCard
          to="/fo-strategies"
          icon={IconLayers}
          title="F&O Playbook"
          description="13 pre-built options strategies (Iron Condor, spreads, straddles) with live condition checks against NIFTY / BANKNIFTY."
          tone="brand"
          badge="13 strategies"
        />
        <HubCard
          to="/strategies/custom"
          icon={IconStrategy}
          title="My Strategies"
          description="Custom rule-based strategies you've authored in natural language. Edit rules, run against a watchlist, get alerts."
          tone="emerald"
        />
        <HubCard
          to="/it-bear"
          icon={IconBear}
          title="IT-Bear Thesis"
          description="5 short-biased strategies for the IT services downturn thesis — Long Put, Bear spreads, Pre-Earnings, NIFTY IT Futures."
          tone="red"
          badge="5 strategies"
        />
        <HubCard
          to="/backtest"
          icon={IconBacktest}
          title="Backtest a strategy"
          description="Test any strategy against historical data before risking capital. Equity curve, win rate, trade log."
          tone="amber"
          badge="Phase C"
        />
      </div>
    </div>
  )
}
