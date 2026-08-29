'use client'

import { useState } from 'react'
import type { NumericChallenge } from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { field } from './chrome'

export const Numeric: ChallengeRenderer<NumericChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
}) => {
  // What was typed, kept alongside the number the runner grades. `-` and `1.`
  // are both on the way to a real answer and both parse to something that is
  // not what the field says, so the field cannot be driven from the number.
  const [text, setText] = useState(
    typeof answer === 'number' && Number.isFinite(answer) ? String(answer) : '',
  )

  const change = (value: string) => {
    setText(value)
    onAnswer(value.trim() === '' ? Number.NaN : Number(value))
  }

  const id = `${challenge.id}-answer`

  return (
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor={id} className="font-mono text-eyebrow uppercase text-muted">
        Your answer
      </label>

      <input
        id={id}
        type="number"
        inputMode="decimal"
        step="any"
        value={text}
        disabled={settled}
        autoComplete="off"
        onChange={(event) => change(event.target.value)}
        className={cn(field, 'w-44 font-mono')}
      />

      {challenge.unit && <span className="font-mono text-caption text-muted">{challenge.unit}</span>}
    </div>
  )
}
