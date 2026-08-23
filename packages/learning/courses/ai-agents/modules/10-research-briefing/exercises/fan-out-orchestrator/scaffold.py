"""
Fan out, and what it costs.

An orchestrator that splits a question into independent sub questions, sends one
worker after each, and keeps a running total of what the whole thing cost.

The corpus is not in this file. `test.py` builds it and hands it to
`make_search`, because "a worker only ever sees the documents its own search
returned" is the property being graded, and a module level corpus would make
that impossible to check.

Run `python3 test.py` when you think you have it.

Gotcha: `from __future__ import annotations` makes every annotation a string, so
`budget: Budget` below resolves fine even before Budget exists. It also means no
annotation is ever checked at runtime. Nothing stops you returning the wrong
shape; only the tests will.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from mockllm import cosine_similarity, embed_text

# The tool schemas the scripted model answers with. You do not have to change
# these, but read them: they are the contract each model call is working to.
PLAN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "plan",
            "description": "Break a research question into independent sub questions.",
            "parameters": {
                "type": "object",
                "properties": {"sub_queries": {"type": "array", "items": {"type": "string"}}},
                "required": ["sub_queries"],
            },
        },
    }
]

NOTE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "record_notes",
            "description": "Record quotes from the documents you were given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "doc_id": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                            "required": ["doc_id", "quote"],
                        },
                    }
                },
                "required": ["notes"],
            },
        },
    }
]


@dataclass(frozen=True)
class Doc:
    """One document in the corpus. Given to you."""

    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Note:
    """
    One quote a worker took from one document. Given to you.

    `worker` is there so the brief can say which worker found what, and so a
    single misbehaving worker is traceable after the fact.
    """

    sub_query: str
    doc_id: str
    quote: str
    worker: str


class BudgetExceeded(RuntimeError):
    """
    The run spent more than it was allowed to spend. Given to you.

    `notes` carries the work that was already paid for. Raising with an empty
    list throws away tokens you have already been billed for.
    """

    def __init__(self, message: str, notes: list[Note] | None = None) -> None:
        super().__init__(message)
        self.notes: list[Note] = list(notes or [])


@dataclass
class Budget:
    """
    The meter. One per run, shared by every stage.

    Declare three fields, in this order:

        limit: int
        spent: int = 0
        by_stage: dict[str, int] = field(default_factory=dict)

    `by_stage` must use `field(default_factory=dict)`. A bare `{}` default is a
    mutable default, and every Budget you ever create would share one dict.
    Python's dataclass decorator raises rather than let you do it.
    """

    def charge(self, stage: str, usage) -> None:
        """
        Bill one model call to a stage.

        `usage` is the `usage` attribute of a completion, and `usage.total_tokens`
        is the number you want.

        Add that number to `spent` and to `by_stage[stage]`, creating the key on
        first use, so that afterwards `spent == sum(by_stage.values())`.

        Then, if `spent` is now strictly greater than `limit`, raise
        `BudgetExceeded`. Record the spend BEFORE raising: the call happened and
        you were billed for it, and a meter that drops the reading it tripped on
        cannot tell you what the run cost.

        Spending exactly the limit is fine. The limit is a ceiling, not a wall
        one token short of it.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class WorkerOutput:
    """
    What one worker produced, and what it threw away. Given to you.

    Attributes:
        notes: the notes that survived the check below.
        dropped: how many were discarded for citing a document this worker was
            never given. Counted here because here is the only place that knows:
            a fabricated note is thrown away inside run_worker, and a count
            thrown away with it cannot be recovered by anything downstream. It
            is your fabrication rate, and a jump in it is the earliest sign a
            prompt change went wrong.
    """

    notes: list[Note]
    dropped: int = 0


@dataclass
class Research:
    """Everything one research run gathered. Given to you."""

    question: str
    sub_queries: list[str]
    notes: list[Note]
    budget: Budget
    #: The documents this run read. A note carries a doc id and nothing else, so
    #: the brief cannot turn a citation into a title without these.
    corpus: list[Doc] = field(default_factory=list)
    #: Notes the workers refused, summed over the run.
    dropped: int = 0


