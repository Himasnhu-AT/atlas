"""
Fan out, and what it costs: reference solution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from mockllm import cosine_similarity, embed_text

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
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Note:
    sub_query: str
    doc_id: str
    quote: str
    worker: str


class BudgetExceeded(RuntimeError):
    """The run spent more than it was allowed to spend."""

    def __init__(self, message: str, notes: list[Note] | None = None) -> None:
        super().__init__(message)
        self.notes: list[Note] = list(notes or [])


@dataclass
class Budget:
    limit: int
    spent: int = 0
    by_stage: dict[str, int] = field(default_factory=dict)

    def charge(self, stage: str, usage) -> None:
        # Record first, then complain. A meter that discards the reading it
        # tripped on cannot tell you what the run actually cost.
        self.spent += usage.total_tokens
        self.by_stage[stage] = self.by_stage.get(stage, 0) + usage.total_tokens
        if self.spent > self.limit:
            raise BudgetExceeded(
                f"budget of {self.limit} tokens exceeded at stage {stage!r}: "
                f"spent {self.spent}"
            )


@dataclass(frozen=True)
class WorkerOutput:
    """
    What one worker produced, and what it threw away.

    `dropped` is counted here because here is the only place that knows it. A
    fabricated note is discarded inside run_worker, and a count discarded at the
    point of discarding cannot be recovered by anything downstream.
    """

    notes: list[Note]
    dropped: int = 0


@dataclass
class Research:
    question: str
    sub_queries: list[str]
    notes: list[Note]
    budget: Budget
    # The documents this run read. A note carries a doc id and nothing else, so
    # without these the brief cannot turn a citation into a title.
    corpus: list[Doc] = field(default_factory=list)
    # Notes the workers refused, summed over the run. This is the fabrication
    # rate, and it is only a number you have if you kept it.
    dropped: int = 0


def make_search(corpus: list[Doc]) -> Callable[[str, int], list[Doc]]:
    # Embed once, at build time. A worker that re-embedded the corpus on every
    # search would do the same arithmetic four times per run.
    vectors = {doc.id: embed_text(f"{doc.title} {doc.text}") for doc in corpus}
    documents = list(corpus)

    def search(query: str, k: int = 3) -> list[Doc]:
        wanted = embed_text(query)
        ranked = sorted(
            documents,
            key=lambda doc: (-cosine_similarity(wanted, vectors[doc.id]), doc.id),
        )
        return ranked[: max(k, 0)]

    return search


def plan(client, question: str, max_sub_queries: int = 4, budget: Budget | None = None) -> list[str]:
    response = client.chat.completions.create(
        model="mock",
        messages=[
            {
                "role": "system",
                "content": (
                    "Break the question into independent sub questions. Each one must "
                    "be answerable on its own, with no reference to the others."
                ),
            },
            {"role": "user", "content": question},
        ],
        tools=PLAN_TOOLS,
    )
    if budget is not None:
        budget.charge("plan", response.usage)

    call = response.choices[0].message.tool_calls[0]
    raw = json.loads(call.function.arguments).get("sub_queries") or []

    kept: list[str] = []
    for item in raw:
        candidate = str(item).strip()
        if not candidate or candidate in kept:
            continue
        kept.append(candidate)

    kept = kept[:max_sub_queries]
    # An empty plan is not a reason to answer nothing. One worker on the
    # original question is the honest floor.
    return kept or [question]


def run_worker(
    client,
    search,
    sub_query: str,
    budget: Budget,
    worker: str,
    k: int = 2,
) -> WorkerOutput:
    documents = search(sub_query, k)
    allowed = {doc.id for doc in documents}

    rendered = "\n\n".join(f"[{doc.id}] {doc.title}\n{doc.text}" for doc in documents)
    response = client.chat.completions.create(
        model="mock",
        messages=[
            {
                "role": "system",
                "content": (
                    "Record quotes that answer the sub question. Quote the documents "
                    "below exactly, and cite nothing that is not among them."
                ),
            },
            {"role": "user", "content": f"Sub question: {sub_query}\n\n{rendered}"},
        ],
        tools=NOTE_TOOLS,
    )
    budget.charge("worker", response.usage)

    call = response.choices[0].message.tool_calls[0]
    raw = json.loads(call.function.arguments).get("notes") or []

    notes: list[Note] = []
    dropped = 0
    for item in raw:
        doc_id = str(item.get("doc_id", ""))
        quote = str(item.get("quote", ""))
        # The worker only saw `documents`. A citation to anything else was
        # invented, and inventions are cheaper to drop here than to chase later.
        if doc_id not in allowed:
            dropped += 1
            continue
        notes.append(Note(sub_query=sub_query, doc_id=doc_id, quote=quote, worker=worker))
    return WorkerOutput(notes=notes, dropped=dropped)


def orchestrate(
    client,
    search,
    corpus: list[Doc],
    question: str,
    budget: Budget,
    max_sub_queries: int = 4,
) -> Research:
    sub_queries = plan(client, question, max_sub_queries=max_sub_queries, budget=budget)

    notes: list[Note] = []
    dropped = 0
    try:
        for index, sub_query in enumerate(sub_queries, start=1):
            output = run_worker(client, search, sub_query, budget, f"w{index}")
            notes.extend(output.notes)
            dropped += output.dropped
    except BudgetExceeded as exceeded:
        # Work already paid for is work already done. Hand it back.
        exceeded.notes = notes
        raise

    return Research(
        question=question,
        sub_queries=sub_queries,
        notes=notes,
        budget=budget,
        # `search` is a closure and deliberately hides the corpus it ranks, so
        # the run has to record what it was reading. The next stage turns a doc
        # id into a title and cannot do it from the notes alone.
        corpus=list(corpus),
        dropped=dropped,
    )
