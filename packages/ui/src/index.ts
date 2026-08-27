// Public surface of @atlas/ui.
//
// Source-only package: consumers (apps/web, apps/desktop) compile these files
// through their own Vite pipeline, and must also import the stylesheet once:
//
//   import '@atlas/ui/styles.css'

/* ------------------------------------------------------------------ utils */
export { cn } from './lib/cn'
export type { ClassValue } from './lib/cn'

export { renderMarkdown, escapeHtml, copyCodeFrom } from './lib/markdown'


/* ------------------------------------------------------------- primitives */
export { Button } from './components/Button'
export type { ButtonProps, ButtonVariant, ButtonSize } from './components/Button'

export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from './components/Card'
export type { CardProps } from './components/Card'

export { Badge } from './components/Badge'
export type { BadgeProps, BadgeVariant, BadgeSize } from './components/Badge'

export { ProgressBar } from './components/ProgressBar'
export type { ProgressBarProps, ProgressTone } from './components/ProgressBar'

export { Spinner } from './components/Spinner'
export type { SpinnerProps, SpinnerSize } from './components/Spinner'

export { Input } from './components/Input'
export type { InputProps, InputSize } from './components/Input'

export { Label } from './components/Label'
export type { LabelProps } from './components/Label'

export { Alert } from './components/Alert'
export type { AlertProps, AlertVariant } from './components/Alert'

export { Markdown } from './components/Markdown'
export type { MarkdownProps } from './components/Markdown'

/* ------------------------------------------------------------- composites */
export { ModuleCard } from './components/ModuleCard'
export type { ModuleCardProps } from './components/ModuleCard'

export { LessonSidebar } from './components/LessonSidebar'
export type { LessonSidebarProps } from './components/LessonSidebar'

export { AppShell } from './components/AppShell'
export type { AppShellProps } from './components/AppShell'

/* ---------------------------------------------------------------- widgets */
export * from './widgets'
