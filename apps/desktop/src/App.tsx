import { Navigate, Route, Routes } from 'react-router-dom'

import Practice from './pages/Practice'
import ProjectPage from './pages/Project'
import { firstLessonRef, practicePath } from './lib/content'
import { recallLesson } from './lib/recent'

/**
 * The desktop app is one screen: the practice IDE.
 *
 * There is no marketing site and no catalogue here; those live in apps/web. And
 * there is no sign-in gate, because the app is offline-first by design. The
 * course and every exercise are bundled, tests run locally, and progress is
 * kept on this machine. An account only ever adds cross-device sync, so it must
 * never be the thing standing between a learner and lesson one.
 */
export default function App() {
  return (
    <Routes>
      <Route index element={<ResumeRedirect />} />
      <Route path="practice/:moduleSlug/:lessonSlug" element={<Practice />} />
      <Route path="project" element={<ProjectPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

/** Reopen the lesson from last session, or start at the beginning. */
function ResumeRedirect() {
  const target = recallLesson() ?? firstLessonRef

  if (!target) {
    return (
      <div className="flex h-full items-center justify-center bg-paper px-6 text-center">
        <p className="max-w-sm text-sm text-ink-soft">
          No lessons are bundled with this build. Run{' '}
          <code className="font-mono">pnpm --filter @learn/learning build</code> and start the
          app again.
        </p>
      </div>
    )
  }

  return <Navigate to={practicePath(target.module.slug, target.lesson.slug)} replace />
}
