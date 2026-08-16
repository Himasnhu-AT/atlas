import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * tailwind-merge only knows about Tailwind's *stock* theme scales. Our design
 * tokens add a few named values (see `src/styles.css`), and without teaching
 * the merger about them it would classify e.g. `shadow-none` as a shadow
 * *colour* rather than a box-shadow, so `shadow-none shadow-none` would keep
 * both classes instead of letting the later one win.
 */
const merge = extendTailwindMerge({
  extend: {
    theme: {
      shadow: ['card', 'card-hover', 'pop', 'inset-hairline'],
      radius: ['card', 'field', 'pill'],
      ease: ['out-expo', 'spring'],
    },
  },
})

/**
 * Compose conditional class names and resolve Tailwind conflicts so that the
 * last-specified utility always wins.
 *
 * ```ts
 * cn('px-3 py-2', isActive && 'bg-accent', className)
 * ```
 */
export function cn(...inputs: ClassValue[]): string {
  return merge(clsx(inputs))
}

export type { ClassValue }
