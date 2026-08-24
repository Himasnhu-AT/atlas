import 'server-only'

import type { CourseEntry, ModuleEntry } from '@atlas/learning'

import { store } from './store'

/**
 * What a reader may open, and why.
 *
 * One function, used by every surface that could leak content: the lesson page,
 * the exercise files, and anything added later. A boundary spread across route
 * handlers is a boundary with a hole in it, and the hole is always the newest
 * handler.
 *
 * The rule is progression, not payment. A module opens when the modules it
 * declares as prerequisites are finished. There is nothing to buy, no plan, and
 * no track that is worth more than another.
 *
 * That rule was already on the screen before it was enforced. `moduleStatus` in
 * `@atlas/core` has always computed a locked state from prerequisites, and the
 * dashboard has always drawn "Opens after Foundations" underneath a module a
 * reader had not reached. It was advice. This makes it the answer.
 *
 * ## What this does not cover, and why that is written down here
 *
 * The desktop app bundles every lesson at build time so it works with no
 * network, so this gate does not reach it. That matters much less than it did
 * when the gate decided what somebody had paid for: skipping ahead in the
 * practice app costs the learner their own footing and nobody else anything.
 * The web is where the sequence is enforced, and the desktop is a place to
 * practise what you have reached.
 */

export interface Access {
  /** Signed in at all. Reading is open to everyone; this is about how far. */
  signedIn: boolean
  /**
   * Module ids this reader has finished.
   *
   * Empty when signed out, which is not a special case: a reader with no
   * progress has finished nothing, so they get exactly the modules that ask for
   * nothing. Every course starts with one.
   */
  completed: Set<string>
}

export async function accessFor(userId: string | undefined): Promise<Access> {
  if (!userId) return { signedIn: false, completed: new Set() }

  const snapshot = await store().progressFor(userId)
  return {
    signedIn: true,
    completed: new Set(
      snapshot.modules.filter((row) => row.status === 'completed').map((row) => row.moduleId),
    ),
  }
}

/**
 * May this reader open this module?
 *
 * Note what is NOT gated: the catalogue, the map, a module's lesson list, and
 * every lesson's title and summary. Somebody deciding what to learn next has to
 * be able to see where the road goes, and a course whose table of contents is
 * hidden until you have earned it reads as a puzzle rather than a syllabus.
 *
 * What is gated is the lesson body and the exercise files, so that arriving at
 * module nine on your first day is not a thing that happens by accident.
 *
 * Prerequisites cannot cross a course boundary, so this never has to look
 * outside the course it was handed.
 */
export function canOpen(access: Access, course: CourseEntry, module: ModuleEntry): boolean {
  void course
  return module.prerequisites.every((id) => access.completed.has(id))
}

/**
 * The modules standing between this reader and that one, nearest first.
 *
 * Only the direct prerequisites, not the whole ancestry. Telling somebody on
 * module one that they must finish eight modules is true and useless; telling
 * them the one thing to do next is what they can act on.
 */
export function blockedBy(
  access: Access,
  course: CourseEntry,
  module: ModuleEntry,
): ModuleEntry[] {
  const missing = module.prerequisites.filter((id) => !access.completed.has(id))
  return course.modules.filter((candidate) => missing.includes(candidate.id))
}
