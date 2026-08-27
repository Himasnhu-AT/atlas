'use client'

import { useState } from 'react'

export interface CacheVariable {
  name: string
  offsetBytes: number
  sizeBytes: number
}

export interface CacheHierarchyVisualizerProps {
  cacheLineBytes?: number
  cores?: number
  variables: CacheVariable[]
}

export function CacheHierarchyVisualizer({
  variables,
}: CacheHierarchyVisualizerProps) {
  const [core1Freq, setCore1Freq] = useState(50)
  const [core2Freq, setCore2Freq] = useState(50)

  // False sharing occurs when both cores write frequently to variables sharing the same 64-byte line
  const conflictIntensity = Math.round(((core1Freq * core2Freq) / 2500) * 100)
  const effectiveThroughputPct = Math.max(100 - Math.round(conflictIntensity * 0.85), 15)

  return (
    <div className="not-prose my-8 rounded border border-rule bg-paper p-5 font-sans shadow-sm sm:p-6">
      <div className="flex items-center justify-between border-b border-rule pb-3">
        <div>
          <span className="text-eyebrow font-medium uppercase text-muted">CPU Cache & MESI Coherence</span>
          <h4 className="text-section font-serif text-ink">False Sharing & Cache Invalidation Simulator</h4>
        </div>
        <span className={`font-mono text-caption font-semibold ${conflictIntensity > 50 ? 'text-fail' : 'text-pass'}`}>
          Throughput: {effectiveThroughputPct}%
        </span>
      </div>

      {/* Shared Cache Line Diagram */}
      <div className="mt-5 rounded border border-rule-strong bg-paper-sunken p-4">
        <div className="text-[11px] font-mono uppercase text-muted text-center mb-2">
          Shared 64-Byte L1 Cache Line (MESI Protocol)
        </div>
        <div className="flex gap-2">
          <div className="flex-1 rounded border border-accent bg-accent/15 p-3 text-center">
            <span className="text-caption font-mono font-bold text-accent">Core 1 Write Target</span>
            <div className="text-xs text-ink-soft mt-1">{variables[0]?.name || 'var_a'} ({variables[0]?.sizeBytes || 4}B)</div>
          </div>
          <div className="flex-1 rounded border border-[#5c6b73] bg-[#5c6b73]/15 p-3 text-center">
            <span className="text-caption font-mono font-bold text-ink">Core 2 Write Target</span>
            <div className="text-xs text-ink-soft mt-1">{variables[1]?.name || 'var_b'} ({variables[1]?.sizeBytes || 4}B)</div>
          </div>
        </div>
        {conflictIntensity > 40 && (
          <div className="mt-3 text-center text-caption font-mono font-bold text-fail animate-pulse">
            ⚠️ MESI INVALIDATION CASCADE: Cache line ping-pongs across CPU cores!
          </div>
        )}
      </div>

      {/* Frequency Sliders */}
      <div className="mt-5 grid gap-4 border-t border-rule pt-4 sm:grid-cols-2">
        <div>
          <div className="flex justify-between text-caption text-ink-soft">
            <label htmlFor="ch-core1">Core 1 Write Rate</label>
            <span className="font-mono text-muted">{core1Freq} ops/ms</span>
          </div>
          <input
            id="ch-core1"
            type="range"
            min="0"
            max="100"
            value={core1Freq}
            onChange={(e) => setCore1Freq(Number(e.target.value))}
            className="w-full accent-accent cursor-pointer mt-1"
          />
        </div>

        <div>
          <div className="flex justify-between text-caption text-ink-soft">
            <label htmlFor="ch-core2">Core 2 Write Rate</label>
            <span className="font-mono text-muted">{core2Freq} ops/ms</span>
          </div>
          <input
            id="ch-core2"
            type="range"
            min="0"
            max="100"
            value={core2Freq}
            onChange={(e) => setCore2Freq(Number(e.target.value))}
            className="w-full accent-accent cursor-pointer mt-1"
          />
        </div>
      </div>
    </div>
  )
}
