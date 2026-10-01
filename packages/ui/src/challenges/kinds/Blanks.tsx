'use client'

import { useMemo } from 'react'
import type { BlanksChallenge } from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { field } from './chrome'

type Part = { text: string } | { blank: number }

const TOKEN = /\{\{(\d+)\}\}/g

/**
 * Split the template into literal runs and blanks.
 *
 * The runs go inside the same `<pre>` as the controls, so the indentation the
 * author wrote is the indentation the learner reads. Rebuilding the listing
 * line by line and dropping the controls in afterwards loses exactly that.
 */
function partsOf(template: string): Part[] {
  const parts: Part[] = []
  let cursor = 0

  for (const match of template.matchAll(TOKEN)) {
    if (match.index > cursor) parts.push({ text: template.slice(cursor, match.index) })
    parts.push({ blank: Number(match[1]) })
    cursor = match.index + match[0].length
  }
  if (cursor < template.length) parts.push({ text: template.slice(cursor) })

  return parts
}

export const Blanks: ChallengeRenderer<BlanksChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
}) => {
  const given = (answer ?? {}) as Record<number, string>
  const parts = useMemo(() => partsOf(challenge.template), [challenge.template])

  const set = (n: number, value: string) => onAnswer({ ...given, [n]: value })

  return (
    <div>
      <p className="font-mono text-eyebrow uppercase text-muted">{challenge.lang}</p>

      <pre className="mt-2 overflow-x-auto rounded-sheet border border-rule bg-paper-sunken p-4 font-mono text-caption leading-loose text-ink">
        <code>
          {parts.map((part, position) => {
            if ('text' in part) return <span key={position}>{part.text}</span>

            const blank = challenge.blanks.find((candidate) => candidate.n === part.blank)
            // The content build proves every blank in the template is declared,
            // so this only fires for an unvalidated challenge. Showing the token
            // is more honest than silently dropping it.
            if (!blank) return <span key={position}>{`{{${part.blank}}}`}</span>

            const value = given[blank.n] ?? ''
            const common = cn(field, 'mx-1 inline-block align-middle font-mono')

            if (blank.as === 'select') {
              return (
                <select
                  key={position}
                  value={value}
                  disabled={settled}
                  aria-label={`Blank ${blank.n}`}
                  onChange={(event) => set(blank.n, event.target.value)}
                  className={common}
                >
                  <option value="">Choose</option>
                  {blank.options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              )
            }

            return (
              <input
                key={position}
                type="text"
                value={value}
                disabled={settled}
                aria-label={`Blank ${blank.n}`}
                spellCheck={false}
                autoComplete="off"
                // `size` is the one width that comes from the content itself, so
                // the field is as wide as the longest answer it will hold and no
                // hardcoded measurement is involved.
                size={Math.min(24, Math.max(6, ...blank.accept.map((accept) => accept.length)))}
                onChange={(event) => set(blank.n, event.target.value)}
                className={common}
              />
            )
          })}
        </code>
      </pre>
    </div>
  )
}
