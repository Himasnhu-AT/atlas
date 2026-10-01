"use client";

import React, { useState } from "react";

export type LessonStage = "play" | "read" | "code";

export interface LessonStageControllerProps {
  hasInteractive?: boolean;
  hasExercise?: boolean;
  interactiveNode?: React.ReactNode;
  headerNode?: React.ReactNode;
  proseNode: React.ReactNode;
  exerciseNode?: React.ReactNode;
  sidebarNode?: React.ReactNode;
  footerNode?: React.ReactNode;
  /**
   * Whether the challenges stand on their own.
   *
   * When they do, the lesson opens on them and reading stays optional, which
   * is the shape a discovery challenge wants. When they do not, reading leads
   * and is numbered first, because a challenge that assumes the prose is a
   * comprehension check, and putting it before the text it checks asks the
   * learner about something nobody has told them.
   */
  readingOptional?: boolean;
}

/**
 * The three stages of a lesson: play it, read about it, write it.
 *
 * Their order is not fixed. Reading leads unless the lesson's challenges were
 * authored to stand on their own, because a challenge that assumes the prose
 * is a comprehension check and asking it first is asking about something
 * nobody has said yet.
 *
 * All three are in the document at all times and the inactive ones carry the
 * `hidden` attribute. That is not a style preference: the prose is the whole
 * of what a search engine is served, and a lesson that mounts only the active
 * stage ships HTML with no lesson in it. `[hidden]` is forced to
 * `display: none` in the shared stylesheet so a stage's own `flex` class
 * cannot outrank it.
 */
