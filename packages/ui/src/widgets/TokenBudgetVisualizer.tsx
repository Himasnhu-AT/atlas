'use client'

import { useState } from 'react'

export interface TokenBudgetVisualizerProps {
  maxTokens?: number
  systemTokens?: number
  toolSchemaTokens?: number
  initialTurns?: number
  reserveOutputTokens?: number
  showAttentionHeatmap?: boolean
  puzzleTarget?: string
}

export function TokenBudgetVisualizer({
  maxTokens = 4096,
  systemTokens: defaultSystemTokens = 350,
  toolSchemaTokens: defaultToolTokens = 400,
  initialTurns = 8,
  reserveOutputTokens = 512,
  showAttentionHeatmap = true,
  puzzleTarget,
}: TokenBudgetVisualizerProps) {
  const [systemTokens, setSystemTokens] = useState(defaultSystemTokens)
  const [toolTokens, setToolTokens] = useState(defaultToolTokens)
  const [turns, setTurns] = useState(initialTurns)
  const [tokensPerTurn, setTokensPerTurn] = useState(180)

  const historyTokens = turns * tokensPerTurn
  const totalInputTokens = systemTokens + toolTokens + historyTokens
  const totalWithReserve = totalInputTokens + reserveOutputTokens
  const isOverflow = totalWithReserve > maxTokens
  const usedRatio = Math.min(totalWithReserve / maxTokens, 1)

  const systemPct = (systemTokens / maxTokens) * 100
  const toolPct = (toolTokens / maxTokens) * 100
  const historyPct = (historyTokens / maxTokens) * 100
  const reservePct = (reserveOutputTokens / maxTokens) * 100

  // Quadratic attention complexity ratio relative to 1k tokens
  const attentionFootprint = Math.round(Math.pow(totalInputTokens / 1000, 2) * 10) / 10

  return (
    <div className="not-prose my-8 rounded border border-rule bg-paper p-5 font-sans shadow-sm sm:p-6">
      <div className="flex items-center justify-between border-b border-rule pb-3">
        <div>
          <span className="text-eyebrow font-medium uppercase text-muted">Interactive Sandbox</span>
          <h4 className="text-section font-serif text-ink">Context Budget & Attention Matrix</h4>
        </div>
        <div className="text-right font-mono text-caption">
          <span className={isOverflow ? 'text-fail font-semibold' : 'text-pass font-semibold'}>
            {totalWithReserve} / {maxTokens} tokens
          </span>
        </div>
      </div>

      {puzzleTarget && (
        <div className="mt-3 rounded border border-rule-strong bg-paper-sunken px-3 py-2 text-caption text-ink-soft">
          <strong className="font-semibold text-ink">Challenge:</strong> {puzzleTarget}
        </div>
      )}

      {/* Context Allocation Bar */}
      <div className="mt-5">
        <div className="flex justify-between text-caption text-muted mb-1.5">
          <span>Context Window Allocation</span>
          <span>{Math.round(usedRatio * 100)}% Used</span>
        </div>
        <div className="relative h-6 w-full overflow-hidden rounded bg-paper-sunken border border-rule flex">
          <div
            style={{ width: `${systemPct}%` }}
            className="h-full bg-accent opacity-90 transition-all duration-150"
            title={`System Prompt: ${systemTokens}t`}
          />
          <div
            style={{ width: `${toolPct}%` }}
            className="h-full bg-[#5c6b73] opacity-90 transition-all duration-150"
            title={`Tool Schemas: ${toolTokens}t`}
          />
          <div
            style={{ width: `${historyPct}%` }}
            className="h-full bg-[#9d8189] opacity-90 transition-all duration-150"
            title={`Conversation History: ${historyTokens}t`}
          />
          <div
            style={{ width: `${reservePct}%` }}
            className="h-full bg-[#d4a373] opacity-90 transition-all duration-150"
            title={`Output Reserve: ${reserveOutputTokens}t`}
          />
          {isOverflow && (
            <div className="absolute right-0 top-0 bottom-0 bg-fail/30 w-full animate-pulse flex items-center justify-end pr-2 text-caption text-fail font-bold font-mono">
              OVERFLOW (+{totalWithReserve - maxTokens}t)
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap gap-4 text-caption text-muted font-mono text-[11px]">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-xs bg-accent" />
            <span>System: {systemTokens}t</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-xs bg-[#5c6b73]" />
            <span>Tools: {toolTokens}t</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-xs bg-[#9d8189]" />
            <span>History: {historyTokens}t</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-xs bg-[#d4a373]" />
            <span>Reserve: {reserveOutputTokens}t</span>
          </div>
        </div>
      </div>

      {/* Sliders Grid */}
      <div className="mt-6 grid gap-4 border-t border-rule pt-4 sm:grid-cols-2">
        <div>
          <div className="flex justify-between text-caption text-ink-soft">
            <label htmlFor="tb-turns">Conversation Turns: {turns}</label>
            <span className="font-mono text-muted">{historyTokens}t</span>
          </div>
          <input
            id="tb-turns"
            type="range"
            min="0"
            max="30"
            value={turns}
            onChange={(e) => setTurns(Number(e.target.value))}
            className="mt-1 w-full accent-accent cursor-pointer"
          />
        </div>

        <div>
          <div className="flex justify-between text-caption text-ink-soft">
            <label htmlFor="tb-tpt">Avg Tokens / Turn: {tokensPerTurn}</label>
            <span className="font-mono text-muted">{tokensPerTurn}t</span>
          </div>
          <input
            id="tb-tpt"
            type="range"
            min="50"
            max="500"
            step="10"
            value={tokensPerTurn}
            onChange={(e) => setTokensPerTurn(Number(e.target.value))}
            className="mt-1 w-full accent-accent cursor-pointer"
          />
        </div>

        <div>
          <div className="flex justify-between text-caption text-ink-soft">
            <label htmlFor="tb-sys">System Prompt Tokens</label>
            <span className="font-mono text-muted">{systemTokens}t</span>
          </div>
          <input
            id="tb-sys"
            type="range"
            min="100"
            max="1200"
            step="25"
            value={systemTokens}
            onChange={(e) => setSystemTokens(Number(e.target.value))}
            className="mt-1 w-full accent-accent cursor-pointer"
          />
        </div>

        <div>
          <div className="flex justify-between text-caption text-ink-soft">
            <label htmlFor="tb-tools">Tool Schema Overhead</label>
            <span className="font-mono text-muted">{toolTokens}t</span>
          </div>
          <input
            id="tb-tools"
            type="range"
            min="0"
            max="1500"
            step="50"
            value={toolTokens}
            onChange={(e) => setToolTokens(Number(e.target.value))}
            className="mt-1 w-full accent-accent cursor-pointer"
          />
        </div>
      </div>

      {showAttentionHeatmap && (
        <div className="mt-5 rounded border border-rule bg-paper-raised p-3 text-caption flex items-center justify-between">
          <div className="text-ink-soft">
            <span className="font-medium text-ink">Attention Memory Scaling:</span> O(N²) KV-cache cost grows with total sequence length.
          </div>
          <div className="font-mono font-semibold text-accent whitespace-nowrap pl-4">
            ~{attentionFootprint}x baseline
          </div>
        </div>
      )}
    </div>
  )
}
