import React from 'react'
import { TokenBudgetVisualizer } from './TokenBudgetVisualizer'
import { StateMachineSimulator } from './StateMachineSimulator'
import { MemoryLayoutVisualizer } from './MemoryLayoutVisualizer'
import { VectorSpaceExplorer } from './VectorSpaceExplorer'
import { OrderBookDepthVisualizer } from './OrderBookDepthVisualizer'
import { CacheHierarchyVisualizer } from './CacheHierarchyVisualizer'
import { AdversarialInputBuilder } from './AdversarialInputBuilder'
import { StructuredOutputWorkbench } from './StructuredOutputWorkbench'

export const WidgetRegistry: Record<string, React.ComponentType<any>> = {
  'token-budget': TokenBudgetVisualizer,
  'state-machine': StateMachineSimulator,
  'memory-layout': MemoryLayoutVisualizer,
  'vector-space': VectorSpaceExplorer,
  'order-book': OrderBookDepthVisualizer,
  'cache-hierarchy': CacheHierarchyVisualizer,
  'adversarial-input': AdversarialInputBuilder,
  'structured-output': StructuredOutputWorkbench,
}
