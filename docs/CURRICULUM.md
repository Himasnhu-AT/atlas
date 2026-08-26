# Curriculum

What the courses teach, in what order, and why each module exists. `docs/PLAN.md` records the
build decisions. This file records the content decisions, and it is the thing to read before
adding or moving a lesson.

There are four courses. Everything below the "The destination" heading describes the AI agent
engineering course, which was the first and is the longest. The data engineering course follows it,
the quantitative trading course is after that, and the introduction to programming course is at the bottom.

## Rules that apply to every course

A course declares its own tracks in `course.yaml`, and a module names one of them. There is no
global list of tracks and there should never be one again: the words that describe one
curriculum are not the words that describe another.

Nothing crosses a course boundary. A prerequisite may only name a module in its own course,
and the build refuses one that does not, because a course that cannot be started on its own is
a later chapter of another one. Cross-lesson *links* may point anywhere, and the build resolves
them into real paths.

`estimatedHours` is the sum of a module's lesson minutes and its exercise timeboxes, rounded to
the nearest half hour, with a total landing exactly on a quarter hour rounding down. It is a
measurement, not an ambition, and it is checked rather than trusted.

A course ships whatever its exercises import in its own `lib/`, copied into every workspace
rather than installed. The AI course ships `mockllm`; the data course ships a deterministic
fixture generator. Neither knows the other exists.

## Outbound links

A lesson may close with a **Seen in production** section pointing at one public engineering
write-up, with a sentence saying what to read it for. Three rules, because a link section is
easy to let rot:

The link is to the **primary source**, never to a list that collects it. Every URL was fetched
and returned 200 before it shipped; several otherwise good candidates were left out because
their host blocks a plain fetch and "probably fine" is not verified.

**One per lesson at most**, and only where the write-up illuminates the specific thing the
lesson teaches. A link that is merely on the same topic is noise, and a section of them is a
worse version of a bookmark folder.

**Say what to read it for.** These are long articles written for a different purpose, and
without a sentence of direction the reader either skips it or reads the wrong half.

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
| 6 | Agent security | Tool output and retrieved text are attacker-controlled input. |
| 7 | Self-correction | A second look is only worth what it did not read. |
| 8 | Multi-agent and production | More than one loop, and how you know any of it works. |
| 9 | State graphs | One runtime style, rebuilt: durable state and resume. |
| 10 | Handoffs and typed output | The other runtime style, rebuilt: control and contracts. |
| 11 | Support triage | Everything, applied to one agent with a behaviour contract. |
| 12 | Research briefing | Everything, applied to many agents with a verification pass. |

Tracks: modules 0 to 2 are `base`, 3 to 8 are `agent`, 9 and 10 are `frameworks`, 11 and 12 are
`projects`. `order` is global across tracks, not per track.

Modules 6 and 7 were added after the first eleven, from a survey of what the field covers that
this course did not. Both were in `docs/PLAN.md`'s original syllabus and had been dropped:
security was implicit in "guardrails" and never stated, and reflection had a module of its own
that never shipped. They sit before multi-agent because both are properties of a single agent,
and the projects then apply them.

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
| An escalation or handoff payload | 8.1 routing and specialists | 10.2 handoffs, 11.3 when to hand over |
| Untrusted text in the context | 6.1 the attack surface | 6.3 least privilege, 6.4 out-of-band checks |
| A check is worth what it did not read | 6.4 the guardrail that shares the compromise | 7.1 marking its own homework, 7.3 chain of verification |
| Keeping what you could not check | 1.3 quarantine (data course) | 7.3 unsupported claims, 7.5 ambiguous chunks |

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

### 6. Agent security (`ai-agent-security`, agent)

| # | Lesson | Exercise |
|---|---|---|
| 1 | The context is the attack surface | |
| 2 | Injection through a tool result | `injected-tool-output` |
| 3 | Least privilege for tools | `tool-permissions` |
| 4 | A guardrail that cannot be talked out of | `out-of-band-check` |

