/**
 * Backtest — Phase A placeholder showing the planned flow.
 * Phase C will replace this with the real engine (Alpaca US + jugaad-data India).
 */
import { PageHeader, Card } from '../ui'
import { IconBacktest } from '../ui/icons'

const STEPS = [
  { n: 1, title: 'Pick a strategy', desc: 'Choose from the marketplace or a draft you just built.' },
  { n: 2, title: 'Pick universe', desc: 'NIFTY IT, a single stock, or a custom watchlist (India or US).' },
  { n: 3, title: 'Pick date range', desc: 'e.g. Jan 2025 → today. Minimum 6 months recommended.' },
  { n: 4, title: 'Set paper capital', desc: 'Starting balance + per-trade sizing rules.' },
  { n: 5, title: 'Run', desc: 'Replays historical bars through the same engine the live system uses.' },
  { n: 6, title: 'Review', desc: 'Equity curve, every trade taken, win rate, max drawdown, vs-benchmark.' },
]

export default function Backtest() {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <PageHeader
        title="Backtest"
        subtitle="Validate any strategy against historical data before going live"
        icon={IconBacktest}
      />

      <div className="bg-amber-500/10 border border-amber-500/25 rounded-xl p-4 mb-6">
        <p className="text-sm font-semibold text-amber-600 dark:text-amber-300">Coming in Phase C</p>
        <p className="text-xs text-ink-muted mt-1 leading-relaxed">
          The backtest engine is the next phase. Data sources: <strong>jugaad-data</strong> for Indian
          NSE history (already installed, 10+ years) and <strong>Alpaca Markets</strong> for US stocks
          (free paper key — sign up at alpaca.markets). The flow below is what you'll get.
        </p>
      </div>

      <Card>
        <h3 className="text-sm font-semibold text-ink mb-4">How backtesting will work</h3>
        <div className="space-y-3">
          {STEPS.map(s => (
            <div key={s.n} className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full bg-brand-soft text-brand flex items-center justify-center text-xs font-bold shrink-0 tnum">
                {s.n}
              </div>
              <div>
                <p className="text-sm font-medium text-ink">{s.title}</p>
                <p className="text-xs text-ink-muted mt-0.5">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
