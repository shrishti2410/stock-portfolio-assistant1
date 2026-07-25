/**
 * MarketsHub — reference market data: option chain, MCX commodities, earnings.
 */
import { PageHeader } from '../ui'
import { IconMarkets, IconChart, IconCalendar } from '../ui/icons'
import { HubCard } from './HubCard'

export default function MarketsHub() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Markets"
        subtitle="Reference data — option chains, commodities, and the earnings calendar"
        icon={IconMarkets}
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <HubCard
          to="/options"
          icon={IconChart}
          title="Option Chain"
          description="Live NSE option chain — strikes, OI, IV, PCR for NIFTY, BANKNIFTY, and F&O stocks."
          tone="brand"
        />
        <HubCard
          to="/mcx"
          icon={IconMarkets}
          title="MCX Commodities"
          description="Gold, Silver, Crude, Natural Gas, Copper — spot prices and 60-day history."
          tone="amber"
        />
        <HubCard
          to="/it-bear/earnings"
          icon={IconCalendar}
          title="Earnings Calendar"
          description="Upcoming IT-sector earnings with countdown + last 4 quarters. Pre-earnings sweet-spot flags."
          tone="purple"
        />
      </div>
    </div>
  )
}