def make_search(corpus: list[Doc]) -> Callable[[str, int], list[Doc]]:
    """
    Build the search function the workers will use.

    Return a closure `search(query: str, k: int = 3) -> list[Doc]` that:
      - embeds the query with `embed_text`
      - scores every document with `cosine_similarity` against the embedding of
        that document, built from its title and its text together
      - returns the top k, highest score first, ties broken by ascending doc id

    Embed the corpus once, here, rather than inside the closure. Four workers
    calling a search that re-embeds five documents each time is four times the
    arithmetic for one answer.

    The tie break matters more than it looks. Two documents can score exactly
    the same, and a run whose results depend on Python's dict ordering is a run
    you cannot reproduce when it goes wrong.
    """
    raise NotImplementedError


def plan(client, question: str, max_sub_queries: int = 4, budget: Budget | None = None) -> list[str]:
    """
    Ask the model to split one question into independent sub questions.

    Make exactly one model call, passing `tools=PLAN_TOOLS`. The scripted reply
    is `tool_call('plan', {'sub_queries': [...]})`, so the sub questions arrive
    as JSON in `choices[0].message.tool_calls[0].function.arguments`.

    Then, in this order:
      1. strip each candidate and drop the ones that are empty
      2. drop duplicates, keeping the first occurrence and the original order
      3. truncate to `max_sub_queries`
      4. if nothing survives, return `[question]`

    Order matters. Truncating before deduplicating means three copies of one
    sub question can eat the whole budget.

    When `budget` is given, charge the call to the stage `'plan'`. Every function
    that spends has to be handed the meter, or the total is a fiction.
    """
    raise NotImplementedError


def run_worker(
    client,
    search,
    sub_query: str,
    budget: Budget,
    worker: str,
    k: int = 2,
) -> WorkerOutput:
    """
    Run one worker on one sub question.

    Steps:
      1. `documents = search(sub_query, k)`
      2. make ONE model call whose messages contain the sub question and the
         full text of those documents and nothing else, with `tools=NOTE_TOOLS`
      3. charge the call to the stage `'worker'`
      4. read `tool_call('record_notes', {'notes': [{'doc_id':.., 'quote':..}]})`
         out of the reply
      5. return a `WorkerOutput` holding one `Note` per surviving entry, each
         carrying this `sub_query` and this `worker`, and a count of the ones
         you discarded. A note is discarded when its `doc_id` was not among the
         documents this worker was given. The survivors keep their order.

    Step 2 is the isolation property the whole design rests on. A worker that
    can see another worker's documents is one long prompt wearing a costume, and
    you have paid four times for it.

    Step 5 is the cheapest fabrication check there is. The worker was handed a
    closed set of documents; a citation outside it was invented. Count what you
    drop as you drop it: this function is the last place that number exists, and
    an eval that wants a fabrication rate cannot reconstruct it later.
    """
    raise NotImplementedError


def orchestrate(
    client,
    search,
    corpus: list[Doc],
    question: str,
    budget: Budget,
    max_sub_queries: int = 4,
) -> Research:
    """
    Plan, then fan out, then hand back everything that was gathered.

    Call `plan` with this budget and this cap, then run one worker per sub
    question, naming them `'w1'`, `'w2'` and so on in order. Collect every note
    into one list, sum what the workers dropped, and return a `Research`
    carrying the question, the sub questions, the notes, the budget, the corpus
    and that dropped total.

    `corpus` is passed in even though `search` already ranks it, and the
    redundancy is the point: `search` is a closure and deliberately hides the
    documents it was built over, so a run that does not record them hands the
    next stage a pile of doc ids it cannot turn into titles. A `Research` that
    cannot name its own sources is not a finished run.

    If a `BudgetExceeded` escapes from any worker, attach the notes gathered so
    far to it (`exceeded.notes = notes`) and re-raise. Losing them means paying
    again for work already done.
    """
    raise NotImplementedError
