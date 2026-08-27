'use client'

import { useState } from 'react'

export interface StructuredOutputWorkbenchProps {
  onGoToCode?: () => void
  onGoToRead?: () => void
}

export function StructuredOutputWorkbench({ onGoToCode, onGoToRead }: StructuredOutputWorkbenchProps) {
  const [currentStep, setCurrentStep] = useState<number>(0)

  // Step 1: Human Extraction Task (No handholding)
  const [step1Input, setStep1Input] = useState<string>(
    `Sure! Here is the extracted order data you requested:\n\`\`\`json\n{\n  "customer_name": "Ana Silva",\n  "order_id": "ORD-401",\n  "quantity": 3,\n  "status": "open"\n}\n\`\`\`\nHope this helps with your processing!`,
  )
  const [step1Hint, setStep1Hint] = useState<string | null>(null)
  const [step1Passed, setStep1Passed] = useState<boolean>(false)

  // Step 2: Human Schema Repair Task (No handholding)
  const [step2Input, setStep2Input] = useState<string>(
    `{\n  "customer_name": "Ana Silva",\n  "quantity": "two",\n  "status": "pending"\n}`,
  )
  const [step2Hint, setStep2Hint] = useState<string | null>(null)
  const [step2Passed, setStep2Passed] = useState<boolean>(false)

  // Step 3: Human Feedback Prompt Construction (No handholding)
  const [step3Hint, setStep3Hint] = useState<string | null>(null)
  const [step3Passed, setStep3Passed] = useState<boolean>(false)
  const [selectedStrategy, setSelectedStrategy] = useState<'vague' | 'error_only' | 'precise' | null>(null)

  // Verification 1
  const handleCheckStep1 = () => {
    const trimmed = step1Input.trim()
    if (trimmed.startsWith('Sure') || trimmed.includes('Hope this helps')) {
      setStep1Hint('Hint: Strip the conversational preamble ("Sure!...") and closing remarks ("Hope this helps!"). Only the JSON object should remain.')
      return
    }
    if (trimmed.startsWith('```') || trimmed.endsWith('```')) {
      setStep1Hint('Hint: Strip the opening ```json and closing ``` markdown code fences.')
      return
    }
    try {
      const parsed = JSON.parse(trimmed)
      if (typeof parsed === 'object' && parsed !== null && parsed.customer_name === 'Ana Silva') {
        setStep1Hint(null)
        setStep1Passed(true)
      } else {
        setStep1Hint('Hint: The extracted JSON must be a valid object with fields customer_name, order_id, quantity, and status.')
      }
    } catch {
      setStep1Hint('Hint: The string does not parse as valid JSON yet. Make sure opening { and closing } are balanced.')
    }
  }

  // Verification 2
  const handleCheckStep2 = () => {
    try {
      const parsed = JSON.parse(step2Input.trim())
      if (typeof parsed.quantity !== 'number' || typeof parsed.quantity === 'boolean') {
        setStep2Hint('Hint: "quantity" must be an integer (e.g. 2), not a string ("two") or boolean.')
        return
      }
      if (!['open', 'shipped', 'closed'].includes(parsed.status)) {
        setStep2Hint(`Hint: "status" must be one of ["open", "shipped", "closed"], got "${parsed.status}".`)
        return
      }
      if (typeof parsed.customer_name !== 'string' || !parsed.customer_name) {
        setStep2Hint('Hint: "customer_name" must be a non-empty string.')
        return
      }
      setStep2Hint(null)
      setStep2Passed(true)
    } catch (err) {
      setStep2Hint(`Hint: Syntax error in JSON: ${(err as Error).message}`)
    }
  }

  // Verification 3
  const handleCheckStep3 = (strategy: 'vague' | 'error_only' | 'precise') => {
    setSelectedStrategy(strategy)
    if (strategy === 'vague') {
      setStep3Hint('Hint: Vague feedback ("try again") fails because the model does not know which field violated the schema.')
      setStep3Passed(false)
    } else if (strategy === 'error_only') {
      setStep3Hint('Hint: Sending only the error without the previous reply deprives the model of the context it needs to modify.')
      setStep3Passed(false)
    } else {
      setStep3Hint(null)
      setStep3Passed(true)
    }
  }

  return (
    <div className="my-2 w-full font-sans">
      {/* Top Segmented Progress Bar */}
      <div className="mb-6 flex items-center justify-between gap-4 border-b border-rule pb-3">
        <div className="flex flex-1 items-center gap-2">
          {[0, 1, 2, 3, 4].map((stepIdx) => {
            const isFilled = currentStep >= stepIdx
            return (
              <div
                key={stepIdx}
                className={`h-2 flex-1 rounded-full transition-all duration-300 ${
                  isFilled ? 'bg-accent' : 'bg-rule-strong'
                }`}
              />
            )
          })}
        </div>
        <span className="text-caption font-mono font-medium text-muted shrink-0">
          {currentStep === 0
            ? 'Overview'
            : currentStep === 4
            ? 'Complete'
            : `Challenge ${currentStep} of 3`}
        </span>
      </div>

      {/* =================================================================== */}
      {/* SCREEN 0: THE HOOK / HERO COVER                                     */}
      {/* =================================================================== */}
      {currentStep === 0 && (
        <div className="grid gap-8 lg:grid-cols-12 py-4 animate-in fade-in duration-300 items-center">
          <div className="lg:col-span-7 space-y-4">
            <p className="text-eyebrow font-mono uppercase text-accent font-semibold">
              Interactive Hands-On Exploration
            </p>
            <h2 className="font-serif text-[clamp(1.75rem,2.8vw,2.25rem)] text-ink leading-tight">
              The Structured Output Problem
            </h2>
            <p className="text-lead font-serif text-ink-soft">
              Language models emit unstructured natural language. In this 3-minute interactive challenge, you will discover how to isolate JSON strings, enforce domain schema invariants, and assemble self-healing feedback loops.
            </p>

            <div className="pt-2">
              <button
                onClick={() => setCurrentStep(1)}
                className="inline-flex min-h-11 items-center justify-center rounded-field bg-accent px-8 text-caption font-semibold text-white shadow-sm hover:bg-accent-deep active:scale-98 transition-all cursor-pointer"
              >
                Start Challenge 1 &rarr;
              </button>
            </div>
          </div>

          <div className="lg:col-span-5 flex justify-center">
            <div className="w-full max-w-sm rounded-xl border border-rule-strong bg-paper-sunken p-6 shadow-sm space-y-4">
              <div className="text-[11px] font-mono uppercase font-bold text-muted border-b border-rule pb-2">
                Pipeline Architecture
              </div>
              <div className="flex items-center justify-between font-mono text-xs">
                <span className="text-ink">1. Raw LLM Stream</span>
                <span className="text-muted">&rarr; Text</span>
              </div>
              <div className="flex items-center justify-between font-mono text-xs">
                <span className="text-accent font-semibold">2. Extraction &amp; Parse</span>
                <span className="text-accent font-semibold">&rarr; JSON Object</span>
              </div>
              <div className="flex items-center justify-between font-mono text-xs">
                <span className="text-pass font-semibold">3. Domain Invariants</span>
                <span className="text-pass font-semibold">&rarr; Strict DB Types</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SCREEN 1: CHALLENGE 1 - EXTRACT CLEAN JSON (2-COLUMN GRID)          */}
      {/* =================================================================== */}
      {currentStep === 1 && (
        <div className="grid gap-8 lg:grid-cols-12 py-2 animate-in fade-in duration-300">
          {/* Left Column: Challenge Description & Guidelines */}
          <div className="lg:col-span-5 space-y-4">
            <div>
              <span className="text-[11px] font-mono uppercase text-accent font-bold">Challenge 01</span>
              <h3 className="font-serif text-title text-ink mt-0.5">
                Strip Markdown &amp; Prose Noise
              </h3>
            </div>

            <p className="text-caption text-ink-soft leading-relaxed">
              When an LLM responds, it frequently wraps output in conversational preamble (&quot;Sure! Here is the order...&quot;) and markdown fences (<code>```json</code>).
            </p>

            <div className="rounded-lg border border-rule bg-paper-sunken p-4 text-caption text-ink-soft space-y-2">
              <strong className="block text-ink font-semibold text-[12px]">Your Objective:</strong>
              <p>
                Edit the text buffer on the right so that <strong>only the pure JSON object</strong> remains. Strip the preamble, closing remarks, and markdown code fences.
              </p>
            </div>

            {step1Hint && (
              <div className="rounded-lg border border-fail/30 bg-fail/5 p-4 text-caption font-mono text-fail animate-in fade-in">
                {step1Hint}
              </div>
            )}
          </div>

          {/* Right Column: User Editable Buffer & Action Controls */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between text-[11px] font-mono text-muted uppercase font-semibold">
              <span>Editable Response Buffer:</span>
              <button
                onClick={() => {
                  setStep1Input(
                    `{\n  "customer_name": "Ana Silva",\n  "order_id": "ORD-401",\n  "quantity": 3,\n  "status": "open"\n}`,
                  )
                }}
                className="text-accent hover:underline text-[11px] cursor-pointer"
              >
                Auto-Strip Helper
              </button>
            </div>

            <textarea
              value={step1Input}
              onChange={(e) => {
                setStep1Input(e.target.value)
                setStep1Hint(null)
              }}
              rows={11}
              className="w-full rounded-lg border-2 border-rule-strong bg-paper p-4 font-mono text-xs text-ink leading-relaxed focus:border-accent focus:outline-none shadow-sm"
              placeholder="Paste or clean the JSON object here..."
            />

            <div className="flex items-center justify-between pt-2">
              {!step1Passed ? (
                <button
                  onClick={handleCheckStep1}
                  className="inline-flex min-h-11 items-center justify-center rounded-field bg-accent px-8 text-caption font-semibold text-white shadow-sm hover:bg-accent-deep active:scale-98 transition-all cursor-pointer"
                >
                  Check Extraction Answer
                </button>
              ) : (
                <div className="flex flex-wrap items-center gap-4 animate-in fade-in">
                  <span className="rounded-full bg-pass/10 px-4 py-2 text-caption font-semibold text-pass">
                    ✓ Clean JSON Object Isolated!
                  </span>
                  <button
                    onClick={() => setCurrentStep(2)}
                    className="inline-flex min-h-11 items-center justify-center rounded-field bg-pass px-6 text-caption font-semibold text-white shadow-sm hover:bg-pass/90 transition-all cursor-pointer"
                  >
                    Continue to Challenge 2 &rarr;
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SCREEN 2: CHALLENGE 2 - SCHEMA REPAIR (2-COLUMN GRID)               */}
      {/* =================================================================== */}
      {currentStep === 2 && (
        <div className="grid gap-8 lg:grid-cols-12 py-2 animate-in fade-in duration-300">
          {/* Left Column: Declared Schema Contract & Rules */}
          <div className="lg:col-span-5 space-y-4">
            <div>
              <span className="text-[11px] font-mono uppercase text-accent font-bold">Challenge 02</span>
              <h3 className="font-serif text-title text-ink mt-0.5">
                Enforce Schema Invariants
              </h3>
            </div>

            <p className="text-caption text-ink-soft leading-relaxed">
              Syntactically valid JSON is not enough. Your SQL database and Python business logic require strict field types and enum invariants.
            </p>

            <div className="rounded-lg border border-rule-strong bg-paper-sunken p-4 font-mono text-xs space-y-2 shadow-xs">
              <div className="text-[10px] text-muted uppercase font-bold tracking-wider border-b border-rule pb-1.5">
                Declared Schema Contract:
              </div>
              <div className="text-[11px] space-y-1 text-ink-soft">
                <div><span className="text-accent font-semibold">&quot;customer_name&quot;</span>: {'{ "type": "string" }'}</div>
                <div><span className="text-accent font-semibold">&quot;quantity&quot;</span>: {'{ "type": "integer" }'}</div>
                <div><span className="text-accent font-semibold">&quot;status&quot;</span>: {'{ "type": "string", "enum": ["open", "shipped", "closed"] }'}</div>
              </div>
            </div>

            {step2Hint && (
              <div className="rounded-lg border border-fail/30 bg-fail/5 p-4 text-caption font-mono text-fail animate-in fade-in">
                {step2Hint}
              </div>
            )}
          </div>

          {/* Right Column: User Editable JSON */}
          <div className="lg:col-span-7 space-y-4">
            <div className="text-[11px] font-mono text-muted uppercase font-semibold">
              Model Output (Edit to satisfy schema):
            </div>

            <textarea
              value={step2Input}
              onChange={(e) => {
                setStep2Input(e.target.value)
                setStep2Hint(null)
              }}
              rows={11}
              className="w-full rounded-lg border-2 border-rule-strong bg-paper p-4 font-mono text-xs text-ink leading-relaxed focus:border-accent focus:outline-none shadow-sm"
            />

            <div className="flex items-center justify-between pt-2">
              {!step2Passed ? (
                <button
                  onClick={handleCheckStep2}
                  className="inline-flex min-h-11 items-center justify-center rounded-field bg-accent px-8 text-caption font-semibold text-white shadow-sm hover:bg-accent-deep active:scale-98 transition-all cursor-pointer"
                >
                  Check Schema Validation
                </button>
              ) : (
                <div className="flex flex-wrap items-center gap-4 animate-in fade-in">
                  <span className="rounded-full bg-pass/10 px-4 py-2 text-caption font-semibold text-pass">
                    ✓ Invariants Verified: Types &amp; Enums Safe!
                  </span>
                  <button
                    onClick={() => setCurrentStep(3)}
                    className="inline-flex min-h-11 items-center justify-center rounded-field bg-pass px-6 text-caption font-semibold text-white shadow-sm hover:bg-pass/90 transition-all cursor-pointer"
                  >
                    Continue to Challenge 3 &rarr;
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SCREEN 3: CHALLENGE 3 - THE RETRY PROMPT (2-COLUMN GRID)            */}
      {/* =================================================================== */}
      {currentStep === 3 && (
        <div className="grid gap-8 lg:grid-cols-12 py-2 animate-in fade-in duration-300">
          {/* Left Column: Feedback Concept & Hints */}
          <div className="lg:col-span-5 space-y-4">
            <div>
              <span className="text-[11px] font-mono uppercase text-accent font-bold">Challenge 03</span>
              <h3 className="font-serif text-title text-ink mt-0.5">
                Automated Feedback Recovery
              </h3>
            </div>

            <p className="text-caption text-ink-soft leading-relaxed">
              When an LLM fails schema validation in production, what feedback message gives the highest probability of immediate self-correction on Turn 2?
            </p>

            {step3Hint && (
              <div className="rounded-lg border border-fail/30 bg-fail/5 p-4 text-caption font-mono text-fail animate-in fade-in">
                {step3Hint}
              </div>
            )}
          </div>

          {/* Right Column: Interactive Strategy Selectors */}
          <div className="lg:col-span-7 space-y-3">
            <button
              onClick={() => handleCheckStep3('vague')}
              className={`w-full rounded-lg border p-4 text-left font-mono text-xs transition-all cursor-pointer ${
                selectedStrategy === 'vague'
                  ? 'border-fail bg-fail/5 ring-1 ring-fail text-fail'
                  : 'border-rule bg-paper hover:bg-paper-sunken text-ink'
              }`}
            >
              <span className="text-[10px] text-muted uppercase block font-bold mb-1">Strategy A: Vague Nudge</span>
              &quot;Your last response was wrong. Please try again.&quot;
            </button>

            <button
              onClick={() => handleCheckStep3('error_only')}
              className={`w-full rounded-lg border p-4 text-left font-mono text-xs transition-all cursor-pointer ${
                selectedStrategy === 'error_only'
                  ? 'border-fail bg-fail/5 ring-1 ring-fail text-fail'
                  : 'border-rule bg-paper hover:bg-paper-sunken text-ink'
              }`}
            >
              <span className="text-[10px] text-muted uppercase block font-bold mb-1">Strategy B: Validator Error Only</span>
              &quot;ValidationError: quantity: expected integer, got str.&quot;
            </button>

            <button
              onClick={() => handleCheckStep3('precise')}
              className={`w-full rounded-lg border-2 p-4 text-left font-mono text-xs transition-all cursor-pointer ${
                selectedStrategy === 'precise'
                  ? 'border-pass bg-pass/10 ring-2 ring-pass text-ink'
                  : 'border-accent/40 bg-paper hover:bg-accent/5 text-ink'
              }`}
            >
              <span className="text-[10px] text-accent uppercase block font-bold mb-1">Strategy C: 2-Turn Context + Specific Error (Recommended)</span>
              Attach bad reply in history + user prompt: &quot;That reply was not usable: quantity: expected integer, got str. Return only corrected JSON.&quot;
            </button>

            {step3Passed && (
              <div className="pt-4 flex items-center justify-between animate-in fade-in">
                <span className="rounded-full bg-pass/10 px-4 py-2 text-caption font-semibold text-pass">
                  ✓ Model Self-Corrected on Turn 2!
                </span>
                <button
                  onClick={() => setCurrentStep(4)}
                  className="inline-flex min-h-11 items-center justify-center rounded-field bg-pass px-6 text-caption font-semibold text-white shadow-sm hover:bg-pass/90 transition-all cursor-pointer"
                >
                  Complete Exploration &rarr;
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SCREEN 4: COMPLETION - 2 CHOICES: WRITE CODE OR READ OPTIONAL       */}
      {/* =================================================================== */}
      {currentStep === 4 && (
        <div className="flex flex-col items-center text-center py-6 sm:py-8 animate-in fade-in duration-300">
          <div className="rounded-full bg-pass/10 p-3 text-pass font-bold text-lg mb-2">
            🎉 Visual Intuition Mastered!
          </div>

          <h2 className="font-serif text-[clamp(1.75rem,2.8vw,2.25rem)] text-ink leading-tight">
            You are ready to build the solution
          </h2>
          <p className="mt-2 max-w-[54ch] text-lead font-serif text-ink-soft">
            You have mastered extraction, schema validation, and retry recovery. Choose where you want to go next:
          </p>

          {/* The 2 Clear Pathways */}
          <div className="mt-8 grid gap-6 sm:grid-cols-2 w-full max-w-2xl">
            {/* Primary Choice: Write Code */}
            <button
              onClick={() => {
                if (onGoToCode) onGoToCode()
              }}
              className="flex flex-col items-start justify-between rounded-xl border-2 border-accent bg-accent/5 p-6 text-left transition-all hover:bg-accent/10 hover:shadow-md cursor-pointer group"
            >
              <div>
                <span className="text-[10px] font-mono uppercase font-bold text-accent">Recommended</span>
                <h4 className="font-serif text-title text-ink mt-1 group-hover:text-accent transition-colors">
                  Write the Code &rarr;
                </h4>
                <p className="mt-2 text-caption text-ink-soft leading-relaxed">
                  Open the exercise buffer, implement <code className="font-mono text-accent">extract_json</code>, <code className="font-mono text-accent">validate</code>, and pass all unit tests in <code className="font-mono text-accent">solution.py</code>.
                </p>
              </div>
              <div className="mt-6 inline-flex rounded-field bg-accent px-5 py-2.5 text-caption font-semibold text-white shadow-xs group-hover:bg-accent-deep transition-colors">
                Start Coding Exercise (Stage 03)
              </div>
            </button>

            {/* Secondary Choice: Read Theory (Optional) */}
            <button
              onClick={() => {
                if (onGoToRead) onGoToRead()
              }}
              className="flex flex-col items-start justify-between rounded-xl border border-rule-strong bg-paper p-6 text-left transition-all hover:bg-paper-sunken hover:shadow-xs cursor-pointer group"
            >
              <div>
                <span className="text-[10px] font-mono uppercase font-bold text-muted">Optional Deep Dive</span>
                <h4 className="font-serif text-title text-ink mt-1 group-hover:text-ink transition-colors">
                  Read Theory &amp; Notes
                </h4>
                <p className="mt-2 text-caption text-ink-soft leading-relaxed">
                  Browse the comprehensive editorial documentation on constrained decoding token masks, length truncations, and production case studies.
                </p>
              </div>
              <div className="mt-6 inline-flex rounded-field border border-rule-strong px-5 py-2.5 text-caption font-semibold text-ink-soft group-hover:text-ink transition-colors">
                Read Documentation (Stage 02)
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
