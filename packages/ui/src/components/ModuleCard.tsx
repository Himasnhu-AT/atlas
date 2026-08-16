import type { ComponentPropsWithRef, MouseEvent } from 'react'
import { ArrowRight, BookOpen, Clock } from 'lucide-react'
import { cn } from '../lib/cn'
import { Badge, type BadgeVariant } from './Badge'

export type CardDifficulty = 'beginner' | 'intermediate' | 'advanced'

/** Structural shape, so any caller with matching data can use this card. */
export interface CardModule {
  id: string
  slug: string
  name: string
  order: number
  summary: string
  difficulty: CardDifficulty
  estimatedHours: number
  tags?: string[]
  lessons: unknown[]
}
import { ProgressBar } from './ProgressBar'

export interface ModuleCardProps
  extends Omit<ComponentPropsWithRef<'a'>, 'href' | 'children'> {
  module: CardModule
  /** Completion of the module, 0–100. */
  progressPct: number
  href: string
  /**
   * Client-side navigation hook. When supplied, plain left-clicks are
   * intercepted and handed to this callback; modified clicks (new tab, etc.)
   * still fall through to the real `href`.
   */
  onNavigate?: (href: string) => void
}

const DIFFICULTY_VARIANT: Record<CardDifficulty, BadgeVariant> = {
  beginner: 'success',
  intermediate: 'warning',
  advanced: 'danger',
}

const DIFFICULTY_LABEL: Record<CardDifficulty, string> = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
}

function formatHours(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`
  const rounded = Math.round(hours * 10) / 10
  return `${rounded} hr${rounded === 1 ? '' : 's'}`
}

/** Course-overview tile: one module, its metadata, and the learner's progress. */
export function ModuleCard({
  module,
  progressPct,
  href,
  onNavigate,
  onClick,
  className,
  ...props
}: ModuleCardProps) {
  const pct = Math.min(Math.max(Math.round(progressPct), 0), 100)
  const complete = pct >= 100
  const lessonCount = module.lessons.length

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)
    if (!onNavigate || event.defaultPrevented) return
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return
    }
    event.preventDefault()
    onNavigate(href)
  }

  return (
    <a
      href={href}
      onClick={handleClick}
      aria-label={`${module.name} — ${pct}% complete`}
      className={cn(
        'group flex h-full flex-col gap-4 rounded-sheet border border-rule bg-paper-raised p-5',
        'shadow-none transition-[box-shadow,border-color,transform] duration-200 ease-paper',
        'hover:-translate-y-0.5 hover:border-rule-strong hover:shadow-none',
        'focus-visible:-translate-y-0.5 focus-visible:shadow-none',
        className,
      )}
      {...props}
    >
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden
          className={cn(
            'inline-flex size-8 shrink-0 items-center justify-center rounded-lg',
            'font-mono text-xs font-semibold tabular-nums',
            complete
              ? 'bg-pass-wash text-pass'
              : 'bg-accent-wash text-accent',
          )}
        >
          {String(module.order).padStart(2, '0')}
        </span>
        <Badge variant={DIFFICULTY_VARIANT[module.difficulty]} size="sm">
          {DIFFICULTY_LABEL[module.difficulty]}
        </Badge>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted">
          <Clock aria-hidden className="size-3.5" />
          {formatHours(module.estimatedHours)}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-1.5">
        <h3 className="flex items-start gap-1.5 text-base leading-snug font-semibold tracking-[-0.01em] text-ink">
          <span className="min-w-0">{module.name}</span>
          <ArrowRight
            aria-hidden
            className={cn(
              'mt-0.5 size-4 shrink-0 text-muted transition-transform duration-200 ease-paper',
              'group-hover:translate-x-0.5 group-hover:text-accent',
            )}
          />
        </h3>
        <p className="line-clamp-2 text-sm leading-relaxed text-ink-soft">{module.summary}</p>
      </div>

      {module.tags && module.tags.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5">
          {module.tags.slice(0, 4).map((tag: string) => (
            <li key={tag}>
              <Badge variant="outline" size="sm">
                {tag}
              </Badge>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-col gap-2 border-t border-rule pt-3.5">
        <div className="flex items-center justify-between gap-3 text-xs font-medium">
          <span className="inline-flex items-center gap-1.5 text-muted">
            <BookOpen aria-hidden className="size-3.5" />
            {lessonCount} {lessonCount === 1 ? 'lesson' : 'lessons'}
          </span>
          <span className={cn('tabular-nums', complete ? 'text-pass' : 'text-ink-soft')}>
            {complete ? 'Complete' : `${pct}%`}
          </span>
        </div>
        <ProgressBar
          value={pct}
          max={100}
          size="xs"
          tone={complete ? 'success' : 'brand'}
          valueText={`${pct}% complete`}
        />
      </div>
    </a>
  )
}
