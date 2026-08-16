import type { AnalysisReport, Diagnostic } from '../../lib/ipc'

/**
 * Static analysis results.
 *
 * Errors first, then warnings, because that is the order a person fixes them
 * in. Each row is clickable and jumps the editor to the line, which is the
 * whole point of showing a line number.
 */
export function Diagnostics({
  report,
  running,
  onSelect,
}: {
  report: AnalysisReport | null
  running: boolean
  onSelect: (file: string, line: number) => void
}) {
  if (running) {
    return <Empty>Checking…</Empty>
  }

  if (!report) {
    return <Empty>Run a check to see problems here.</Empty>
  }

  if (report.runnerError) {
    return (
      <div role="alert" className="px-4 py-3 text-caption text-fail">
        {report.runnerError}
      </div>
    )
  }

  if (report.diagnostics.length === 0) {
    return (
      <Empty>
        Nothing to report across {report.filesChecked}{' '}
        {report.filesChecked === 1 ? 'file' : 'files'}.
        <span className="mt-1 block text-muted">
          Static checks pass. Whether the agent behaves well is a different
          question, and only a real model can answer it.
        </span>
      </Empty>
    )
  }

  const errors = report.diagnostics.filter((d) => d.severity === 'error').length

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <p className="border-b border-rule px-4 py-2 text-caption text-muted">
        {errors > 0
          ? `${errors} ${errors === 1 ? 'error' : 'errors'} to fix before this runs`
          : 'No errors'}
        {report.diagnostics.length > errors &&
          `, ${report.diagnostics.length - errors} worth a look`}
        {' · '}
        {report.filesChecked} {report.filesChecked === 1 ? 'file' : 'files'} in{' '}
        {report.durationMs}ms
      </p>

      <ul>
        {report.diagnostics.map((diagnostic, index) => (
          <Row
            key={`${diagnostic.file}:${diagnostic.line}:${diagnostic.rule}:${index}`}
            diagnostic={diagnostic}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </div>
  )
}

function Row({
  diagnostic,
  onSelect,
}: {
  diagnostic: Diagnostic
  onSelect: (file: string, line: number) => void
}) {
  const isError = diagnostic.severity === 'error'

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(diagnostic.file, diagnostic.line)}
        className="flex w-full gap-3 border-b border-rule px-4 py-2.5 text-left transition-colors duration-150 ease-paper hover:bg-paper-sunken"
      >
        <span
          aria-hidden
          className={`mt-1.5 size-1.5 shrink-0 rounded-full ${isError ? 'bg-fail' : 'bg-warn'}`}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-caption text-ink">{diagnostic.message}</span>
          <span className="mt-0.5 block font-mono text-[11px] text-muted">
            {diagnostic.file}:{diagnostic.line}
            {'  '}
            <span className="text-muted">{diagnostic.rule}</span>
          </span>
        </span>
      </button>
    </li>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="px-4 py-6 text-caption text-muted">{children}</p>
}
