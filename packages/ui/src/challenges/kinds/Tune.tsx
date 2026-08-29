'use client'

import { evaluateTune, type TuneChallenge, type TuneReadings } from '@atlas/core'

import type { ChallengeRenderer } from '../protocol'
import { Mark } from './chrome'

/** Two decimals at most, and no trailing zeros to read past. */
function show(value: number): string {
  if (Number.isInteger(value)) return String(value)
  return value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

function windowOf(target: { min?: number; max?: number }): string {
  if (target.min !== undefined && target.max !== undefined) {
    return `${show(target.min)} to ${show(target.max)}`
  }
  if (target.min !== undefined) return `at least ${show(target.min)}`
  if (target.max !== undefined) return `at most ${show(target.max)}`
  return 'anything'
}

/**
 * Move the inputs, watch the outputs.
 *
 * The outputs come from `evaluateTune`, the same function the runner grades
 * with, so what a learner watches move is what they are eventually checked
 * against. The in-range mark repeats that comparison for display; it decides
 * nothing, and pressing Check is still what settles the challenge.
 */
export const Tune: ChallengeRenderer<TuneChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
}) => {
  const given = (answer ?? {}) as TuneReadings
  const inputs: TuneReadings = Object.fromEntries(
    challenge.inputs.map((input) => [input.id, given[input.id] ?? input.initial]),
  )
  const readings = evaluateTune(challenge, inputs)

  return (
    <div>
      <div className="space-y-5">
        {challenge.inputs.map((input) => {
          const id = `${challenge.id}-${input.id}`
          const value = inputs[input.id]!
          return (
            <div key={input.id}>
              <div className="flex items-baseline justify-between gap-4">
                <label htmlFor={id} className="text-caption text-ink">
                  {input.label}
                </label>
                <output htmlFor={id} className="font-mono text-caption text-ink">
                  {show(value)}
                  {input.unit && <span className="text-muted"> {input.unit}</span>}
                </output>
              </div>

              <input
                id={id}
                type="range"
                min={input.min}
                max={input.max}
                step={input.step}
                value={value}
                disabled={settled}
                onChange={(event) =>
                  onAnswer({ ...inputs, [input.id]: Number(event.target.value) })
                }
                className="mt-1 block min-h-11 w-full accent-accent"
              />

              <div className="flex justify-between font-mono text-eyebrow uppercase text-muted">
                <span>{show(input.min)}</span>
                <span>{show(input.max)}</span>
              </div>
            </div>
          )
        })}
      </div>

      <dl className="mt-6 divide-y divide-rule border-t border-rule-strong">
        {challenge.outputs.map((output) => {
          const value = readings[output.id] ?? 0
          const target = output.target
          const inside =
            !target ||
            ((target.min === undefined || value >= target.min) &&
              (target.max === undefined || value <= target.max))

          return (
            <div key={output.id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-3">
              <dt className="grow text-caption text-ink">{output.label}</dt>

              <dd className="font-mono text-section text-ink">
                {show(value)}
                {output.unit && <span className="text-caption text-muted"> {output.unit}</span>}
              </dd>

              <dd className="w-full font-mono text-eyebrow uppercase text-muted">
                {target ? (
                  <>
                    <Mark tone={inside ? 'pass' : 'fail'} className="mr-2">
                      {inside ? 'in range' : 'out of range'}
                    </Mark>
                    target {windowOf(target)}
                  </>
                ) : (
                  <Mark tone="quiet">not graded</Mark>
                )}
              </dd>
            </div>
          )
        })}
      </dl>
    </div>
  )
}