The exercise in lesson 2 asserts a false positive rate ABOVE zero on legitimate documentation.
That assertion is the lesson: a detector tight enough to catch the quiet attack flags the refund
policy page, because that page is instructions. Do not tune the patterns to make it pass.

### 7. Self-correction (`ai-self-correction`, agent)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Marking its own homework | |
| 2 | Reflection and its failure mode | `reflect-and-revise` |
| 3 | Chain of verification | `verify-claims` |
| 4 | Self-consistency | `sample-and-agree` |
| 5 | Retrieval that corrects itself | `corrective-retrieval` |

Five lessons, at the top of the range the module shape allows, because the RAG variants belong
here rather than bolted onto module 5: corrective, self and adaptive RAG are self-correction
applied to retrieval, and putting them in Memory and RAG would have made that module six
lessons and buried the connection.

The reflection exercise ends with a test asserting the loop leaves a factual error in place. It
is there so nobody mistakes reflection for verification.

### 8. Multi-agent systems and production (`ai-multi-agent-and-production`, agent)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Routing and specialists | `intent-router` |
| 2 | Orchestrator and workers | `orchestrator` |
| 3 | Evaluating agents | `eval-harness` |
| 4 | Observability and cost | `run-ledger` |

The last module before the projects, so it is where "does it work" and "what did it cost"
become first class. Evaluating an agent is treated as harder than evaluating a prompt, because
there is a trajectory and not just an output.

### 9. State graphs and durable execution (`ai-state-graphs`, frameworks)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Why a graph beats a loop | |
| 2 | Channels and reducers | `channel-reducers` |
| 3 | The super-step | `super-step-engine` |
| 4 | Checkpoints, resume and time travel | `checkpoint-saver` |

### 10. Handoffs, guardrails, and typed output (`ai-handoffs-and-typed-output`, frameworks)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Two runtimes, one loop | |
| 2 | Handoffs are tool calls | `handoff-runner` |
| 3 | Guardrails that can stop a run | `guardrail-tripwire` |
| 4 | Typed output and the retry loop | `validated-output` |

### 11. Support triage that knows when to escalate (`ai-support-triage`, projects)

| # | Lesson | Exercise |
|---|---|---|
| 1 | The escalation contract | |
| 2 | Grounded answers and scope | `grounded-reply` |
| 3 | When to hand over | `escalation-contract` |
| 4 | Grading the behaviour | `persona-harness` |

### 12. Research briefing with verified citations (`ai-research-briefing`, projects)

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

---

# The data engineering course

`courses/data-engineering`, five modules, seventeen lessons, thirteen graded exercises, in the
Python standard library alone.

## The spine

**A pipeline is a promise about data that has to keep being true tomorrow, so every stage has
to be re-runnable and every promise has to be checkable.**

| Step | Module | The idea it adds |
|---|---|---|
| 0 | Records and formats | A row is a claim, and the file is not the table you wanted. |
| 1 | Cleaning and validation | Every value is a string until something decides, and the deciding can fail. |
| 2 | Storage and query | A table refuses what a list of dicts cannot, and then you can ask questions. |
| 3 | Pipelines | Running it again is the job. Idempotence, watermarks, backfills, resume. |
| 4 | Quality and contracts | The check that notices, and the promise written down. |

Tracks: modules 0 to 2 are `handling`, 3 and 4 are `pipelines`.

## Where each idea is introduced, and where it is paid off

| Thread | Introduced | Paid off |
|---|---|---|
| Present and empty is not absent | 0.2 the short row | 1.2 missing versus invalid |
| Double counting one parent value | 0.3 exploding a list | 2.4 the multiplying join |
| A failure that returns rather than raises | 1.1 coercion | 1.2 the extract report, 4.1 the check runner |
| A rate that moved | 1.3 quarantine | 4.1 row counts against history |
| Naming the conflict you forgive | 2.2 ON CONFLICT versus OR IGNORE | 3.2 the upsert a watermark depends on |
| One transaction | 2.2 the load | 3.2 the watermark, 3.4 the run log |
| Owning a partition | 3.1 idempotence | 3.3 the backfill, 3.4 resume |
| Counting what you lost | 2.4 the join audit | 4.1 the checks, 4.3 the contract |

