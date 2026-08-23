# Curriculum

What the course teaches, in what order, and why each module exists. `docs/PLAN.md` records
the build decisions. This file records the content decisions, and it is the thing to read
before adding or moving a lesson.

## The destination

A student who finishes has built two working systems, offline, against a scripted model
client:

A support agent that answers from a knowledge base, refuses to answer what it cannot ground,
escalates on a contract rather than on a guess, and is graded by a harness that fails it for
escalating too early and for refusing too long.

A research pipeline that fans questions out to workers, writes one brief, and verifies every
cited claim against the source text before anything ships, with an accountant attached that
shows what the fan out cost.

Everything before those two modules exists to make them buildable. A lesson that does not
lead somewhere in that sentence is a lesson to cut.

## The spine

The course is one idea developed in eleven steps: **a model call is stateless, so every
useful system is a loop you own, and everything hard is about what you put in the loop and
how you know it worked.**

| Step | Module | The idea it adds |
|---|---|---|
| 0 | Foundations | The toolchain, and the response shape everything else reads. |
| 1 | LLM fundamentals | The call is stateless and bounded. You own the conversation. |
| 2 | Prompt engineering | What goes in the call, and how you measure whether it worked. |
| 3 | Tool use | The loop. A model that can act, observe, and stop. |
| 4 | Agent frameworks | What an abstraction over that loop buys and costs. |
| 5 | Memory and RAG | Knowledge the model was never trained on, and a bounded prompt. |
| 6 | Multi-agent and production | More than one loop, and how you know any of it works. |
| 7 | State graphs | One runtime style, rebuilt: durable state and resume. |
| 8 | Handoffs and typed output | The other runtime style, rebuilt: control and contracts. |
| 9 | Support triage | Everything, applied to one agent with a behaviour contract. |
| 10 | Research briefing | Everything, applied to many agents with a verification pass. |

Tracks: modules 0 to 2 are `base`, 3 to 6 are `agent`, 7 and 8 are `frameworks`, 9 and 10 are
`projects`. `order` is global across tracks, not per track.

## Where each idea is introduced, and where it is paid off

The through lines are what make the course feel like one course. Each is introduced once,
deliberately small, and cashed in later.

| Thread | Introduced | Paid off |
|---|---|---|
| The response shape and `finish_reason` | 0.3 reading a completion | 3.3 the ReAct loop, where it becomes the exit condition |
| The messages array as state you own | 1.4 the conversation loop | 5.5 conversation memory, 7.2 channels and reducers |
| Measurement instead of taste | 2.4 measuring a prompt | 6.3 evaluating agents, 9.4 grading the behaviour |
| Validate then retry | 2.3 structured output | 8.4 typed output and the retry loop |
| Tool call ids and message pairing | 3.3 the ReAct loop | 3.4 parallel tool calls, 8.2 handoffs are tool calls |
| Failure as an observation, not a crash | 3.5 when tools fail | 6.4 observability, 8.3 guardrails |
| A trace record per step | 4.3 middleware and tracing | 6.4 observability and cost, 10.1 what fan out costs |
| Grounding and refusing to answer | 5.4 the RAG pipeline | 9.2 grounded answers and scope |
| Decomposition and aggregation | 6.2 orchestrator and workers | 10.1 fan out, 10.2 writing the brief |
| An escalation or handoff payload | 6.1 routing and specialists | 8.2 handoffs, 9.3 when to hand over |

If you add a lesson, it belongs in this table. If it does not, ask what it is for.

## Module shape

Every module is four or five lessons, except Foundations, which is three because its job is
to get someone to a passing test rather than to teach a subject. Every lesson is divided into
three to six named subsections so a student can navigate it and return to one part.

Most modules contain one lesson with no exercise, placed where an idea needs room to be
established before anything is graded. That is usually the opening lesson. It is not a rule:
module 6 carries an exercise on all four of its lessons, and module 10 puts its exercise-free
lesson last, because "Running it for real" is the ship-it wrap-up and an exercise there would
be strange. Place it where the module needs it and do not add a lesson to satisfy a pattern.

An exercise is a directory of three files, `scaffold.py`, `reference.py` and `test.py`, run
against `mockllm` with nothing installed but Python 3.10 or newer. The gate in
`packages/learning/scripts/` refuses to ship an exercise whose reference fails its own test,
whose scaffold passes it, or whose signatures have drifted between the two.

`estimatedHours` on a module is the sum of its lesson minutes plus the sum of its exercise
timeboxes, rounded to the nearest half hour, and **a total landing exactly on a quarter hour
rounds down**. It is a measurement, not an ambition. The numbers before the 2.0.0 rebuild
were ambitions, and several were wrong by a factor of three: module 9 claimed eight hours
against content measuring four and five sixths.

Ties round down because the error is friendlier in that direction. Nobody resents finishing
early. Module 8 is the current tie, at 255 minutes.

