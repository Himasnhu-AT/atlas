import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { isDesktop } from '@learn/core'
import { FolderOpen, Play, RotateCw } from 'lucide-react'

import { CodeEditor } from '../components/editor'
import { SplitPane } from '../components/SplitPane'
import { TerminalSlot } from '../components/TerminalSlot'
import { Diagnostics } from '../components/project/Diagnostics'
import { FileTree } from '../components/project/FileTree'
import { errorMessage } from '../lib/errors'
import {
  projectAnalyse,
  projectClose,
  projectCurrent,
  projectOpen,
  projectRead,
  projectWrite,
  type AnalysisReport,
  type Project as ProjectInfo,
} from '../lib/ipc'

/** How long the buffer sits idle before it is written back to the repo. */
const AUTOSAVE_MS = 1200

/**
 * Working on the student's own repository.
 *
 * The exercises are scaffolded, graded, and live in the app's sandbox. A project
 * is the opposite: their code, their layout, their repo, and the app is just an
 * editor with a terminal and a checker attached.
 *
 * Because there is no reference solution here, "correct" is not something this
 * screen can decide. What it can do is tell them whether the code parses and
 * hangs together, which is what the static analysis pane is for, and give them a
 * terminal to run it in.
 */
export default function ProjectPage() {
  const desktop = isDesktop()

  const [project, setProject] = useState<ProjectInfo | null>(null)
  const [activePath, setActivePath] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [analysing, setAnalysing] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // A grant survives restarts, so the app reopens the repo it had last.
  useEffect(() => {
    if (!desktop) return
    void projectCurrent()
      .then(setProject)
      .catch((cause: unknown) => setError(errorMessage(cause)))
  }, [desktop])

  const openFolder = useCallback(async () => {
    setError(null)
    try {
      const chosen = await projectOpen()
      // Null means the student dismissed the picker, which is not an error and
      // must not clear the project they already had open.
      if (!chosen) return

      setProject(chosen)
      setActivePath(null)
      setCode('')
      setReport(null)
      setStatus(`Opened ${chosen.name}`)
    } catch (cause) {
      setError(errorMessage(cause))
    }
  }, [])

  const closeFolder = useCallback(async () => {
    await projectClose()
    setProject(null)
    setActivePath(null)
    setCode('')
    setReport(null)
  }, [])

  const openFile = useCallback(async (path: string) => {
    setError(null)
    try {
      const contents = await projectRead(path)
      setActivePath(path)
      setCode(contents)
      savedRef.current = contents
    } catch (cause) {
      setError(errorMessage(cause))
    }
  }, [])

  /* --------------------------------------------------------------- autosave */

  const savedRef = useRef('')
  useEffect(() => {
    if (!activePath || code === savedRef.current) return

    const timer = setTimeout(() => {
      const pending = code
      void projectWrite(activePath, pending)
        .then(() => {
          savedRef.current = pending
          setStatus('Saved')
        })
        .catch((cause: unknown) => setError(errorMessage(cause)))
    }, AUTOSAVE_MS)

    return () => clearTimeout(timer)
  }, [code, activePath])

  /* ---------------------------------------------------------------- analyse */

  const analyse = useCallback(async () => {
    if (!project || analysing) return

    setAnalysing(true)
    setError(null)
    try {
      // Save first: analysing the previous save while the editor shows
      // something else produces findings that do not match what they see.
      if (activePath && savedRef.current !== code) {
        await projectWrite(activePath, code)
        savedRef.current = code
      }
      setReport(await projectAnalyse(''))
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setAnalysing(false)
    }
  }, [project, analysing, activePath, code])

  /* ----------------------------------------------------------------- render */

  if (!desktop) {
    return (
      <Centered>
        Opening a folder needs the desktop app. In a browser tab there is no
        filesystem to point at.
      </Centered>
    )
  }

  if (!project) {
    return (
      <div className="flex h-full flex-col bg-paper">
        <Header />
        <div className="flex flex-1 items-center justify-center px-8">
          <div className="max-w-[46ch]">
            <h1 className="font-serif text-title text-ink">Open a project</h1>
            <p className="mt-4 text-ink-soft">
              Point the app at a repository on your own machine and it becomes an editor for
              it: file tree, editor, terminal, and a static checker that tells you whether
              your Python holds together.
            </p>
            <p className="mt-4 text-caption text-muted">
              The app can only reach the folder you choose here. Nothing outside it is
              readable, and the grant is dropped whenever you close the project.
            </p>

            <button
              type="button"
              onClick={openFolder}
              className="mt-8 inline-flex min-h-11 items-center gap-2.5 rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent"
            >
              <FolderOpen aria-hidden className="size-4" />
              Choose a folder
            </button>

            {error && (
              <p role="alert" className="mt-5 text-caption text-fail">
                {error}
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <Header
        project={project}
        onOpenFolder={openFolder}
        onCloseFolder={closeFolder}
        onAnalyse={analyse}
        analysing={analysing}
      />

      <div className="min-h-0 flex-1">
        <SplitPane
          direction="horizontal"
          label="Resize the file tree and the editor"
          fraction={0.2}
          onFractionChange={() => {}}
          first={
            <div className="flex h-full min-h-0 flex-col border-r border-rule bg-paper-raised">
              <FileTree activePath={activePath} onOpenFile={openFile} />
            </div>
          }
          second={
            <SplitPane
              direction="horizontal"
              label="Resize the editor and the terminal"
              fraction={0.62}
              onFractionChange={() => {}}
              first={
                <SplitPane
                  direction="vertical"
                  label="Resize the editor and the problem list"
                  fraction={0.68}
                  onFractionChange={() => {}}
                  first={
                    activePath ? (
                      <CodeEditor
                        value={code}
                        language="python"
                        onChange={setCode}
                        onRun={() => void analyse()}
                        ariaLabel={`Editing ${activePath}`}
                      />
                    ) : (
                      <Centered>Choose a file to start editing.</Centered>
                    )
                  }
                  second={
                    <div className="flex h-full min-h-0 flex-col border-t border-rule bg-paper-raised">
                      <p className="border-b border-rule px-4 py-2 text-eyebrow font-medium uppercase text-muted">
                        Problems
                      </p>
                      <Diagnostics
                        report={report}
                        running={analysing}
                        onSelect={(file) => void openFile(file)}
                      />
                    </div>
                  }
                />
              }
              second={
                <TerminalSlot
                  available
                  onSessionChange={() => {}}
                  onError={setError}
                  onCollapse={() => {}}
                />
              }
            />
          }
        />
      </div>

      <footer className="flex shrink-0 items-center gap-3 border-t border-rule px-4 py-1.5 text-caption text-muted">
        <span className="truncate font-mono text-[11px]">{project.path}</span>
        {activePath && <span className="truncate">· {activePath}</span>}
        <span className="ml-auto">{error ?? status ?? ''}</span>
      </footer>
    </div>
  )
}

function Header({
  project,
  onOpenFolder,
  onCloseFolder,
  onAnalyse,
  analysing,
}: {
  project?: ProjectInfo
  onOpenFolder?: () => void
  onCloseFolder?: () => void
  onAnalyse?: () => void
  analysing?: boolean
} = {}) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-rule px-4">
      <Link
        to="/"
        className="inline-flex min-h-9 items-center text-caption text-ink-soft transition-colors duration-200 ease-paper hover:text-ink"
      >
        &larr; Lessons
      </Link>

      {project && (
        <>
          <span className="font-serif text-ink">{project.name}</span>

          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={onAnalyse}
              disabled={analysing}
              className="inline-flex min-h-9 items-center gap-2 rounded-field border border-rule px-3 text-caption text-ink transition-colors duration-200 ease-paper hover:bg-paper-sunken disabled:opacity-60"
            >
              {analysing ? (
                <RotateCw aria-hidden className="size-3.5 animate-spin" />
              ) : (
                <Play aria-hidden className="size-3.5" />
              )}
              Check code
            </button>
            <button
              type="button"
              onClick={onOpenFolder}
              className="inline-flex min-h-9 items-center rounded-field border border-rule px-3 text-caption text-ink transition-colors duration-200 ease-paper hover:bg-paper-sunken"
            >
              Change folder
            </button>
            <button
              type="button"
              onClick={onCloseFolder}
              className="inline-flex min-h-9 items-center px-2 text-caption text-muted transition-colors duration-200 ease-paper hover:text-ink"
            >
              Close
            </button>
          </div>
        </>
      )}
    </header>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center bg-paper px-8 text-center">
      <p className="max-w-[44ch] text-caption text-muted">{children}</p>
    </div>
  )
}
