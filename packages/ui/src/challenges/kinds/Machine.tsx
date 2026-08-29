'use client'

import { useState } from 'react'
import {
  machineStart,
  offeredActions,
  stepMachine,
  type MachineChallenge,
  type MachineState,
} from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { Mark, quietButton } from './chrome'

interface Step {
  on: string
  to: string
  /** `predict` mode only: the state they named before it moved. */
  predicted?: string
}

/**
 * Drive a machine to its goal, or predict where each action lands.
 *
 * Every move goes through `stepMachine`, so the guards, the effects and the
 * step count are the same ones the content build walked when it proved the goal
 * was reachable. The trace is the exception and it is local state: it is a
 * record of this sitting rather than part of the answer, and `checkMachine`
 * reads only where the machine is and what its counters say.
 */
export const Machine: ChallengeRenderer<MachineChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
}) => {
  const state = (answer ?? machineStart(challenge)) as MachineState
  const [trace, setTrace] = useState<Step[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [called, setCalled] = useState<{ guess: string; actual: string; note?: string } | null>(null)

  const actions = offeredActions(challenge, state)
  const here = challenge.states[state.at]
  const spent = state.steps >= challenge.win.maxSteps

  const nameOf = (id: string) => challenge.states[id]?.label ?? id

  const apply = (on: string, predicted?: string) => {
    const transition = actions.find((candidate) => candidate.on === on)
    if (!transition) return
    onAnswer(stepMachine(challenge, state, on))
    setTrace((previous) => [...previous, { on, to: transition.to, predicted }])
  }

  const take = (on: string) => {
    setCalled(null)
    if (challenge.mode === 'predict') {
      setPending(on)
      return
    }
    apply(on)
  }

  // A wrong call is not a dead end. The machine moves either way and the
  // transition's own note is the correction, so a run never stalls on a guess.
  const call = (guess: string) => {
    const on = pending
    setPending(null)
    if (!on) return
    const transition = actions.find((candidate) => candidate.on === on)
    if (!transition) return

    setCalled({ guess, actual: transition.to, note: transition.note })
    apply(on, guess)
  }

  const restart = () => {
    onAnswer(machineStart(challenge))
    setTrace([])
    setPending(null)
    setCalled(null)
  }

  return (
    <div>
      <ol className="flex flex-wrap gap-2">
        {Object.entries(challenge.states).map(([id, node]) => {
          const current = id === state.at
          return (
            <li
              key={id}
              aria-current={current ? 'step' : undefined}
              className={cn(
                'rounded-field border px-3 py-2',
                current ? 'border-accent bg-accent-wash' : 'border-rule bg-paper',
              )}
            >
              <span className="block font-mono text-eyebrow uppercase text-muted">{id}</span>
              <span className="block text-caption text-ink">{node.label}</span>
              {current && <Mark tone="quiet">here now</Mark>}
              {!current && node.error && <Mark tone="fail">error state</Mark>}
            </li>
          )
        })}
      </ol>

      {here?.note && <p className="mt-4 text-caption text-ink-soft">{here.note}</p>}

      <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3 border-y border-rule py-4">
        {Object.entries(state.vars).map(([name, value]) => (
          <div key={name}>
            <dt className="font-mono text-eyebrow uppercase text-muted">{name}</dt>
            <dd className="font-mono text-section text-ink">{value}</dd>
          </div>
        ))}
        <div>
          <dt className="font-mono text-eyebrow uppercase text-muted">Steps</dt>
          <dd className={cn('font-mono text-section', spent ? 'text-fail' : 'text-ink')}>
            {state.steps} of {challenge.win.maxSteps}
          </dd>
        </div>
      </dl>

      {pending ? (
        <div className="mt-5 rounded-sheet border border-rule-strong bg-paper-sunken p-4">
          <p className="text-caption text-ink">
            Where does <span className="font-mono">{pending}</span> land?
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(challenge.states).map(([id, node]) => (
              <button
                key={id}
                type="button"
                onClick={() => call(id)}
                className={quietButton}
              >
                {node.label}
              </button>
            ))}
            <button type="button" onClick={() => setPending(null)} className="min-h-11 px-2 font-mono text-caption text-muted transition-colors duration-200 ease-paper hover:text-ink">
              Never mind
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-5 flex flex-wrap gap-2">
          {actions.map((action) => (
            <button
              key={`${action.on}-${action.to}`}
              type="button"
              onClick={() => take(action.on)}
              disabled={settled}
              className="inline-flex min-h-11 items-center gap-2 rounded-field bg-accent px-4 text-caption font-medium text-white transition-colors duration-200 ease-paper hover:bg-accent-deep disabled:bg-rule-strong"
            >
              <span className="font-mono">{action.on}</span>
              {/* In predict mode the destination is the question, so it is not
                  printed on the button that asks it. */}
              {challenge.mode === 'drive' && (
                <span className="opacity-75">
                  <span aria-hidden="true">&rarr; </span>
                  {nameOf(action.to)}
                </span>
              )}
            </button>
          ))}

          {actions.length === 0 && (
            <p className="text-caption text-ink-soft">
              Nothing is available from here. Start again to take a different route.
            </p>
          )}

          <button type="button" onClick={restart} disabled={settled} className={quietButton}>
            Start again
          </button>
        </div>
      )}

      {called && (
        <p className="mt-4 text-caption text-ink-soft">
          <Mark tone={called.guess === called.actual ? 'pass' : 'fail'} className="mr-2">
            {called.guess === called.actual ? 'called it' : 'not that one'}
          </Mark>
          {called.guess === called.actual
            ? `It went to ${nameOf(called.actual)}.`
            : `You said ${nameOf(called.guess)}. It went to ${nameOf(called.actual)}.`}
          {called.note && ` ${called.note}`}
        </p>
      )}

      <ol className="mt-5 rounded-sheet bg-paper-sunken px-4 py-3 font-mono text-caption text-ink-soft">
        <li>{nameOf(challenge.initial)}</li>
        {trace.map((step, position) => (
          <li key={position}>
            <span aria-hidden="true">&rarr; </span>
            {step.on} lands in {nameOf(step.to)}
            {step.predicted && step.predicted !== step.to && ` (you said ${nameOf(step.predicted)})`}
          </li>
        ))}
      </ol>
    </div>
  )
}