## Full module map

### 0. Records and formats (`de-records`, handling)

| # | Lesson | Exercise |
|---|---|---|
| 1 | What a record is | |
| 2 | Reading a messy file | `read-csv` |
| 3 | Shapes that nest | `flatten-records` |

The hand-written parser is deliberate and is never used again. Its failures are the failures
a learner will spend years diagnosing in other people's pipelines, and they are much easier to
recognise having caused them once.

### 1. Cleaning and validation (`de-cleaning`, handling)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Coercion and what it costs | `coerce-fields` |
| 2 | A schema that reports | `row-schema` |
| 3 | Quarantine, not deletion | `quarantine` |

The return type is the lesson. A function that can fail and returns only a value has to encode
failure as a value, and every value it could pick is also a legitimate answer.

### 2. Storage and query (`de-storage`, handling)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Why a table | |
| 2 | Loading a table | `load-table` |
| 3 | Indexes and the plan | `query-plan` |
| 4 | The rows a join loses | `join-audit` |

`INSERT OR IGNORE` versus `ON CONFLICT ... DO NOTHING` is the sharpest single point in the
course: the obvious spelling silently forgives every constraint, including the ones the schema
existed to enforce.

### 3. Pipelines (`de-pipelines`, pipelines)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Idempotence | |
| 2 | Watermarks | `incremental-load` |
| 3 | Backfills | `backfill` |
| 4 | The partial run | `resumable-run` |

The watermark uses `>=` and not `>`, and the reason is the whole design: overlap is cheap and
gaps are permanent.

### 4. Quality and contracts (`de-contracts`, pipelines)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Counting is a test | `row-checks` |
| 2 | Freshness | `freshness` |
| 3 | The contract | |

The last lesson has no exercise on purpose. It is the wrap-up, and it names where every earlier
piece ended up.

---

# The quantitative trading course

`courses/quant-trading`, seven modules, twenty-six lessons, twenty graded exercises, in the
Python standard library alone.

## The spine

**A backtest is a hypothesis about market mechanics that has to survive execution friction, so
every signal must be tested against causal event streams, realistic queue dynamics, and
statistical validation that penalizes multiple testing.**

| Step | Module | The idea it adds |
|---|---|---|
| 0 | Market microstructure | Trades are discrete queue interactions, not continuous curves. |
| 1 | Time series and signals | Prices drift, so you model stationary returns, streaming variance, and cointegration. |
| 2 | Event-driven backtesting | Vectorized backtests leak future state. Causal event queues prevent lookahead bias. |
| 3 | Statistical arbitrage | Market-neutral spreads, volatility-scaled momentum, and fractional Kelly sizing. |
| 4 | Derivatives and Greeks | Non-linear payoffs, closed-form Black-Scholes, Greeks, and American binomial trees. |
| 5 | Portfolio risk and liquidation | Tail risk beyond variance: VaR, Expected Shortfall, drawdown duration, and Almgren-Chriss. |
| 6 | Validation and financial ML | Dollar bars, path-dependent triple barriers, fractional differencing, and Deflated Sharpe. |

Tracks: modules 0 and 1 are `foundations`, 2 and 3 are `strategies`, 4 and 5 are `risk`, and 6 is `validation`.

## Full module map

### 0. Market microstructure and order books (`quant-microstructure`, foundations)

| # | Lesson | Exercise |
|---|---|---|
| 1 | How markets match | |
| 2 | Limit order book | `limit-order-book` |
| 3 | Spread and order book imbalance | `order-imbalance` |

