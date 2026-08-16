import DOMPurify from 'dompurify'
import { Marked, type RendererObject, type Tokens } from 'marked'

/** Escape a raw string for safe interpolation into HTML text/attribute slots. */
export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** GitHub-ish heading slug: keeps unicode word characters, collapses the rest. */
function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/<[^>]*>/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
}

/**
 * Slugs must be unique within a single rendered document, so the counter is
 * reset by `renderMarkdown` before every parse.
 */
const usedSlugs = new Map<string, number>()

function uniqueSlug(base: string): string {
  const key = base || 'section'
  const seen = usedSlugs.get(key) ?? 0
  usedSlugs.set(key, seen + 1)
  return seen === 0 ? key : `${key}-${seen}`
}

const KNOWN_LANGUAGE_LABELS: Record<string, string> = {
  js: 'javascript',
  jsx: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  py: 'python',
  rs: 'rust',
  sh: 'bash',
  shell: 'bash',
  zsh: 'bash',
  yml: 'yaml',
  md: 'markdown',
}

function isExternalHref(href: string): boolean {
  return /^(https?:)?\/\//i.test(href)
}

const renderer: RendererObject = {
  code({ text, lang, escaped }: Tokens.Code): string {
    const rawLang = (lang ?? '').trim().split(/\s+/)[0]?.toLowerCase() ?? ''
    const label = KNOWN_LANGUAGE_LABELS[rawLang] ?? rawLang
    const body = escaped ? text : escapeHtml(text)
    const langChip = label
      ? `<span class="md-code__lang">${escapeHtml(label)}</span>`
      : '<span class="md-code__lang">code</span>'
    const codeClass = label ? ` class="language-${escapeHtml(label)}"` : ''

    // The copy button is deliberately *not* emitted here: `<button>` is on the
    // sanitiser's deny list, so it is attached afterwards from trusted code.
    return (
      `<figure class="md-code">` +
      `<figcaption class="md-code__bar">${langChip}</figcaption>` +
      `<pre><code${codeClass}>${body}\n</code></pre>` +
      `</figure>`
    )
  },

  // GFM task lists normally compile to `<input type="checkbox">`, and form
  // controls are denied by the sanitiser. Render an inert marker instead so the
  // checkbox survives and still announces its state.
  checkbox({ checked }: Tokens.Checkbox): string {
    const cls = checked ? 'md-check md-check--checked' : 'md-check'
    const label = checked ? 'Completed' : 'Not completed'
    return `<span class="${cls}" role="img" aria-label="${label}"></span>`
  },

  heading(token: Tokens.Heading): string {
    const level = Math.min(Math.max(token.depth, 1), 6)
    const content = this.parser.parseInline(token.tokens)
    const id = uniqueSlug(slugify(token.text))
    return `<h${level} id="${escapeHtml(id)}">${content}</h${level}>`
  },

  link({ href, title, tokens }: Tokens.Link): string {
    const content = this.parser.parseInline(tokens)
    const titleAttr = title ? ` title="${escapeHtml(title)}"` : ''
    const external = isExternalHref(href)
    const relAttr = external ? ' target="_blank" rel="noopener noreferrer"' : ''
    return `<a href="${escapeHtml(href)}"${titleAttr}${relAttr}>${content}</a>`
  },

  table(token: Tokens.Table): string {
    // Alignment travels as a class, never an inline style — the sanitiser
    // strips `style` outright so authored markdown cannot inject CSS.
    const cell = (c: Tokens.TableCell, tag: 'th' | 'td'): string => {
      const align = c.align ? ` class="md-align-${c.align}"` : ''
      return `<${tag}${align}>${this.parser.parseInline(c.tokens)}</${tag}>`
    }
    const head = `<tr>${token.header.map((c) => cell(c, 'th')).join('')}</tr>`
    const body = token.rows
      .map((row) => `<tr>${row.map((c) => cell(c, 'td')).join('')}</tr>`)
      .join('')
    return (
      `<div class="md-table-wrap"><table>` +
      `<thead>${head}</thead>` +
      (body ? `<tbody>${body}</tbody>` : '') +
      `</table></div>`
    )
  },
}

