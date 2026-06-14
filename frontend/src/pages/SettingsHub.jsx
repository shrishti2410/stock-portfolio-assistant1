/**
 * SettingsHub — notifications, Telegram, broker setup, indicator glossary.
 */
import { PageHeader } from '../ui'
import { IconBell, IconSettings, IconStrategy } from '../ui/icons'
import { HubCard } from './HubCard'

export default function SettingsHub() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Settings"
        subtitle="Notifications, broker connection, and reference material"
        icon={IconSettings}
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <HubCard
          to="/it-bear/notifications"
          icon={IconBell}
          title="Notifications"
          description="In-app, email, and Telegram alerts. Per-layer auto-execution toggles for the trading engine."
          tone="brand"
        />
        <HubCard
          to="/trading/settings"
          icon={IconSettings}
          title="Trading Engine"
          description="Capital limits, paper/live mode, strategy toggles, scan interval, circuit breaker."
          tone="emerald"
        />
        <HubCard
          to="/glossary"
          icon={IconStrategy}
          title="Indicator Glossary"
          description="Reference for RSI, MACD, EMA, Bollinger Bands, ADX, Stochastic RSI and how signals are read."
          tone="slate"
        />
      </div>
    </div>
  )
}
