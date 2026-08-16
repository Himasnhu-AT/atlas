import { findLessonRef, type LessonRef } from './content'

/**
 * The lesson the learner had open when they last closed the window, so the app
 * reopens where they left off rather than at lesson one.
 */

const STORAGE_KEY = 'learn.desktop.lastLesson'

export function rememberLesson(ref: LessonRef): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, `${ref.module.slug}/${ref.lesson.slug}`)
  } catch (error) {
    console.warn('[desktop] could not remember the current lesson', error)
  }
}

export function recallLesson(): LessonRef | undefined {
  if (typeof localStorage === 'undefined') return undefined
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return undefined
    const [moduleSlug, lessonSlug] = raw.split('/')
    return findLessonRef(moduleSlug, lessonSlug)
  } catch {
    return undefined
  }
}