const parser = new Marked({ gfm: true, breaks: false, async: false }).use({ renderer })

/**
 * `USE_PROFILES: { html: true }` narrows the allow-list to HTML, taking SVG and
 * MathML — the usual mXSS playground — off the table entirely. Interactive and
 * embedding elements are then denied on top of that.
 */
const SANITIZE_CONFIG: NonNullable<Parameters<typeof DOMPurify.sanitize>[1]> = {
  USE_PROFILES: { html: true },
  ADD_ATTR: ['target'],
  FORBID_TAGS: ['style', 'form', 'input', 'button', 'iframe', 'object', 'embed'],
  FORBID_ATTR: ['style', 'srcset', 'formaction', 'ping'],
  ALLOW_DATA_ATTR: false,
}

/**
 * The copy-button chrome we generate ourselves must survive sanitisation, but
 * author-supplied markdown must never be able to inject a `<button>`. So the
 * generated markup is re-attached from a trusted template after sanitising:
 * DOMPurify strips every button, then we restore ours on the figures we know
 * we emitted.
 */
function restoreCopyButtons(root: Element): void {
  for (const bar of root.querySelectorAll('figure.md-code > figcaption.md-code__bar')) {
    if (bar.querySelector('button')) continue
    const button = bar.ownerDocument.createElement('button')
    button.type = 'button'
    button.className = 'md-code__copy'
    button.setAttribute('data-copy-code', '')
    button.setAttribute('aria-label', 'Copy code to clipboard')
    button.textContent = 'Copy'
    bar.appendChild(button)
  }
}

/**
 * Compile markdown to HTML **without sanitising it**.
 *
 * Internal to this module and deliberately absent from the package's public
 * exports: the output is unsafe until it has been through `renderMarkdown`.
 */
export function compileMarkdown(source: string): string {
  usedSlugs.clear()
  return parser.parse(source, { async: false })
}

/**
 * Compile markdown to a sanitised HTML string.
 *
 * Sanitisation happens after compilation, so raw HTML embedded in the markdown
 * source is subject to exactly the same filtering as generated markup.
 * In an environment without a DOM (SSR, tests) the source is returned escaped
 * inside a `<pre>` rather than trusting unsanitised HTML.
 */
export function renderMarkdown(source: string): string {
  if (!source) return ''

  const rawHtml = compileMarkdown(source)

  if (typeof window === 'undefined' || !DOMPurify.isSupported) {
    return `<pre>${escapeHtml(source)}</pre>`
  }

  const fragment = DOMPurify.sanitize(rawHtml, {
    ...SANITIZE_CONFIG,
    RETURN_DOM_FRAGMENT: true,
  })

  const host = document.createElement('div')
  host.appendChild(fragment)
  restoreCopyButtons(host)
  return host.innerHTML
}

/**
 * Copy the code of the block owning `trigger` to the clipboard.
 * Returns false when the browser refuses (permissions, insecure context).
 */
export async function copyCodeFrom(trigger: Element): Promise<boolean> {
  const figure = trigger.closest('figure.md-code')
  const code = figure?.querySelector('pre code')
  const text = code?.textContent
  if (!text) return false

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text.replace(/\n$/, ''))
      return true
    }
  } catch {
    /* fall through to the legacy path below */
  }

  // Legacy fallback for non-secure origins where the async clipboard is absent.
  const scratch = document.createElement('textarea')
  scratch.value = text.replace(/\n$/, '')
  scratch.setAttribute('readonly', '')
  scratch.style.position = 'fixed'
  scratch.style.opacity = '0'
  document.body.appendChild(scratch)
  scratch.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(scratch)
  return ok
}
