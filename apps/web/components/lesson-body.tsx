import { InteractiveRenderer } from '@atlas/ui'

export function LessonBody({ html }: { html: string }) {
  return <InteractiveRenderer html={html} className="prose-learn" />
}

