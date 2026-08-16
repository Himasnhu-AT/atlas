'use client'

import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'

/**
 * Flips the `.dark` class on <html> and remembers the choice.
 *
 * The class is applied before paint by an inline script in the root layout, so
 * this component only handles changes. It renders a neutral placeholder until
 * mounted, because the server cannot know which theme the browser picked.
 */
export function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null)

  useEffect(() => {
    setDark(document.documentElement.classList.contains('dark'))
  }, [])

  function toggle() {
    const next = !document.documentElement.classList.contains('dark')
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      // Private browsing. The toggle still works for this session.
    }
    setDark(next)
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      className="grid size-9 place-items-center rounded-lg text-muted transition hover:bg-surface-hover hover:text-ink"
    >
      {dark === null ? (
        <span className="size-4" />
      ) : dark ? (
        <Sun className="size-4" />
      ) : (
        <Moon className="size-4" />
      )}
    </button>
  )
}