### 1. Quantitative time series and signals (`quant-time-series`, foundations)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Returns and stationarity | |
| 2 | Streaming statistics | `streaming-stats` |
| 3 | Mean reversion and Ornstein-Uhlenbeck processes | `ou-estimation` |
| 4 | Cointegration and spread signals | `cointegration-spread` |

### 2. Event-driven backtesting and execution (`quant-backtesting`, strategies)

| # | Lesson | Exercise |
|---|---|---|
| 1 | The event loop | |
| 2 | Slippage and transaction costs | `execution-handler` |
| 3 | Portfolio accounting and PnL | `portfolio-ledger` |
| 4 | Building the event backtester | `event-backtester` |

### 3. Statistical arbitrage and factor models (`quant-stat-arb`, strategies)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Pairs trading and spread execution | `pairs-strategy` |
| 2 | Time-series momentum and volatility scaling | `momentum-signals` |
| 3 | Cross-sectional factor ranking and dollar neutrality | `factor-rebalancer` |
| 4 | Position sizing and the Kelly criterion | `kelly-sizing` |

### 4. Derivatives pricing and the Greeks (`quant-options`, risk)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Options and put-call parity | |
| 2 | The Black-Scholes-Merton model | `black-scholes-pricing` |
| 3 | Analytical Greeks and sensitivity risk | `analytical-greeks` |
| 4 | Binomial trees and American options | `binomial-tree` |

### 5. Portfolio risk and optimal liquidation (`quant-risk`, risk)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Value at Risk and Expected Shortfall | `var-cvar-calculator` |
| 2 | Drawdowns and duration analysis | `drawdown-tracker` |
| 3 | Sharpe and Sortino ratios | `performance-metrics` |
| 4 | Optimal liquidation and market impact | `almgren-chriss` |

### 6. Validation and financial machine learning (`quant-validation`, validation)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Financial data structures and dollar bars | `dollar-bars` |
| 2 | The triple-barrier labeling method | `triple-barrier` |
| 3 | Fractional differentiation and memory | `fractional-diff` |
| 4 | Multiple testing and the Deflated Sharpe Ratio | `deflated-sharpe` |

---

# The introduction to programming course

`courses/intro-programming`, six modules, twenty-four lessons, twenty-three graded exercises,
covering systems programming in C, object and lifecycle mechanics in C++, and dynamic runtime
execution in Python.

## The spine

**Programs translate algorithmic intent into memory operations across distinct runtime
architectures: mastering software engineering requires understanding how C manages physical
bytes, C++ builds zero-cost abstractions with deterministic lifecycles, and Python coordinates
dynamic runtime object graphs.**

| Step | Module | The idea it adds |
|---|---|---|
| 0 | Memory, bits, and pointers in C | The machine operates on physical bytes, linear addresses, stack frames, and manual heaps. |
| 1 | Data structures and binary layouts in C | Struct padding, dynamic arrays with geometric growth, linked lists, and binary wire formats. |
| 2 | RAII, objects, and lifecycles in C++ | Class invariants, deterministic scope destruction (RAII), copy vs move semantics, and smart pointers. |
| 3 | Polymorphism, vtables, and generics in C++ | Dynamic dispatch via vtables, template monomorphization, open-addressing hash maps, and binary heaps. |
| 4 | Dynamic runtimes and Python object model | The PyObject heap graph, dynamic attribute lookup, C3 linearization MRO, closures, and generators. |
| 5 | Virtual machines and cross-language architecture | Bytecode stack virtual machines, mark-and-sweep cycle garbage collection, and FFI type marshaling. |

Tracks: modules 0 and 1 are `systems`, 2 and 3 are `objects`, 4 is `scripts`, and 5 is `bridges`.

## Where each idea is introduced, and where it is paid off

