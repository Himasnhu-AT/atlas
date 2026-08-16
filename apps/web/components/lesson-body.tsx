/**
 * Renders a lesson body.
 *
 * The content build already turned markdown into HTML with syntax highlighting
 * applied, so this is an insertion rather than a render. The HTML comes from
 * our own build of our own files in this repo, never from user input, which is
 * what makes it safe to insert directly.
 */
export function LessonBody({ html }: { html: string }) {
  return <div className="prose-learn" dangerouslySetInnerHTML={{ __html: html }} />
}
