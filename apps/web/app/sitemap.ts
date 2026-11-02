import type { MetadataRoute } from 'next'

import { activeCourses, activeModules } from '@/lib/content'
import { SITE_URL } from '@/lib/site'

/**
 * Every course and module page, and the lessons a signed-out reader can open.
 * A lesson behind a prerequisite is not listed: a crawler is signed out, so the
 * gate would show it the locked page rather than the lesson.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const urls = ['/', '/learn', '/download']
  for (const course of activeCourses()) {
    urls.push(`/learn/${course.slug}`)
    for (const module of activeModules(course)) {
      urls.push(`/learn/${course.slug}/${module.slug}`)
      if (module.prerequisites.length > 0) continue
      for (const lesson of module.lessons) {
        urls.push(`/learn/${course.slug}/${module.slug}/${lesson.slug}`)
      }
    }
  }
  return urls.map((path) => ({ url: `${SITE_URL}${path === '/' ? '' : path}` }))
}