| Thread | Introduced | Paid off |
|---|---|---|
| Direct memory offsets and pointers | 0.2 memory addresses and pointers | 1.1 struct layout, 2.3 move ownership buffer, 5.4 FFI marshaling |
| Manual heap allocation and free lists | 0.4 manual heap allocation | 2.2 RAII guards, 2.4 smart pointers, 5.3 mark-and-sweep GC |
| Contiguous memory vs node pointer chasing | 1.2 dynamic arrays, 1.3 linked nodes | 3.3 open-addressing hash map, 3.4 binary min-heap |
| Invariants and deterministic resource destruction | 2.1 class invariants | 2.2 RAII scope guards, 2.4 shared_ptr control blocks |
| Ownership transfer without copying | 2.3 move semantics | 4.1 PyObject reference counts, 5.2 VM operand stack transfers |
| Dynamic dispatch vs static binding | 3.1 virtual functions and vtables | 4.2 C3 linearization MRO, 5.2 VM opcode dispatch |
| Dynamic attribute lookup and object headers | 4.1 PyObject structure | 4.2 C3 MRO attribute chain, 5.4 FFI Python-to-C marshaling |
| Automatic memory management and cycles | 2.4 weak_ptr cycle avoidance | 4.1 reference count decref, 5.3 mark-and-sweep cycle collector |

## Full module map

### 0. Memory, bits, and pointers in C (`intro-c-memory`, systems)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Bits, bytes, and two's complement integers | `bit-manipulation` |
| 2 | Memory addresses and pointer arithmetic | `pointer-arithmetic` |
| 3 | Stack frames and local variable lifetimes | `call-stack-simulator` |
| 4 | Manual heap allocation and free-list allocators | `heap-allocator` |

### 1. Data structures and binary layouts in C (`intro-c-data-structures`, systems)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Struct layout, alignment, and memory padding | `struct-padding-calculator` |
| 2 | Dynamic arrays and amortized growth | `dynamic-array` |
| 3 | Linked nodes and pointer manipulation | `doubly-linked-list` |
| 4 | Binary serialization and network packet parsing | `binary-packet-parser` |

### 2. RAII, objects, and lifecycles in C++ (`intro-cpp-objects`, objects)

| # | Lesson | Exercise |
|---|---|---|
| 1 | From C structs to C++ classes and encapsulation | `value-semantics` |
| 2 | Resource acquisition is initialization (RAII) | `raii-resource-guard` |
| 3 | Copy semantics, move semantics, and ownership transfer | `move-ownership-buffer` |
| 4 | Smart pointers and reference count management | `smart-pointers` |

### 3. Polymorphism, vtables, and generic containers in C++ (`intro-cpp-generics`, objects)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Virtual functions, dynamic dispatch, and vtables | `vtable-dispatch-engine` |
| 2 | Compile-time generics, templates, and algorithms | `generic-algorithm-pipeline` |
| 3 | Hash tables, open addressing, and collision resolution | `hash-map-open-addressing` |
| 4 | Binary heaps and priority queues | `binary-heap-priority-queue` |

### 4. Dynamic runtimes and the Python object model (`intro-python-runtime`, scripts)

| # | Lesson | Exercise |
|---|---|---|
| 1 | The PyObject structure and dynamic typing | `boxed-object-model` |
| 2 | Dynamic attribute lookup and C3 linearization | `c3-linearization-mro` |
| 3 | Scopes, closures, and metaprogramming decorators | `closure-and-memoize` |
| 4 | Iterators, generator state machines, and streams | `generator-pipeline` |

### 5. Virtual machines and cross-language architecture (`intro-virtual-machines`, bridges)

| # | Lesson | Exercise |
|---|---|---|
| 1 | Compilation, bytecode interpretation, and virtual machines | |
| 2 | Building a stack-based bytecode virtual machine | `stack-virtual-machine` |
| 3 | Garbage collection, cycle detection, and mark-and-sweep | `mark-and-sweep-gc` |
| 4 | Foreign function interfaces and cross-language bridges | `ffi-marshaling-bridge` |


