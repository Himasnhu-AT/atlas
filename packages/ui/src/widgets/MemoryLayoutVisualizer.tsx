'use client'

import { useState } from 'react'

export interface StructField {
  id: string
  name: string
  type: string
  sizeBytes: number
}

export interface MemoryLayoutVisualizerProps {
  alignmentBytes?: number
  fields: StructField[]
  cacheLineBytes?: number
  allowReorder?: boolean
}

export function MemoryLayoutVisualizer({
  alignmentBytes = 8,
  fields: initialFields,
  cacheLineBytes = 64,
  allowReorder = true,
}: MemoryLayoutVisualizerProps) {
  const [fields, setFields] = useState<StructField[]>(initialFields)

  // Compute offsets and padding
  let currentOffset = 0
  const layoutSegments: Array<{
    field?: StructField
    offset: number
    size: number
    isPadding: boolean
  }> = []

  fields.forEach((field) => {
    // Alignment required for field
    const fieldAlign = Math.min(field.sizeBytes, alignmentBytes)
    const padding = (fieldAlign - (currentOffset % fieldAlign)) % fieldAlign
    if (padding > 0) {
      layoutSegments.push({
        offset: currentOffset,
        size: padding,
        isPadding: true,
      })
      currentOffset += padding
    }
    layoutSegments.push({
      field,
      offset: currentOffset,
      size: field.sizeBytes,
      isPadding: false,
    })
    currentOffset += field.sizeBytes
  })

  // Trailing struct alignment padding
  const trailingPadding = (alignmentBytes - (currentOffset % alignmentBytes)) % alignmentBytes
  if (trailingPadding > 0) {
    layoutSegments.push({
      offset: currentOffset,
      size: trailingPadding,
      isPadding: true,
    })
    currentOffset += trailingPadding
  }

  const totalStructBytes = currentOffset
  const totalPaddingBytes = layoutSegments.filter((s) => s.isPadding).reduce((a, b) => a + b.size, 0)
  const usefulBytes = totalStructBytes - totalPaddingBytes
  const fitsInCacheLine = totalStructBytes <= cacheLineBytes

  const moveField = (index: number, direction: 'up' | 'down') => {
    if (!allowReorder) return
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= fields.length) return
    const updated = [...fields]
    const temp = updated[index]
    updated[index] = updated[target]
    updated[target] = temp
    setFields(updated)
  }

  return (
    <div className="not-prose my-8 rounded border border-rule bg-paper p-5 font-sans shadow-sm sm:p-6">
      <div className="flex items-center justify-between border-b border-rule pb-3">
        <div>
          <span className="text-eyebrow font-medium uppercase text-muted">Hardware & Memory Model</span>
          <h4 className="text-section font-serif text-ink">Struct Padding & Cache Line Alignment</h4>
        </div>
        <div className="text-right font-mono text-caption">
          <span className="font-semibold text-ink">{totalStructBytes} bytes total</span>
          <span className="ml-2 text-muted">({totalPaddingBytes}B wasted padding)</span>
        </div>
      </div>

      {/* Memory Byte Visualizer Bar */}
      <div className="mt-5">
        <div className="flex justify-between text-caption text-muted mb-1.5 font-mono text-[11px]">
          <span>Memory Byte Offsets (0 .. {totalStructBytes}B)</span>
          <span>64B Cache Line Limit: {Math.round((totalStructBytes / cacheLineBytes) * 100)}%</span>
        </div>

        <div className="flex flex-wrap gap-1 rounded border border-rule-strong bg-paper-sunken p-2">
          {layoutSegments.map((segment, idx) => (
            <div
              key={`${segment.offset}-${idx}`}
              style={{ flexGrow: segment.size }}
              className={`flex flex-col items-center justify-center rounded p-2 text-center transition-all ${
                segment.isPadding
                  ? 'border border-dashed border-fail/40 bg-fail/10 text-fail'
                  : 'border border-accent/40 bg-accent/15 text-accent font-semibold'
              }`}
            >
              <span className="text-[10px] font-mono opacity-80">
                {segment.isPadding ? 'PAD' : segment.field?.type}
              </span>
              <span className="text-caption font-mono font-bold">
                {segment.isPadding ? `+${segment.size}B` : `${segment.field?.name} (${segment.size}B)`}
              </span>
              <span className="text-[9px] font-mono text-muted mt-0.5">
                @{segment.offset}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Field Order Manipulation Table */}
      {allowReorder && (
        <div className="mt-6 border-t border-rule pt-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-caption font-medium text-ink-soft">Field Declaration Order (Reorder to minimize padding):</span>
            {totalPaddingBytes === 0 && (
              <span className="text-caption font-semibold text-pass">Optimal Layout: 0 Padding Bytes!</span>
            )}
          </div>

          <div className="divide-y divide-rule rounded border border-rule bg-paper-raised">
            {fields.map((f, i) => (
              <div key={f.id} className="flex items-center justify-between px-3 py-2 text-caption">
                <div className="flex items-center gap-3 font-mono">
                  <span className="text-muted text-[11px] w-4">{i + 1}.</span>
                  <span className="font-semibold text-ink">{f.name}</span>
                  <span className="text-muted text-[11px]">{f.type} ({f.sizeBytes}B)</span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => moveField(i, 'up')}
                    disabled={i === 0}
                    className="rounded border border-rule px-2 py-0.5 text-xs text-muted hover:text-ink disabled:opacity-30"
                  >
                    &uarr;
                  </button>
                  <button
                    onClick={() => moveField(i, 'down')}
                    disabled={i === fields.length - 1}
                    className="rounded border border-rule px-2 py-0.5 text-xs text-muted hover:text-ink disabled:opacity-30"
                  >
                    &darr;
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Metrics Footer */}
      <div className="mt-4 grid grid-cols-3 gap-2 rounded bg-paper-sunken p-3 text-center text-caption font-mono">
        <div>
          <span className="text-muted block text-[10px]">USEFUL DATA</span>
          <span className="font-bold text-ink">{usefulBytes} Bytes</span>
        </div>
        <div>
          <span className="text-muted block text-[10px]">WASTED PADDING</span>
          <span className={`font-bold ${totalPaddingBytes > 0 ? 'text-fail' : 'text-pass'}`}>
            {totalPaddingBytes} Bytes
          </span>
        </div>
        <div>
          <span className="text-muted block text-[10px]">CACHE LINE STATUS</span>
          <span className={`font-bold ${fitsInCacheLine ? 'text-pass' : 'text-fail'}`}>
            {fitsInCacheLine ? 'Fits 1 Line (64B)' : 'Spans 2 Lines!'}
          </span>
        </div>
      </div>
    </div>
  )
}
