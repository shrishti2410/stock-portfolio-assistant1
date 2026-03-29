/**
 * IndicatorGlossary — explains each technical indicator used in the app.
 */

import { Link } from 'react-router-dom'

const INDICATORS = [
  {
    name: 'RSI (Relative Strength Index)',
    short: 'RSI',
    description: 'Measures the speed and magnitude of recent price changes to evaluate overbought or oversold conditions. Values range from 0 to 100.',
    interpretation: [
      { condition: 'RSI < 30', meaning: 'Oversold', signal: 'bullish', detail: 'Stock may be undervalued — potential buying opportunity as a bounce is likely.' },
      { condition: 'RSI 30–45', meaning: 'Weak momentum', signal: 'bearish', detail: 'Below neutral zone — bearish pressure exists.' },
      { condition: 'RSI 45–55', meaning: 'Neutral', signal: 'neutral', detail: 'No strong directional signal — wait for clearer trend.' },
      { condition: 'RSI 55–70', meaning: 'Strong momentum', signal: 'bullish', detail: 'Above neutral — bullish momentum building.' },
      { condition: 'RSI > 70', meaning: 'Overbought', signal: 'bearish', detail: 'Stock may be overvalued — potential pullback ahead.' },
    ],
    period: '14 days',
  },
  {
    name: 'MACD (Moving Average Convergence Divergence)',
    short: 'MACD',
    description: 'Shows the relationship between two moving averages (12-day EMA and 26-day EMA). The MACD histogram shows the difference between MACD line and signal line.',
    interpretation: [
      { condition: 'Histogram crosses above 0', meaning: 'Bullish crossover', signal: 'bullish', detail: 'MACD line crossed above signal line — strong buy signal.' },
      { condition: 'Histogram crosses below 0', meaning: 'Bearish crossover', signal: 'bearish', detail: 'MACD line crossed below signal line — strong sell signal.' },
      { condition: 'Histogram positive', meaning: 'Bullish momentum', signal: 'bullish', detail: 'Upward momentum is present.' },
      { condition: 'Histogram negative', meaning: 'Bearish momentum', signal: 'bearish', detail: 'Downward momentum is present.' },
    ],
    period: '12, 26, 9 days',
  },
  {
    name: 'EMA (Exponential Moving Average)',
    short: 'EMA',
    description: 'A weighted moving average that gives more importance to recent prices. We track EMA 10, 20, 50, and 200 to identify short and long-term trends.',
    interpretation: [
      { condition: 'EMA 10 > EMA 20', meaning: 'Short-term uptrend', signal: 'bullish', detail: 'Recent prices are rising faster than the 20-day average.' },
      { condition: 'EMA 10 < EMA 20', meaning: 'Short-term downtrend', signal: 'bearish', detail: 'Recent prices are falling relative to the 20-day average.' },
      { condition: 'EMA 50 > EMA 200', meaning: 'Golden Cross', signal: 'bullish', detail: 'Long-term bullish signal — historically predicts sustained uptrends.' },
      { condition: 'EMA 50 < EMA 200', meaning: 'Death Cross', signal: 'bearish', detail: 'Long-term bearish signal — often precedes extended downtrends.' },
      { condition: 'Price > EMA 50', meaning: 'Above medium trend', signal: 'bullish', detail: 'Stock is trading above its 50-day moving average — positive.' },
      { condition: 'Price < EMA 50', meaning: 'Below medium trend', signal: 'bearish', detail: 'Stock is trading below its 50-day moving average — negative.' },
    ],
    period: '10, 20, 50, 200 days',
  },
  {
    name: 'Bollinger Bands',
    short: 'BB',
    description: 'A volatility indicator with an upper and lower band around a 20-day moving average. The bands widen when volatility increases and narrow when it decreases.',
    interpretation: [
      { condition: 'Price at lower band', meaning: 'Potential bounce', signal: 'bullish', detail: 'Price is at the statistical low — may revert to the mean (bounce up).' },
      { condition: 'Price at upper band', meaning: 'Potential pullback', signal: 'bearish', detail: 'Price is at the statistical high — may revert to the mean (pull back).' },
      { condition: 'Between bands', meaning: 'Normal range', signal: 'neutral', detail: 'Price is within normal volatility range.' },
    ],
    period: '20 days, 2 std dev',
  },
  {
    name: 'ADX (Average Directional Index)',
    short: 'ADX',
    description: 'Measures the strength of a trend regardless of direction. Does NOT tell you if the trend is up or down — only how strong it is.',
    interpretation: [
      { condition: 'ADX > 25', meaning: 'Strong trend', signal: 'neutral', detail: 'A strong trend is in place (could be bullish or bearish). Other indicators tell you the direction.' },
      { condition: 'ADX < 25', meaning: 'Weak/no trend', signal: 'neutral', detail: 'No clear trend — market is ranging. Trend-following strategies may not work well.' },
    ],
    period: '14 days',
  },
  {
    name: 'Volume Analysis',
    short: 'Volume',
    description: 'Compares current trading volume to the 20-day average. High volume confirms price moves; low volume suggests weak conviction.',
    interpretation: [
      { condition: 'Volume > 2x average', meaning: 'Volume spike', signal: 'neutral', detail: 'Unusual activity — could signal breakout, news event, or institutional interest.' },
      { condition: 'Volume > 1.5x average', meaning: 'Above normal', signal: 'neutral', detail: 'Higher-than-normal interest — confirms the current price move.' },
      { condition: 'Volume < 0.5x average', meaning: 'Low participation', signal: 'neutral', detail: 'Very low volume — price moves on low volume are unreliable.' },
    ],
    period: '20-day average',
  },
  {
    name: 'Stochastic RSI',
    short: 'StochRSI',
    description: 'Applies the Stochastic oscillator formula to RSI values instead of price. More sensitive than regular RSI — gives earlier signals but more false positives.',
    interpretation: [
      { condition: 'StochRSI < 20', meaning: 'Oversold', signal: 'bullish', detail: 'RSI itself is at an oversold extreme — strong potential for reversal up.' },
      { condition: 'StochRSI > 80', meaning: 'Overbought', signal: 'bearish', detail: 'RSI itself is at an overbought extreme — strong potential for reversal down.' },
    ],
    period: '14 days',
  },
]

