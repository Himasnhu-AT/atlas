import { z } from 'zod'

/**
 * The vocabulary a `text-contract` challenge is checked against.
 *
 * A closed set of typed assertions rather than an expression language, because
 * the desktop app's production CSP is `script-src 'self'` with no
 * `unsafe-eval`. Nothing authored in a lesson is ever evaluated. That is a real
 * limit: when a challenge needs a check this cannot express, the answer is a
 * small component of its own, not an interpreter.
 *
 * The shape came from `StructuredOutputWorkbench`, which spent 475 lines of
 * hand-written React on what turned out to be an ordered chain of exactly these
 * operations with one message per failure.
 */

/** A JSON literal, for the `equals` and `oneOf` operands. */
const Json: z.ZodType<unknown> = z.lazy(() =>
  z.union([z.string(), z.number(), z.boolean(), z.null(), z.array(Json), z.record(z.string(), Json)]),
)

/**
 * A dotted key path with numeric indices, `items.0.qty`.
 *
 * Deliberately not JSONPath. A path language with filters and wildcards is a
 * second thing to implement, document and get wrong, and no lesson so far has
 * needed one.
 */
const Path = z.string().regex(/^[A-Za-z_$][\w$]*([.][A-Za-z_$0-9][\w$]*)*$/, 'a path is dotted keys')

/**
 * An author-supplied pattern, compiled with `new RegExp`.
 *
 * Not `eval`: a RegExp constructor takes no scope and can reach nothing. The
 * real hazard is catastrophic backtracking freezing the tab, which the length
 * cap and the 4000 character buffer bound in practice.
 */
const Pattern = z.string().min(1).max(200)
const Flags = z.string().regex(/^[imsu]*$/).max(4)

export const Assertion = z.discriminatedUnion('op', [
  z.object({ op: z.literal('parses'), as: z.enum(['json', 'integer', 'number']) }),
  z.object({ op: z.literal('exists'), path: Path }),
  z.object({ op: z.literal('absent'), path: Path }),
  z.object({
    op: z.literal('type'),
    path: Path,
    is: z.enum(['string', 'number', 'integer', 'boolean', 'array', 'object', 'null']),
  }),
  z.object({ op: z.literal('equals'), path: Path, value: Json }),
  z.object({ op: z.literal('oneOf'), path: Path, values: z.array(Json).min(1).max(12) }),
  z.object({
    op: z.literal('range'),
    path: Path,
    min: z.number().optional(),
    max: z.number().optional(),
  }),
  z.object({
    op: z.literal('length'),
    path: Path.optional(),
    min: z.number().int().nonnegative().optional(),
    max: z.number().int().nonnegative().optional(),
  }),
  z.object({
    op: z.literal('contains'),
    path: Path.optional(),
    text: z.string().min(1).max(200),
    caseSensitive: z.boolean().default(false),
  }),
  z.object({
    op: z.literal('notContains'),
    path: Path.optional(),
    text: z.string().min(1).max(200),
    caseSensitive: z.boolean().default(false),
  }),
  z.object({ op: z.literal('matches'), path: Path.optional(), pattern: Pattern, flags: Flags.default('') }),
  z.object({ op: z.literal('notMatches'), path: Path.optional(), pattern: Pattern, flags: Flags.default('') }),
])
export type Assertion = z.infer<typeof Assertion>

export const Rule = z.object({
  /**
   * Written as the fix, not the complaint. This single string is the whole of
   * what the learner is told when the rule fails, so "the markdown fence is
   * still there, and three backticks are not JSON" beats "invalid input".
   */
  message: z.string().min(1).max(300),
  check: Assertion,
})
export type Rule = z.infer<typeof Rule>

/** Whether an assertion reads the parsed document rather than the raw text. */
export function needsParsedInput(assertion: Assertion): boolean {
  return 'path' in assertion && typeof assertion.path === 'string'
}
