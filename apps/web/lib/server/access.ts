import 'server-only'

import type { CourseEntry, ModuleEntry } from '@atlas/learning'

import { activeCourses } from '@/lib/content'
import { store } from './store'

/**
 * What a plan may open.
 *
 * One function, used by every surface that could leak content: the lesson page,
 * the exercise files, and anything added later. A boundary spread across route
 * handlers is a boundary with a hole in it, and the hole is always the newest
 * handler.
 *
 * There is no payment provider behind this. `users.plan` is set by hand until
 * there is something worth charging for, and writing a Stripe integration
 * before then is a guess with webhooks attached. What matters now is that the
 * decision lives in one place.
 *
 * ## What this does not cover, and why that is written down here
 *
 * The desktop app bundles every lesson at build time so it works with no
 * network, which means this gate does not apply to it. That is not an oversight
 * to fix with a client-side check — a check in the app is advice, and the
 * content is already on the machine.
 *
 * The place it can be enforced is the content sync: ship the free modules in the
 * bundle and fetch the rest with the device's token, so the server decides. That
 * is a real change to how content reaches the desktop and it belongs with
 * whatever pays for it, so it is named here rather than half-built.
 */

/**
 * The free part of every course is its first track.
 *
 * Deliberately per course rather than "the first course is free". A learner who
 * arrives for data engineering should not have to work through an AI curriculum
 * to see whether they like the product, and a catalogue where most courses are
 * entirely locked reads as a brochure.
 *
 * A course's first declared track is the free one, which makes this a content
 * decision expressed in `course.yaml` rather than a list of ids maintained here
 * that would go stale the first time somebody adds a course.
 */
export function freeTrackOf(course: CourseEntry): string | undefined {
  return course.tracks[0]?.id
}

export function isFreeModule(course: CourseEntry, module: ModuleEntry): boolean {
  return module.track === freeTrackOf(course)
}

/** Every module id a free account may open, across every course. */
export function freeModuleIds(): Set<string> {
  const ids = new Set<string>()
  for (const course of activeCourses()) {
    for (const module of course.modules) {
      if (isFreeModule(course, module)) ids.add(module.id)
    }
  }
  return ids
}

export interface Access {
  plan: 'free' | 'member'
  /** Signed in at all. Reading is open to everyone; this is about what. */
  signedIn: boolean
}

export async function accessFor(userId: string | undefined): Promise<Access> {
  if (!userId) return { plan: 'free', signedIn: false }
  const user = await store().findUserById(userId)
  return { plan: user?.plan ?? 'free', signedIn: Boolean(user) }
}

/**
 * May this account open this module?
 *
 * Note what is NOT gated: the catalogue, the map, a module's lesson list, and
 * every lesson's title and summary. Somebody deciding whether to pay has to be
 * able to see what they would be paying for, and a locked table of contents is
 * a worse advert than an open one.
 *
 * What is gated is the lesson body and the exercise files, which is the thing
 * with the value in it.
 */
export function canOpen(access: Access, course: CourseEntry, module: ModuleEntry): boolean {
  return access.plan === 'member' || isFreeModule(course, module)
}