const SIG_COLOR = {
  bullish: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  bearish: 'bg-red-500/15 text-red-400 border-red-500/30',
  neutral: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
}

export default function IndicatorGlossary() {
  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-slate-500 hover:text-slate-300 text-sm">&larr; Dashboard</Link>
        <h1 className="text-xl font-bold text-white">Indicator Glossary</h1>
      </div>

      <p className="text-sm text-slate-400 mb-6">
        These are the technical indicators used by the screening engine to generate signals.
        Each indicator measures a different aspect of price action, momentum, or volume.
      </p>

      <div className="space-y-6">
        {INDICATORS.map((ind) => (
          <div
            key={ind.short}
            id={ind.short.toLowerCase()}
            className="bg-slate-800/80 border border-slate-700 rounded-xl p-5"
          >
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-base font-bold text-white">{ind.name}</h2>
              <span className="text-[10px] px-2 py-0.5 bg-slate-700 rounded text-slate-400">
                Period: {ind.period}
              </span>
            </div>

            <p className="text-sm text-slate-400 mb-4 leading-relaxed">
              {ind.description}
            </p>

            <div className="space-y-2">
              {ind.interpretation.map((interp, i) => (
                <div
                  key={i}
                  className={`flex items-start gap-3 px-3 py-2 rounded-lg border ${SIG_COLOR[interp.signal]}`}
                >
                  <div className="min-w-[120px]">
                    <span className="text-xs font-bold">{interp.condition}</span>
                  </div>
                  <div className="flex-1">
                    <span className="text-xs font-semibold">{interp.meaning}</span>
                    <p className="text-xs text-slate-400 mt-0.5">{interp.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </main>
  )
}