`timeboxMinutes` measures the exercise, not the lesson. It is calibrated by counting the
distinct decisions the exercise requires, which is how every box in the course was set. A long
lesson followed by a short box is not a mistake: module 3's ReAct lesson is the longest in the
course at 60 minutes and its exercise is boxed at 30, because the exercise is three small
functions and one that composes them with `dispatch` given. If you ever want boxes to track
lesson weight instead, that is a different rule and it has to be applied to all eleven modules
at once, not to the module that prompted the thought.

A consequence worth stating, because it looks like an inconsistency and is not: `difficulty`
is not monotonic with `order`. Module 6 is advanced while modules 7 and 8, which follow it,
are intermediate. They are different tracks, and a student on the agent track finishes at 6.

## Full module map

Lesson ids are `<module-id>.<slug>`. Exercise ids are directory names under the module's
`exercises/`.

### 0. Foundations (`ai-foundations`, base)

| # | Lesson | Exercise |
|---|---|---|
| 1 | How this course works | |
| 2 | Check your setup | `check-your-setup` |
| 3 | Reading a completion | `reading-a-completion` |

The third lesson is the on-ramp. A student who can read a `Completion`, branch on
`finish_reason` and find `usage` has met every object the rest of the course uses.

### 1. LLM fundamentals (`ai-llm-fundamentals`, base)

| # | Lesson | Exercise |
|---|---|---|
| 1 | What a model does | |
| 2 | Tokens and context | `context-budget` |
| 3 | Sampling | `sampling-controls` |
| 4 | The conversation loop | `conversation-loop` |

Sampling is built rather than described. A student who has written `softmax`, temperature
scaling and a nucleus filter does not have to take temperature on faith.

### 2. Prompt engineering (`ai-prompt-engineering`, base)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Anatomy of a prompt | |
| 2 | Teaching with examples | `prompt-assembly` |
| 3 | Structured output | `structured-output` |
| 4 | Measuring a prompt | `prompt-eval` |

The fourth lesson is what separates this module from the genre. A prompt change without a
measurement is a guess, and the harness built here is the direct ancestor of the agent harness
in module 6 and the persona harness in module 9.

### 3. Tool use and building an agent (`ai-tool-use`, agent)

| # | Lesson | Exercise |
|---|---|---|
| 1 | What makes an agent | |
| 2 | Tool schemas | `tool-schemas` |
| 3 | The ReAct loop | `react-loop` |
| 4 | Parallel tool calls | `parallel-dispatch` |
| 5 | When tools fail | `resilient-agent` |

The spine of the course. `react-loop` is the exercise everything after it assumes.

### 4. Agent frameworks (`ai-agent-frameworks`, agent)

| # | Lesson | Exercise |
|---|---|---|
| 1 | What frameworks abstract | |
| 2 | Build a mini framework | `mini-framework` |
| 3 | Middleware and tracing | `run-tracing` |
| 4 | When to adopt one | `declarative-agent` |

This module is the bridge to 7 and 8. It teaches the abstractions so that the graph runtime
and the conversational runtime land as two answers to a question the student already has,
rather than as new material. It names real frameworks and attaches every claim to an
abstraction rather than to a version number, because that is what stays true.

### 5. Memory and RAG (`ai-memory-and-rag`, agent)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Why retrieval | |
| 2 | Chunking | `chunking` |
| 3 | Embeddings and similarity | `vector-search` |
| 4 | The RAG pipeline | `rag-pipeline` |
| 5 | Conversation memory | `memory-window` |

Retrieval and conversation memory are separated on purpose. They are different problems that
get the same word, and collapsing them is why so many implementations trim a tool exchange in
half.

The embeddings in `mockllm` are the hashing trick, so they match on shared words and cannot
match synonyms. Lessons say so rather than hiding it. Everything built here works the same way
against a real embedding API and simply gets better at paraphrase.

### 6. Multi-agent systems and production (`ai-multi-agent-and-production`, agent)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Routing and specialists | `intent-router` |
| 2 | Orchestrator and workers | `orchestrator` |
| 3 | Evaluating agents | `eval-harness` |
| 4 | Observability and cost | `run-ledger` |

The last module before the projects, so it is where "does it work" and "what did it cost"
become first class. Evaluating an agent is treated as harder than evaluating a prompt, because
there is a trajectory and not just an output.

### 7. State graphs and durable execution (`ai-state-graphs`, frameworks)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Why a graph beats a loop | |
| 2 | Channels and reducers | `channel-reducers` |
| 3 | The super-step | `super-step-engine` |
| 4 | Checkpoints, resume and time travel | `checkpoint-saver` |

### 8. Handoffs, guardrails, and typed output (`ai-handoffs-and-typed-output`, frameworks)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Two runtimes, one loop | |
| 2 | Handoffs are tool calls | `handoff-runner` |
| 3 | Guardrails that can stop a run | `guardrail-tripwire` |
| 4 | Typed output and the retry loop | `validated-output` |

### 9. Support triage that knows when to escalate (`ai-support-triage`, projects)

| # | Lesson | Exercise |
|---|---|---|
| 1 | The escalation contract | |
| 2 | Grounded answers and scope | `grounded-reply` |
| 3 | When to hand over | `escalation-contract` |
| 4 | Grading the behaviour | `persona-harness` |

