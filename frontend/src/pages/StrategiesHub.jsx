/**
 * StrategiesHub — landing for the Strategies section.
 * Routes to the unified Strategy Marketplace plus the 3 existing strategy systems.
 */
import { Link } from 'react-router-dom'
import { PageHeader } from '../ui'
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
        <p className="text-sm text-ink">
          <span className="font-semibold">New:</span> the unified{' '}
          <Link to="/marketplace" className="text-brand font-semibold hover:underline">Strategy Marketplace</Link>{' '}
          is live — every strategy in one place, forkable and editable.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <HubCard
          to="/marketplace"
          icon={IconLayers}
          title="Strategy Marketplace"
          description="All strategies in one place — browse, fork, edit triggers, author new ones with AI."
          tone="brand"
          badge="NEW"
        />
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
