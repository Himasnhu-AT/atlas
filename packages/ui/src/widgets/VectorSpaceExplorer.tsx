'use client'

import { useState } from 'react'

export interface VectorPoint {
  id: string
  label: string
  x: number
  y: number
  category?: string
}

export interface VectorSpaceExplorerProps {
  points: VectorPoint[]
  initialSimilarityThreshold?: number
  queryPoint?: {
    label: string
    x: number
    y: number
  }
}

function cosineSimilarity(x1: number, y1: number, x2: number, y2: number): number {
  const dot = x1 * x2 + y1 * y2
  const norm1 = Math.sqrt(x1 * x1 + y1 * y1) || 1
  const norm2 = Math.sqrt(x2 * x2 + y2 * y2) || 1
  return Math.round((dot / (norm1 * norm2)) * 100) / 100
}

export function VectorSpaceExplorer({
  points,
  initialSimilarityThreshold = 0.7,
  queryPoint: defaultQuery = { label: 'Query', x: 0.8, y: 0.6 },
}: VectorSpaceExplorerProps) {
  const [query, setQuery] = useState(defaultQuery)
  const [threshold, setThreshold] = useState(initialSimilarityThreshold)

  // Canvas coordinate system (-1 to +1 mapped to 0 to 400px)
  const toCanvas = (val: number, size = 400) => ((val + 1) / 2) * size

  const ranked = points
    .map((p) => ({
      ...p,
      similarity: cosineSimilarity(query.x, query.y, p.x, p.y),
    }))
    .sort((a, b) => b.similarity - a.similarity)

  return (
    <div className="not-prose my-8 rounded border border-rule bg-paper p-5 font-sans shadow-sm sm:p-6">
      <div className="flex items-center justify-between border-b border-rule pb-3">
        <div>
          <span className="text-eyebrow font-medium uppercase text-muted">Vector Search & RAG</span>
          <h4 className="text-section font-serif text-ink">Cosine Similarity & Vector Space Topology</h4>
        </div>
        <span className="text-caption font-mono text-muted">Threshold: {threshold}</span>
      </div>

      <div className="mt-5 grid gap-6 sm:grid-cols-2">
        {/* Vector 2D Plane SVG */}
        <div className="relative aspect-square w-full rounded border border-rule bg-paper-sunken flex items-center justify-center">
          <svg viewBox="0 0 400 400" className="h-full w-full">
            {/* Grid Axes */}
            <line x1="200" y1="0" x2="200" y2="400" stroke="#ddd6c9" strokeWidth="1.5" />
            <line x1="0" y1="200" x2="400" y2="200" stroke="#ddd6c9" strokeWidth="1.5" />

            {/* Document Vector Points */}
            {ranked.map((p) => {
              const cx = toCanvas(p.x)
              const cy = toCanvas(-p.y) // Invert Y for Cartesian
              const isMatch = p.similarity >= threshold

              return (
                <g key={p.id} className="transition-all duration-150">
                  <line
                    x1="200"
                    y1="200"
                    x2={cx}
                    y2={cy}
                    stroke={isMatch ? '#2d4a72' : '#c4bbaa'}
                    strokeWidth={isMatch ? 2 : 1}
                    strokeDasharray={isMatch ? 'none' : '3,3'}
                  />
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isMatch ? 7 : 5}
                    fill={isMatch ? '#2d4a72' : '#6d6558'}
                    className="cursor-pointer"
                  />
                  <text
                    x={cx + 10}
                    y={cy + 4}
                    fontSize="11"
                    fontFamily="monospace"
                    fill={isMatch ? '#1a1714' : '#6d6558'}
                    fontWeight={isMatch ? 'bold' : 'normal'}
                  >
                    {p.label} ({p.similarity})
                  </text>
                </g>
              )
            })}

            {/* Query Vector Point (Red / Accent) */}
            <g>
              <line
                x1="200"
                y1="200"
                x2={toCanvas(query.x)}
                y2={toCanvas(-query.y)}
                stroke="#9c3328"
                strokeWidth="2.5"
              />
              <circle
                cx={toCanvas(query.x)}
                cy={toCanvas(-query.y)}
                r="8"
                fill="#9c3328"
                className="cursor-grab active:cursor-grabbing"
              />
              <text
                x={toCanvas(query.x) + 12}
                y={toCanvas(-query.y) + 4}
                fontSize="12"
                fontFamily="sans-serif"
                fill="#9c3328"
                fontWeight="bold"
              >
                ★ {query.label}
              </text>
            </g>
          </svg>
        </div>

        {/* Controls and Retrieval Ranking List */}
        <div className="flex flex-col justify-between">
          <div>
            <span className="text-caption font-medium text-ink-soft">Adjust Query Vector Position:</span>
            <div className="mt-3 space-y-3">
              <div>
                <div className="flex justify-between text-[11px] font-mono text-muted">
                  <span>Dimension X (Semantic Bias)</span>
                  <span>{query.x.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="-1"
                  max="1"
                  step="0.05"
                  value={query.x}
                  onChange={(e) => setQuery((q) => ({ ...q, x: Number(e.target.value) }))}
                  className="w-full accent-[#9c3328] cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-[11px] font-mono text-muted">
                  <span>Dimension Y (Context Drift)</span>
                  <span>{query.y.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="-1"
                  max="1"
                  step="0.05"
                  value={query.y}
                  onChange={(e) => setQuery((q) => ({ ...q, y: Number(e.target.value) }))}
                  className="w-full accent-[#9c3328] cursor-pointer"
                />
              </div>

              <div className="border-t border-rule pt-3">
                <div className="flex justify-between text-[11px] font-mono text-muted">
                  <span>Similarity Cutoff (Top-K Filter)</span>
                  <span>&ge; {threshold.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full accent-accent cursor-pointer"
                />
              </div>
            </div>
          </div>

          {/* Ranked Neighbors */}
          <div className="mt-4 rounded border border-rule bg-paper-raised p-3">
            <span className="text-[11px] font-mono uppercase text-muted block mb-2 font-semibold">
              Retrieved Neighbors (Score &ge; {threshold}):
            </span>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {ranked.map((p, idx) => {
                const passed = p.similarity >= threshold
                return (
                  <div
                    key={p.id}
                    className={`flex items-center justify-between text-caption font-mono py-1 px-2 rounded ${
                      passed ? 'bg-accent/10 text-accent font-semibold' : 'text-muted opacity-50'
                    }`}
                  >
                    <span>{idx + 1}. {p.label}</span>
                    <span>{p.similarity.toFixed(2)}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