### 10. Research briefing with verified citations (`ai-research-briefing`, projects)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Fan out and what it costs | `fan-out-orchestrator` |
| 2 | Writing the brief | `cited-synthesis` |
| 3 | The verification pass | `citation-verifier` |
| 4 | Running it for real | |

## Rules for changing this

**A lesson is done when a student could implement the topic from it alone.** That is the
whole test. Every claim carries the mechanism behind it, every recommendation carries its
tradeoff, and at least one idea per lesson is carried through a worked example rather than
described. The pre-2.0.0 base modules failed this by asserting rather than explaining, which
is a different failure from being brief. Do not write to a length, and do not pad a section
that has already said what it needs to.

**Facts that move do not go in prose.** No context window sizes, no token prices, no model
names presented as current. Orders of magnitude and the shape of the constraint survive; a
number does not survive the quarter.

**Contested practice is labelled as contested.** Chunk size, temperature defaults, how many
few-shot examples, when to adopt a framework. Give the tradeoff and say what you would
measure. The course loses more by sounding certain than by admitting the answer is local.

**Every exercise earns its timebox.** Twenty minutes of work, not five minutes of work and
fifteen of guessing what the docstring wanted. If the tests can be passed by reading the test
file instead of the lesson, the exercise is wrong.

**If a test reads a string the student's code produced, the docstring names what must be in
it.** Grade the values the docstring demanded, never the words it happened to use. A bare
`assertIn("cap", sentence)` leaves a student guessing synonyms, which is the one failure the
course promises them is never their own fault.

**Every assertion must be able to fail for a reason that is the student's.** This is a
different check from the one above and it has to be run separately. A docstring can name
exactly what a string must contain while the assertion still cannot fail, because it reads a
substring that the fixture supplies whatever the student wrote. Two such assertions shipped in
this course and both passed the graded-strings audit before failing this one.

The cheap way to run it is to copy the scaffold to `solution.py` and run the suite. A test that
passes when every body raises `NotImplementedError` is by definition not testing the student's
work. The whole course was swept this way and came back with one cluster, the four `TestTools`
tests in `react-loop`, which grade helper code the scaffold ships complete and are grouped in
their own class for that reason.

For a single suspect assertion, mutate instead: break the behaviour in a copy of the reference
and confirm the assertion fails. If two tests catch the same mutation, that is the suite
working rather than redundancy, and it is not a reason to contrive a narrower mutation.

Do not sweep a whole suite by mutation. That was tried first and thrown away, and the reason
is the point: a catalogue of regex mutations needs you to guess what a bug looks like, and one
exercise came back clean only because none of the guesses matched it. A check whose negative
result depends on the checker's imagination is the same failure as an assertion that cannot
fail, one level up. The scaffold method has no such dependency, because the scaffold is
already the artefact meaning "none of this is implemented" and the build already maintains it.

The same trap catches the verification itself. A sweep that reuses one directory and copies
with a bare `cp` will find the copy declined, leave the reference in place, and report every
test passing against the scaffold, which reads as catastrophe rather than as a broken checker.
Use a fresh directory per exercise. A verification step that silently does nothing produces a
green result.

**Lesson prose must name the symbols its exercise exports.** The build validates scaffold,
reference and test against each other and never checks the lesson against them, so a rename
ships green and reaches the student as an `ImportError` naming a symbol the lesson just told
them to write.

**One module owns a topic at mechanism depth. The others keep the consequence and link.**
Three people writing in parallel will each decide the same idea is too important to leave to
someone else, and the course ends up explaining prompt caching three times. The rule has no
exemption for the version that happens to be interesting.

**Handing content forward is safe. Handing a promise forward needs checking from both ends.**
The failure looks like this: an author compresses a section and reaches for a link to carry
what they cut, and the destination was written by someone who never saw the sentence now
pointing at it. Neither end is wrong on its own. Whenever a link carries a claim rather than
supplements one, read the destination.

**Nothing calls a real model.** Stated in `CLAUDE.md` and repeated here because it is the
constraint most likely to be broken by someone adding a lesson in good faith.

## The reveal policy has one accepted exception

`CLAUDE.md` says exercises open on the scaffold and never the reference, because revealing the
solution is a deliberate, confirmed, recorded action. Within a module, later exercises carry
earlier ones' finished code in their scaffold prelude, so a student runs the real thing they
built rather than a stub of it. Module 8's `guardrail-tripwire` contains working
`handoff_tool_name`, `tool_schemas`, `dispatch` and `run`, which are exactly what
`handoff-runner` grades. Module 10's `citation-verifier` carries `cited-synthesis` whole.

So a student stuck on one exercise can read its answer by opening the next one's scaffold,
without the reveal being deliberate, confirmed or recorded.

This is accepted rather than overlooked. The alternative is a capstone whose parts are stubs of
each other, which is the thing that makes most course projects feel like disconnected drills.
The cost is real and it is smaller than the cost of the alternative. It is written down here so
the next person to notice knows it was a decision.
