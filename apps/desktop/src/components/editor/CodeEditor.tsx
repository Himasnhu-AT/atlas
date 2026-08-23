import { useEffect, useRef } from 'react'
import {
  Annotation,
  Compartment,
  EditorSelection,
  EditorState,
  Prec,
  type ChangeSpec,
  type Extension,
} from '@codemirror/state'
import { EditorView, keymap, type KeyBinding } from '@codemirror/view'
import { basicSetup } from 'codemirror'
import { python } from '@codemirror/lang-python'
import type { ExerciseLanguage as Language } from '@atlas/learning'
import { cn } from '@atlas/ui'

/**
 * Width of one indentation step, in spaces.
 *
 * This deliberately matches CodeMirror's built-in `indentUnit` default, which is
 * what `basicSetup`'s auto-indent (`indentOnInput`, Enter inside a block) uses.
 * Manual Tab and automatic re-indentation therefore always agree.
 */
const INDENT_SIZE = 2
const INDENT = ' '.repeat(INDENT_SIZE)

/**
 * Marks transactions that carry a `value` prop change *into* the editor, so the
 * update listener can tell them apart from real user edits and not echo them
 * back out through `onChange`.
 */
const External = Annotation.define<boolean>()

// Module-level compartments are safe to share: a compartment is only a key, and
// its contents live in each EditorState.
const languageConf = new Compartment()
const themeConf = new Compartment()
const editableConf = new Compartment()

/**
 * Syntax mode per lesson language.
 *
 * `bash` has no grammar package in this app's dependency set, so shell exercises
 * get the full editor (history, search, brackets, keymaps) without token
 * colouring rather than a wrong grammar's colouring.
 */
function languageExtension(language: Language): Extension {
  switch (language) {
    case 'python':
      return python()
    case 'bash':
      return []
    default:
      return []
  }
}

/**
 * The editor, set on paper. Warm ground and low-chroma syntax so a buffer sits
 * beside the lesson rather than looking like a different application. There is
 * one theme, matching the product.
 *
 * Was:
 * recognisably the same editor. `basicSetup` contributes
 * `defaultHighlightStyle` as a fallback, which supplies the token colours here.
 */
const paperTheme: Extension = EditorView.theme(
  {
    '&': {
      color: '#383a42',
      backgroundColor: '#fafafa',
    },
    '.cm-content': {
      caretColor: '#526fff',
    },
    '.cm-cursor, .cm-dropCursor': {
      borderLeftColor: '#526fff',
    },
    '&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection':
      {
        backgroundColor: '#dcdfe6',
      },
    '.cm-activeLine': {
      backgroundColor: '#f0f0f1',
    },
    '.cm-gutters': {
      backgroundColor: '#fafafa',
      color: '#9d9d9f',
      border: 'none',
      borderRight: '1px solid #e8e8ea',
    },
    '.cm-activeLineGutter': {
      backgroundColor: '#f0f0f1',
      color: '#383a42',
    },
    '.cm-selectionMatch': {
      backgroundColor: '#e3e6ee',
    },
    '&.cm-focused .cm-matchingBracket, &.cm-focused .cm-nonmatchingBracket': {
      backgroundColor: '#e3e6ee',
      outline: '1px solid #b0b3b9',
    },
    '.cm-panels': {
      backgroundColor: '#f0f0f1',
      color: '#383a42',
    },
    '.cm-tooltip': {
      backgroundColor: '#ffffff',
      border: '1px solid #d3d3d6',
      color: '#383a42',
    },
    '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
      backgroundColor: '#dcdfe6',
      color: '#383a42',
    },
  },
  { dark: false },
)

/** Sizing + typography that both themes share. */
const baseTheme: Extension = EditorView.theme({
  '&': {
    height: '100%',
    fontSize: '13px',
  },
  '.cm-scroller': {
    fontFamily: 'var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace)',
    lineHeight: '1.6',
    overflow: 'auto',
  },
  '.cm-content': {
    paddingBlock: '0.75rem',
  },
  '.cm-gutters': {
    userSelect: 'none',
  },
  '&.cm-focused': {
    outline: 'none',
  },
})

/** Indent every line touched by the selection. */
function indentLines(view: EditorView, dedent: boolean): boolean {
  const { state } = view
  const changes: ChangeSpec[] = []
  const seen = new Set<number>()

  for (const range of state.selection.ranges) {
    const first = state.doc.lineAt(range.from).number
    const last = state.doc.lineAt(range.to).number
    for (let number = first; number <= last; number += 1) {
      if (seen.has(number)) continue
      seen.add(number)
      const line = state.doc.line(number)

      if (!dedent) {
        changes.push({ from: line.from, insert: INDENT })
        continue
      }

      const leading = /^[ \t]+/.exec(line.text)
      if (!leading) continue
      let removed = 0
      let width = 0
      for (const char of leading[0]) {
        const step = char === '\t' ? INDENT_SIZE : 1
        if (width + step > INDENT_SIZE) break
        width += step
        removed += 1
        if (width === INDENT_SIZE) break
      }
      if (removed > 0) changes.push({ from: line.from, to: line.from + removed })
    }
  }

  if (changes.length === 0) return false
  view.dispatch({ changes, userEvent: dedent ? 'delete.dedent' : 'input.indent' })
  return true
}

/** Tab: indent to the next stop, or indent the whole selection. */
function indentCommand(view: EditorView): boolean {
  const { state } = view
  if (state.readOnly) return false

  const single = state.selection.ranges.length === 1 ? state.selection.main : null
  if (single && single.empty) {
    view.dispatch({
      ...state.changeByRange((range) => {
        const line = state.doc.lineAt(range.from)
        const column = range.from - line.from
        const fill = INDENT_SIZE - (column % INDENT_SIZE)
        return {
          changes: { from: range.from, insert: ' '.repeat(fill) },
          range: EditorSelection.cursor(range.from + fill),
        }
      }),
      userEvent: 'input.indent',
      scrollIntoView: true,
    })
    return true
  }

  return indentLines(view, false)
}

