'use client'

import { useState } from 'react'

export interface OrderLevel {
  price: number
  size: number
}

export interface OrderBookDepthVisualizerProps {
  bids: OrderLevel[]
  asks: OrderLevel[]
  tickSize?: number
  defaultOrderSize?: number
}

export function OrderBookDepthVisualizer({
  bids: initialBids,
  asks: initialAsks,
  defaultOrderSize = 350,
}: OrderBookDepthVisualizerProps) {
  const [bids] = useState<OrderLevel[]>(initialBids)
  const [asks] = useState<OrderLevel[]>(initialAsks)
  const [orderSize, setOrderSize] = useState(defaultOrderSize)

  const sortedAsks = [...asks].sort((a, b) => a.price - b.price)
  const sortedBids = [...bids].sort((a, b) => b.price - a.price)

  const bestBid = sortedBids[0]?.price || 0
  const bestAsk = sortedAsks[0]?.price || 0
  const midPrice = Math.round(((bestBid + bestAsk) / 2) * 100) / 100
  const spread = Math.round((bestAsk - bestBid) * 100) / 100

  // Calculate Market Buy execution slippage
  let remainingSize = orderSize
  let totalCost = 0
  let filledLevels = 0

  for (const level of sortedAsks) {
    if (remainingSize <= 0) break
    const fillFromLevel = Math.min(remainingSize, level.size)
    totalCost += fillFromLevel * level.price
    remainingSize -= fillFromLevel
    filledLevels++
  }

  const filledTotal = orderSize - remainingSize
  const vwap = filledTotal > 0 ? Math.round((totalCost / filledTotal) * 1000) / 1000 : midPrice
  const slippageBps = Math.round(((vwap - bestAsk) / bestAsk) * 10000)

  return (
    <div className="not-prose my-8 rounded border border-rule bg-paper p-5 font-sans shadow-sm sm:p-6">
      <div className="flex items-center justify-between border-b border-rule pb-3">
        <div>
          <span className="text-eyebrow font-medium uppercase text-muted">Market Microstructure</span>
          <h4 className="text-section font-serif text-ink">Limit Order Book & Market Impact Simulator</h4>
        </div>
        <div className="text-right font-mono text-caption">
          <span className="text-muted">Spread:</span> <span className="font-semibold text-ink">${spread.toFixed(2)}</span>
          <span className="ml-3 text-muted">Mid:</span> <span className="font-semibold text-ink">${midPrice.toFixed(2)}</span>
        </div>
      </div>

      <div className="mt-5 grid gap-6 sm:grid-cols-2">
        {/* Order Book Depth Ladder */}
        <div className="rounded border border-rule bg-paper-sunken p-3 font-mono text-caption">
          <div className="flex justify-between border-b border-rule pb-1 text-[11px] text-muted">
            <span>PRICE</span>
            <span>ASK SIZE</span>
          </div>
          {/* Asks (Red) */}
          <div className="space-y-1 py-2">
            {sortedAsks.slice(0, 5).reverse().map((level, i) => (
              <div key={`ask-${i}`} className="relative flex justify-between px-2 py-0.5 text-fail">
                <div
                  style={{ width: `${Math.min((level.size / 1000) * 100, 100)}%` }}
                  className="absolute right-0 top-0 bottom-0 bg-fail/10 pointer-events-none rounded"
                />
                <span className="font-semibold">${level.price.toFixed(2)}</span>
                <span>{level.size}</span>
              </div>
            ))}
          </div>

          <div className="my-1 border-t border-b border-rule-strong py-1 text-center font-bold text-ink-soft text-[11px]">
            --- SPREAD ${spread.toFixed(2)} ---
          </div>

          {/* Bids (Green) */}
          <div className="space-y-1 py-2">
            {sortedBids.slice(0, 5).map((level, i) => (
              <div key={`bid-${i}`} className="relative flex justify-between px-2 py-0.5 text-pass">
                <div
                  style={{ width: `${Math.min((level.size / 1000) * 100, 100)}%` }}
                  className="absolute right-0 top-0 bottom-0 bg-pass/10 pointer-events-none rounded"
                />
                <span className="font-semibold">${level.price.toFixed(2)}</span>
                <span>{level.size}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Market Order Execution Simulator */}
        <div className="flex flex-col justify-between">
          <div>
            <span className="text-caption font-medium text-ink-soft">Simulate Market Buy Order Impact:</span>
            <div className="mt-3">
              <div className="flex justify-between text-[11px] font-mono text-muted">
                <span>Order Quantity</span>
                <span className="font-bold text-ink">{orderSize} units</span>
              </div>
              <input
                type="range"
                min="50"
                max="1500"
                step="50"
                value={orderSize}
                onChange={(e) => setOrderSize(Number(e.target.value))}
                className="w-full accent-accent cursor-pointer mt-1"
              />
            </div>
          </div>

          {/* Execution Metrics Box */}
          <div className="mt-4 rounded border border-rule bg-paper-raised p-4 font-mono text-caption space-y-2">
            <div className="flex justify-between">
              <span className="text-muted">Best Available Ask:</span>
              <span className="text-ink font-semibold">${bestAsk.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Executed VWAP:</span>
              <span className="text-accent font-bold">${vwap.toFixed(3)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Price Levels Swept:</span>
              <span className="text-ink font-semibold">{filledLevels} level(s)</span>
            </div>
            <div className="flex justify-between border-t border-rule pt-2">
              <span className="text-muted">Slippage Impact:</span>
              <span className={`font-bold ${slippageBps > 20 ? 'text-fail' : 'text-pass'}`}>
                +{slippageBps} bps
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
