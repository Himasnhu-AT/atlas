'use client'

import React, { useState } from 'react'

export type LessonStage = 'play' | 'read' | 'code'

export interface LessonStageControllerProps {
  hasInteractive?: boolean
  hasExercise?: boolean
  interactiveNode?: React.ReactNode
  headerNode?: React.ReactNode
  proseNode: React.ReactNode
  exerciseNode?: React.ReactNode
  sidebarNode?: React.ReactNode
  footerNode?: React.ReactNode
}

export function LessonStageController({
  hasInteractive = false,
  hasExercise = false,
  interactiveNode,
  headerNode,
  proseNode,
  exerciseNode,
  sidebarNode,
  footerNode,
}: LessonStageControllerProps) {
  // Default to 'play' if interactive exists, otherwise 'read'
  const [activeStage, setActiveStage] = useState<LessonStage>(hasInteractive ? 'play' : 'read')

  return (
    <div className="w-full">
      {/* Top 3-Stage Navigation Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-rule pb-3">
        <nav aria-label="Lesson Stages" className="flex items-center gap-2 sm:gap-4">
          {hasInteractive && (
            <button
              onClick={() => setActiveStage('play')}
              className={`group relative flex items-center gap-2 rounded-field px-3 py-1.5 text-caption font-mono transition-colors cursor-pointer ${
                activeStage === 'play'
                  ? 'font-bold text-accent'
                  : 'text-muted hover:text-ink hover:bg-paper-raised'
              }`}
            >
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  activeStage === 'play' ? 'bg-accent ring-4 ring-accent/15' : 'bg-rule-strong'
                }`}
              />
              <span>01 · PLAY</span>
              {activeStage === 'play' && (
                <span className="absolute -bottom-3.5 left-0 right-0 h-[2px] bg-accent" />
              )}
            </button>
          )}

          <button
            onClick={() => setActiveStage('read')}
            className={`group relative flex items-center gap-2 rounded-field px-3 py-1.5 text-caption font-mono transition-colors cursor-pointer ${
              activeStage === 'read'
                ? 'font-bold text-accent'
                : 'text-muted hover:text-ink hover:bg-paper-raised'
            }`}
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                activeStage === 'read' ? 'bg-accent ring-4 ring-accent/15' : 'bg-rule-strong'
              }`}
            />
            <span>{hasInteractive ? '02 · READ (OPTIONAL)' : '01 · READ'}</span>
            {activeStage === 'read' && (
              <span className="absolute -bottom-3.5 left-0 right-0 h-[2px] bg-accent" />
            )}
          </button>

          {hasExercise && (
            <button
              onClick={() => setActiveStage('code')}
              className={`group relative flex items-center gap-2 rounded-field px-3 py-1.5 text-caption font-mono transition-colors cursor-pointer ${
                activeStage === 'code'
                  ? 'font-bold text-accent'
                  : 'text-muted hover:text-ink hover:bg-paper-raised'
              }`}
            >
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  activeStage === 'code' ? 'bg-accent ring-4 ring-accent/15' : 'bg-rule-strong'
                }`}
              />
              <span>{hasInteractive ? '03 · CODE' : '02 · CODE'}</span>
              {activeStage === 'code' && (
                <span className="absolute -bottom-3.5 left-0 right-0 h-[2px] bg-accent" />
              )}
            </button>
          )}
        </nav>

        <div className="text-[11px] font-mono text-muted uppercase hidden sm:block">
          {activeStage === 'play' && 'Stage 1 · Hands-On Exploration'}
          {activeStage === 'read' && 'Stage 2 · Theory & Documentation (Optional)'}
          {activeStage === 'code' && 'Stage 3 · Code Practice & Verification'}
        </div>
      </div>

      {/* =================================================================== */}
      {/* STAGE 1: PLAY (FULL SCREEN IMMERSION, NO HERO/SIDEBAR CLUTTER)      */}
      {/* =================================================================== */}
      {activeStage === 'play' && hasInteractive && (
        <div className="w-full animate-in fade-in duration-200">
          {React.isValidElement(interactiveNode)
            ? React.cloneElement(interactiveNode as React.ReactElement<any>, {
                onGoToCode: () => setActiveStage(hasExercise ? 'code' : 'read'),
                onGoToRead: () => setActiveStage('read'),
              })
            : interactiveNode}
        </div>
      )}

      {/* =================================================================== */}
      {/* STAGE 2: READ (EDITORIAL DOCUMENTATION + SIDEBAR)                   */}
      {/* =================================================================== */}
      {activeStage === 'read' && (
        <div className="flex flex-col lg:flex-row lg:gap-14 animate-in fade-in duration-200">
          {sidebarNode && (
            <div className="w-full lg:w-64 shrink-0">{sidebarNode}</div>
          )}

          <div className="min-w-0 flex-1">
            {headerNode}

            <div className="mt-8">{proseNode}</div>

            {/* Navigation to Code */}
            <div className="mt-12 flex items-center justify-between border-t border-rule pt-6">
              {hasInteractive ? (
                <button
                  onClick={() => setActiveStage('play')}
                  className="inline-flex items-center gap-2 text-caption font-mono text-muted hover:text-ink transition-colors cursor-pointer"
                >
                  <span>&larr;</span>
                  <span>Back to Stage 1: Interactive Sandbox</span>
                </button>
              ) : (
                <span />
              )}

              {hasExercise && (
                <button
                  onClick={() => setActiveStage('code')}
                  className="inline-flex items-center gap-2 rounded-field bg-accent px-5 py-2.5 text-caption font-medium text-white shadow-xs hover:bg-accent-deep transition-colors cursor-pointer"
                >
                  <span>Proceed to Stage 3: Code Exercise</span>
                  <span>&rarr;</span>
                </button>
              )}
            </div>

            {footerNode && <div className="mt-10">{footerNode}</div>}
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* STAGE 3: CODE (SPLIT SCREEN: 50% SPECS / 50% CODE EDITOR)           */}
      {/* =================================================================== */}
      {activeStage === 'code' && hasExercise && (
        <div className="w-full animate-in fade-in duration-200">
          <div className="grid gap-8 lg:grid-cols-12">
            {/* Left 50% Column: Problem Spec, Invariants, & Requirements */}
            <div className="lg:col-span-5 space-y-6">
              {headerNode}

              <div className="rounded-xl border border-rule-strong bg-paper-sunken p-5 text-caption text-ink-soft space-y-3">
                <span className="text-[10px] font-mono font-bold uppercase text-accent">
                  Coding Objective
                </span>
                <p className="leading-relaxed">
                  Implement your solution in the editor on the right or work in your local IDE. All unit tests run against your code in real-time.
                </p>
                <div className="pt-2 border-t border-rule flex items-center justify-between text-[11px] font-mono text-muted">
                  <span>Language: Python 3.10+</span>
                  <span>Runner: Local / Pyodide</span>
                </div>
              </div>

              <div className="flex items-center gap-4 pt-2">
                <button
                  onClick={() => setActiveStage('read')}
                  className="text-caption font-mono text-muted hover:text-ink transition-colors cursor-pointer"
                >
                  &larr; Review Stage 2: Documentation (Optional)
                </button>
              </div>

              {footerNode && <div className="pt-4 border-t border-rule">{footerNode}</div>}
            </div>

            {/* Right 50% Column: Full-Height Code Editor & Live Test Grader */}
            <div className="lg:col-span-7">
              {exerciseNode}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
