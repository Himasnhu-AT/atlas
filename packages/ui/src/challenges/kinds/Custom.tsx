'use client'

import type { CustomChallenge } from '@atlas/core'

import type { ChallengeRenderer } from '../protocol'
import { WidgetRegistry } from '../../widgets/registry'
import { quietButton } from './chrome'

/**
 * The escape hatch: a bespoke component, addressed through the same door.
 *
 * A component name that is not registered renders a notice rather than nothing.
 * A silent `null` here is a lesson that looks finished and teaches nothing, and
 * it is a bug this repo has already shipped once.
 */
export const Custom: ChallengeRenderer<CustomChallenge> = ({
  challenge,
  onVerdict,
  settled,
  verdict,
}) => {
  const Widget = WidgetRegistry[challenge.component]

  if (!Widget) {
    return (
      <div className="rounded-sheet border border-warn bg-warn-wash p-4 text-caption text-ink">
        <p className="font-mono text-eyebrow uppercase text-warn">Component not registered</p>
        <p className="mt-2">
          This challenge asks for <span className="font-mono">{challenge.component}</span>, which is
          not in <span className="font-mono">packages/ui/src/widgets/registry.ts</span>. Register it
          there, or correct the name in the lesson.
        </p>
        <p className="mt-2 font-mono text-muted">
          Registered: {Object.keys(WidgetRegistry).sort().join(', ')}
        </p>
      </div>
    )
  }

  return (
    <div>
      <Widget {...challenge.props} />

      {/* A bespoke component owns its own simulation, and none of the eight in
          the registry reports a verdict yet. Without a way to say the work is
          done, a `custom` step is the end of the lesson rather than a part of
          it. The runner still records the attempt and shows the reveal. */}
      {!settled && !verdict?.passed && onVerdict && (
        <div className="mt-6 border-t border-rule pt-4">
          <p className="text-caption text-muted">
            This one has no automatic check. Work through it above, then carry on.
          </p>
          <button
            type="button"
            onClick={() => onVerdict({ passed: true })}
            className={`${quietButton} mt-3`}
          >
            Done here
          </button>
        </div>
      )}
    </div>
  )
}