/** Shift-Tab: remove one indentation step from every touched line. */
function dedentCommand(view: EditorView): boolean {
  if (view.state.readOnly) return false
  return indentLines(view, true)
}

export interface CodeEditorProps {
  /** Editor contents. Changing it from outside replaces the document in place. */
  value: string
  /** Drives syntax highlighting and auto-indent. */
  language: Language
  /** Fired for user edits only — never for `value` changes pushed in as props. */
  onChange: (value: string) => void
  /** Bound to Cmd/Ctrl-Enter. */
  onRun?: () => void
  readOnly?: boolean
  className?: string
  /** Accessible name for the editing surface. */
  ariaLabel?: string
}

/**
 * CodeMirror 6 editor.
 *
 * The `EditorView` is created once and then reconfigured through compartments;
 * nothing here tears the view down on a prop change, so undo history, scroll
 * position and the cursor all survive re-renders. Under StrictMode the mount
 * effect runs twice — the cleanup destroys the view and removes its DOM, and
 * the second run rebuilds it from the same refs, so the two passes are
 * symmetric and no listener or DOM node is left behind.
 */
export function CodeEditor({
  value,
  language,
  onChange,
  onRun,
  readOnly = false,
  className,
  ariaLabel = 'Exercise code editor',
}: CodeEditorProps) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const viewRef = useRef<EditorView | null>(null)

  // Latest props, readable from long-lived CodeMirror extensions without
  // reconfiguring (and thus without re-creating) anything.
  const valueRef = useRef(value)
  const languageRef = useRef(language)
  const readOnlyRef = useRef(readOnly)
  const onChangeRef = useRef(onChange)
  const onRunRef = useRef(onRun)
  const ariaLabelRef = useRef(ariaLabel)

  useEffect(() => {
    onChangeRef.current = onChange
    onRunRef.current = onRun
    ariaLabelRef.current = ariaLabel
  })

  // --- create / destroy the view -------------------------------------------
  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const runKeymap: KeyBinding[] = [
      // No `preventDefault: true` on any of these: that flag swallows the key
      // even when the command declines it, and each of these commands can
      // decline (no `onRun`, or a read-only editor). A command that returns
      // true already gets the default prevented for it.
      {
        key: 'Mod-Enter',
        run: () => {
          const run = onRunRef.current
          if (!run) return false
          run()
          return true
        },
      },
      // Tab indents rather than moving focus, which is what a code pane is
      // expected to do. Both commands bail out (returning false, so the key
      // falls through to the browser and focus moves on) when the editor is
      // read-only, which keeps the read-only view fully keyboard-navigable.
      { key: 'Tab', run: indentCommand },
      { key: 'Shift-Tab', run: dedentCommand },
    ]

    const view = new EditorView({
      parent: host,
      state: EditorState.create({
        doc: valueRef.current,
        extensions: [
          // Highest precedence so Mod-Enter and Tab beat the default keymaps
          // that `basicSetup` installs.
          Prec.highest(keymap.of(runKeymap)),
          basicSetup,
          baseTheme,
          languageConf.of(languageExtension(languageRef.current)),
          themeConf.of(paperTheme),
          editableConf.of([
            EditorState.readOnly.of(readOnlyRef.current),
            EditorView.editable.of(!readOnlyRef.current),
          ]),
          // Function form so a later `ariaLabel` prop is picked up without a
          // reconfigure.
          EditorView.contentAttributes.of(() => ({ 'aria-label': ariaLabelRef.current })),
          EditorView.updateListener.of((update) => {
            if (!update.docChanged) return
            if (update.transactions.some((tr) => tr.annotation(External))) return
            const next = update.state.doc.toString()
            valueRef.current = next
            onChangeRef.current(next)
          }),
        ],
      }),
    })

    viewRef.current = view
    return () => {
      viewRef.current = null
      // Destroys the view's DOM and every extension it owns, including the
      // update listener above.
      view.destroy()
    }
  }, [])

  // --- reconcile an externally changed document ----------------------------
  useEffect(() => {
    valueRef.current = value
    const view = viewRef.current
    if (!view) return

    const current = view.state.doc.toString()
    if (current === value) return

    // Replace the document but keep the cursor where it was (clamped), so a
    // debounced save that echoes the value back does not jump the caret.
    const anchor = Math.min(view.state.selection.main.anchor, value.length)
    const head = Math.min(view.state.selection.main.head, value.length)
    view.dispatch({
      changes: { from: 0, to: current.length, insert: value },
      selection: { anchor, head },
      annotations: [External.of(true)],
      scrollIntoView: false,
    })
  }, [value])

  // --- swap the grammar ----------------------------------------------------
  useEffect(() => {
    languageRef.current = language
    const view = viewRef.current
    if (!view) return
    view.dispatch({ effects: languageConf.reconfigure(languageExtension(language)) })
  }, [language])

  // --- toggle editability --------------------------------------------------
  useEffect(() => {
    readOnlyRef.current = readOnly
    const view = viewRef.current
    if (!view) return
    view.dispatch({
      effects: editableConf.reconfigure([
        EditorState.readOnly.of(readOnly),
        EditorView.editable.of(!readOnly),
      ]),
    })
  }, [readOnly])

  return (
    <div
      ref={hostRef}
      data-language={language}
      data-readonly={readOnly ? 'true' : undefined}
      className={cn('h-full min-h-0 w-full overflow-hidden', className)}
    />
  )
}
