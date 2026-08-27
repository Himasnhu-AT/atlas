'use client'

import { useState } from 'react'

export interface StateMachineSimulatorProps {
  initialState: string
  states: Record<
    string,
    {
      label: string
      description?: string
      transitions: Record<string, string>
      isTerminal?: boolean
      isError?: boolean
    }
  >
  faultInjections?: Array<{
    id: string
    label: string
    targetState: string
    action: string
  }>
  goal?: string
}

export function StateMachineSimulator({
  initialState,
  states,
  faultInjections = [],
  goal,
}: StateMachineSimulatorProps) {
  const [currentState, setCurrentState] = useState(initialState)
  const [history, setHistory] = useState<string[]>([initialState])
  const [injectedFault, setInjectedFault] = useState<string | null>(null)

  const activeStateConfig = states[currentState] || {
    label: currentState,
    transitions: {},
  }

  const handleTransition = (action: string) => {
    const next = activeStateConfig.transitions[action]
    if (next && states[next]) {
      setCurrentState(next)
      setHistory((prev) => [...prev, next])
    }
  }

  const handleReset = () => {
    setCurrentState(initialState)
    setHistory([initialState])
    setInjectedFault(null)
  }

  const handleInjectFault = (fault: { id: string; targetState: string; action: string }) => {
    setInjectedFault(fault.id)
    if (states[fault.targetState]) {
      setCurrentState(fault.targetState)
      setHistory((prev) => [...prev, `[FAULT: ${fault.action}] -> ${fault.targetState}`])
    }
  }

  return (
    <div className="not-prose my-8 rounded border border-rule bg-paper p-5 font-sans shadow-sm sm:p-6">
      <div className="flex items-center justify-between border-b border-rule pb-3">
        <div>
          <span className="text-eyebrow font-medium uppercase text-muted">State Simulator</span>
          <h4 className="text-section font-serif text-ink">ReAct Loop & State Machine Execution</h4>
        </div>
        <button
          onClick={handleReset}
          className="rounded border border-rule px-2.5 py-1 text-caption text-muted hover:text-ink hover:bg-paper-sunken transition-colors"
        >
          Reset State
        </button>
      </div>

      {goal && (
        <div className="mt-3 rounded border border-rule-strong bg-paper-sunken px-3 py-2 text-caption text-ink-soft">
          <strong className="font-semibold text-ink">Objective:</strong> {goal}
        </div>
      )}

      {/* State Node Diagram */}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3 py-4">
        {Object.entries(states).map(([key, state]) => {
          const isActive = currentState === key
          return (
            <div
              key={key}
              className={`flex flex-col items-center rounded border px-4 py-3 text-center transition-all duration-200 ${
                isActive
                  ? state.isError
                    ? 'border-fail bg-fail/10 ring-2 ring-fail text-fail font-semibold scale-105 shadow-sm'
                    : 'border-accent bg-accent/10 ring-2 ring-accent text-accent font-semibold scale-105 shadow-sm'
                  : 'border-rule bg-paper-raised text-ink-soft opacity-75'
              }`}
            >
              <span className="font-mono text-caption uppercase text-muted text-[10px]">{key}</span>
              <span className="text-sm">{state.label}</span>
            </div>
          )
        })}
      </div>

      {/* Active State Details & Transitions */}
      <div className="mt-4 rounded border border-rule bg-paper-raised p-4">
        <div className="flex items-center justify-between">
          <div className="text-caption font-mono uppercase text-muted">
            Current Node: <span className="font-semibold text-ink">{activeStateConfig.label}</span>
          </div>
          {activeStateConfig.isTerminal && (
            <span className="text-caption font-semibold text-pass">Terminal State Reached</span>
          )}
        </div>

        {activeStateConfig.description && (
          <p className="mt-2 text-caption text-ink-soft">{activeStateConfig.description}</p>
        )}

        {/* Action Buttons */}
        <div className="mt-4 flex flex-wrap gap-2">
          {Object.entries(activeStateConfig.transitions).map(([action, target]) => (
            <button
              key={action}
              onClick={() => handleTransition(action)}
              className="inline-flex items-center gap-1.5 rounded-field border border-accent bg-accent px-3.5 py-1.5 text-caption font-medium text-white shadow-xs transition-colors hover:bg-accent-deep active:scale-98"
            >
              <span>{action}</span>
              <span className="text-[11px] opacity-75">&rarr; {states[target]?.label || target}</span>
            </button>
          ))}
          {Object.keys(activeStateConfig.transitions).length === 0 && !activeStateConfig.isTerminal && (
            <span className="text-caption text-muted italic">No forward transitions available from this state.</span>
          )}
        </div>
      </div>

      {/* Fault Injection Panel */}
      {faultInjections.length > 0 && (
        <div className="mt-4 border-t border-rule pt-3">
          <div className="flex items-center justify-between">
            <span className="text-caption font-medium text-ink-soft">Simulate Environment Faults:</span>
            {injectedFault && (
              <span className="text-xs font-mono font-semibold text-fail">Active: {injectedFault}</span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {faultInjections.map((fault) => (
              <button
                key={fault.id}
                onClick={() => handleInjectFault(fault)}
                className="rounded border border-fail/40 bg-fail/5 px-2.5 py-1 text-caption text-fail hover:bg-fail/15 transition-colors"
              >
                Trigger {fault.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Execution Trace Log */}
      <div className="mt-4 rounded bg-paper-sunken p-3 text-[11px] font-mono text-ink-soft">
        <span className="font-bold text-muted uppercase">Execution Trace:</span> {history.join(' → ')}
      </div>
    </div>
  )
}
