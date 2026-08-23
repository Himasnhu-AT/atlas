import { findLessonRef, type LessonRef } from './content'

/**
 * The lesson the learner had open when they last closed the window, so the app
 * reopens where they left off rather than at lesson one.
 */

// Bumped when the stored value gained a course segment. An old two-part value
// read by the three-part parser would resolve to nothing and silently send the
// learner back to lesson one, so the key changes rather than the parser guessing.
const STORAGE_KEY = 'learn.desktop.lastLesson.v2'

export function rememberLesson(ref: LessonRef): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, `${ref.course.slug}/${ref.module.slug}/${ref.lesson.slug}`)
  } catch (error) {
    console.warn('[desktop] could not remember the current lesson', error)
  }
}

export function recallLesson(): LessonRef | undefined {
  if (typeof localStorage === 'undefined') return undefined
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return undefined
    const [courseSlug, moduleSlug, lessonSlug] = raw.split('/')
    return findLessonRef(courseSlug, moduleSlug, lessonSlug)
  } catch {
    return undefined
  }
}
