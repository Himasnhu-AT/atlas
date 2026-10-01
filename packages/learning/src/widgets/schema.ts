import { z } from 'zod'

/**
 * Zod validation schemas for all interactive widgets embedded in lessons.
 * Every widget config written in MDX is validated at compile-time by build.ts.
 */

export const TokenBudgetWidgetSchema = z.object({
  maxTokens: z.number().int().positive().default(4096),
  systemTokens: z.number().int().nonnegative().default(350),
  toolSchemaTokens: z.number().int().nonnegative().default(400),
  initialTurns: z.number().int().nonnegative().default(8),
  reserveOutputTokens: z.number().int().nonnegative().default(512),
  showAttentionHeatmap: z.boolean().default(true),
  puzzleTarget: z.string().optional(),
})
export type TokenBudgetWidgetConfig = z.infer<typeof TokenBudgetWidgetSchema>

export const StateMachineWidgetSchema = z.object({
  initialState: z.string(),
  states: z.record(
    z.string(),
    z.object({
      label: z.string(),
      description: z.string().optional(),
      transitions: z.record(z.string(), z.string()).default({}),
      isTerminal: z.boolean().optional(),
      isError: z.boolean().optional(),
    }),
  ),
  faultInjections: z
    .array(
      z.object({
        id: z.string(),
        label: z.string(),
        targetState: z.string(),
        action: z.string(),
      }),
    )
    .optional(),
  goal: z.string().optional(),
})
export type StateMachineWidgetConfig = z.infer<typeof StateMachineWidgetSchema>

export const MemoryLayoutWidgetSchema = z.object({
  alignmentBytes: z.number().int().positive().default(8),
  fields: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      type: z.string(),
      sizeBytes: z.number().int().positive(),
    }),
  ),
  cacheLineBytes: z.number().int().positive().default(64),
  allowReorder: z.boolean().default(true),
})
export type MemoryLayoutWidgetConfig = z.infer<typeof MemoryLayoutWidgetSchema>

export const VectorSpaceWidgetSchema = z.object({
  points: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      x: z.number(),
      y: z.number(),
      category: z.string().optional(),
    }),
  ),
  initialSimilarityThreshold: z.number().min(-1).max(1).default(0.7),
  queryPoint: z
    .object({
      label: z.string(),
      x: z.number(),
      y: z.number(),
    })
    .optional(),
})
export type VectorSpaceWidgetConfig = z.infer<typeof VectorSpaceWidgetSchema>

export const OrderBookDepthWidgetSchema = z.object({
  bids: z.array(z.object({ price: z.number().positive(), size: z.number().positive() })),
  asks: z.array(z.object({ price: z.number().positive(), size: z.number().positive() })),
  tickSize: z.number().positive().default(0.01),
  defaultOrderSize: z.number().positive().default(100),
})
export type OrderBookDepthWidgetConfig = z.infer<typeof OrderBookDepthWidgetSchema>

export const CacheHierarchyWidgetSchema = z.object({
  cacheLineBytes: z.number().int().positive().default(64),
  cores: z.number().int().positive().default(2),
  variables: z.array(
    z.object({
      name: z.string(),
      offsetBytes: z.number().int().nonnegative(),
      sizeBytes: z.number().int().positive(),
    }),
  ),
})
export type CacheHierarchyWidgetConfig = z.infer<typeof CacheHierarchyWidgetSchema>

export const AdversarialInputWidgetSchema = z.object({
  systemPrompt: z.string(),
  guardrailRules: z.array(z.string()),
  targetSecret: z.string().optional(),
  forbiddenTokens: z.array(z.string()).default([]),
})
export type AdversarialInputWidgetConfig = z.infer<typeof AdversarialInputWidgetSchema>

export const StructuredOutputWidgetSchema = z.object({
  initialPreset: z.enum(['clean', 'fence', 'type_mismatch', 'truncated', 'conversational']).default('type_mismatch'),
})
export type StructuredOutputWidgetConfig = z.infer<typeof StructuredOutputWidgetSchema>

export const WidgetRegistrySchemas: Record<string, z.ZodTypeAny> = {
  'token-budget': TokenBudgetWidgetSchema,
  'state-machine': StateMachineWidgetSchema,
  'memory-layout': MemoryLayoutWidgetSchema,
  'vector-space': VectorSpaceWidgetSchema,
  'order-book': OrderBookDepthWidgetSchema,
  'cache-hierarchy': CacheHierarchyWidgetSchema,
  'adversarial-input': AdversarialInputWidgetSchema,
  'structured-output': StructuredOutputWidgetSchema,
}

export function validateWidgetProps(type: string, props: unknown): { success: true; data: any } | { success: false; errors: string[] } {
  const schema = WidgetRegistrySchemas[type]
  if (!schema) {
    return {
      success: false,
      errors: [`Unknown widget type "${type}". Registered types: ${Object.keys(WidgetRegistrySchemas).join(', ')}`],
    }
  }
  const result = schema.safeParse(props || {})
  if (!result.success) {
    return {
      success: false,
      errors: result.error.issues.map((i) => `[${i.path.join('.') || 'root'}] ${i.message}`),
    }
  }
  return { success: true, data: result.data }
}