export function LessonStageController({
  hasInteractive = false,
  hasExercise = false,
  interactiveNode,
  headerNode,
  proseNode,
  exerciseNode,
  sidebarNode,
  footerNode,
  readingOptional = false,
}: LessonStageControllerProps) {
  // Reading leads unless the challenges were authored to stand alone.
  const readingLeads = !hasInteractive || !readingOptional;

  const [activeStage, setActiveStage] = useState<LessonStage>(
    readingLeads ? "read" : "play",
  );

  /**
   * The stages in the order this lesson presents them, so the numbering, the
   * captions and the tab order all come from one list rather than from three
   * places that have to be kept saying the same thing.
   */
  const order: LessonStage[] = [
    ...(readingLeads ? (["read"] as const) : []),
    ...(hasInteractive ? (["play"] as const) : []),
    ...(readingLeads ? [] : (["read"] as const)),
    ...(hasExercise ? (["code"] as const) : []),
  ];

  const label = (stage: LessonStage) => {
    const position = String(order.indexOf(stage) + 1).padStart(2, "0");
    const name =
      stage === "play"
        ? "PLAY"
        : stage === "code"
          ? "CODE"
          : readingLeads
            ? "READ"
            : "READ (OPTIONAL)";
    return `${position} · ${name}`;
  };

  const caption = (stage: LessonStage) => {
    const position = order.indexOf(stage) + 1;
    const name =
      stage === "play"
        ? "Hands-On Exploration"
        : stage === "code"
          ? "Code Practice & Verification"
          : readingLeads
            ? "Theory & Documentation"
            : "Theory & Documentation (Optional)";
    return `Stage ${position} · ${name}`;
  };

  /** The stage after this one, for the button at the foot of each stage. */
  const next = (stage: LessonStage) => order[order.indexOf(stage) + 1];

  return (
    <div className="w-full">
      {/* Top 3-Stage Navigation Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-rule pb-3">
        <nav
          aria-label="Lesson stages"
          className="flex items-center gap-2 sm:gap-4"
        >
          {order.map((stage) => (
            <button
              key={stage}
              type="button"
              aria-current={activeStage === stage ? "step" : undefined}
              onClick={() => setActiveStage(stage)}
              className={`group relative flex items-center gap-2 rounded-field px-3 py-1.5 text-caption font-mono transition-colors cursor-pointer ${
                activeStage === stage
                  ? "font-bold text-accent"
                  : "text-muted hover:text-ink hover:bg-paper-raised"
              }`}
            >
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  activeStage === stage
                    ? "bg-accent ring-4 ring-accent/15"
                    : "bg-rule-strong"
                }`}
              />
              <span>{label(stage)}</span>
              {activeStage === stage && (
                <span className="absolute -bottom-3.5 left-0 right-0 h-[2px] bg-accent" />
              )}
            </button>
          ))}
        </nav>

        <div className="text-[11px] font-mono text-muted uppercase hidden sm:block">
          {caption(activeStage)}
        </div>
      </div>

      {/* =================================================================== */}
      {/* STAGE 1: PLAY (FULL SCREEN IMMERSION, NO HERO/SIDEBAR CLUTTER)      */}
      {/* =================================================================== */}
      {hasInteractive && (
        <div className="w-full animate-fade-in" hidden={activeStage !== "play"}>
          {React.isValidElement(interactiveNode)
            ? React.cloneElement(interactiveNode as React.ReactElement<any>, {
                onGoToCode: () =>
                  setActiveStage(hasExercise ? "code" : "read"),
                onGoToRead: () => setActiveStage("read"),
                readingLeads,
              })
            : interactiveNode}
        </div>
      )}

      {/* =================================================================== */}
      {/* STAGE 2: READ (EDITORIAL DOCUMENTATION + SIDEBAR)                   */}
      {/* =================================================================== */}
      <div
        className="flex flex-col lg:flex-row lg:gap-14 animate-fade-in"
        hidden={activeStage !== "read"}
      >
        {sidebarNode && (
          <div className="w-full lg:w-64 shrink-0">{sidebarNode}</div>
        )}

        <div className="min-w-0 flex-1">
          {headerNode}

          <div className="mt-8">{proseNode}</div>

          {/* Hand off to whatever this lesson actually puts next. */}
          <div className="mt-12 flex items-center justify-between gap-4 border-t border-rule pt-6">
            {hasInteractive && !readingLeads ? (
              <button
                type="button"
                onClick={() => setActiveStage("play")}
                className="inline-flex items-center gap-2 text-caption font-mono text-muted hover:text-ink transition-colors cursor-pointer"
              >
                <span>&larr;</span>
                <span>Back to the challenges</span>
              </button>
            ) : (
              <span />
            )}

            {next("read") && (
              <button
                type="button"
                onClick={() => setActiveStage(next("read")!)}
                className="inline-flex min-h-11 items-center gap-2 rounded-field bg-accent px-5 text-caption font-medium text-white shadow-xs hover:bg-accent-deep transition-colors cursor-pointer"
              >
                <span>
                  {next("read") === "play"
                    ? "Start the challenges"
                    : "Go to the exercise"}
                </span>
                <span>&rarr;</span>
              </button>
            )}
          </div>

          {footerNode && <div className="mt-10">{footerNode}</div>}
        </div>
      </div>

      {/* =================================================================== */}
      {/* STAGE 3: CODE (SPLIT SCREEN: 50% SPECS / 50% CODE EDITOR)           */}
      {/* =================================================================== */}
      {hasExercise && (
        <div className="w-full animate-fade-in" hidden={activeStage !== "code"}>
          <div className="grid gap-8 lg:grid-cols-12">
            {/* Left 50% Column: Problem Spec, Invariants, & Requirements */}
            <div className="lg:col-span-5 space-y-6">
              {headerNode}

              <div className="rounded-xl border border-rule-strong bg-paper-sunken p-5 text-caption text-ink-soft space-y-3">
                <span className="text-[10px] font-mono font-bold uppercase text-accent">
                  Coding Objective
                </span>
                <p className="leading-relaxed">
                  Implement your solution in the editor on the right or work in
                  your local IDE. All unit tests run against your code in
                  real-time.
                </p>
                <div className="pt-2 border-t border-rule flex items-center justify-between text-[11px] font-mono text-muted">
                  <span>Language: Python 3.10+</span>
                  <span>Runner: Local / Pyodide</span>
                </div>
              </div>

              <div className="flex items-center gap-4 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveStage("read")}
                  className="text-caption font-mono text-muted hover:text-ink transition-colors cursor-pointer"
                >
                  &larr; Back to {caption("read").toLowerCase()}
                </button>
              </div>

              {footerNode && (
                <div className="pt-4 border-t border-rule">{footerNode}</div>
              )}
            </div>

            {/* Right 50% Column: Full-Height Code Editor & Live Test Grader */}
            <div className="lg:col-span-7">{exerciseNode}</div>
          </div>
        </div>
      )}
    </div>
  );
}
