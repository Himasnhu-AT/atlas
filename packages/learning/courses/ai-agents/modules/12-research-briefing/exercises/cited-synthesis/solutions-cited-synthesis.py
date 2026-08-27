"""
Writing the brief: reference solution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SYNTHESIS_SYSTEM = (
    "You are writing a short research brief from numbered notes.\n"
    "Mark every factual sentence with the tag of the note it came from, like "
    "[S1], immediately before the full stop.\n"
    "A sentence may carry more than one tag when it draws on more than one note.\n"
    "Write nothing that no note supports. If the notes do not answer part of the "
    "question, say so plainly and leave that sentence untagged."
)

# A sentence boundary is a terminator followed by whitespace. A decimal point
# has no whitespace after it, so this pattern never splits 15.5 in the first
# place. Abbreviations do have whitespace after them, which is what the merge
# pass below is for.
_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

_TAG = re.compile(r"\[S\d+\]")

_ABBREVIATIONS = frozenset({"e.g.", "i.e.", "etc.", "vs.", "cf.", "fig.", "no.", "al."})

_INITIALS = re.compile(r"^(?:[A-Za-z]\.)+$")


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
        self.spent += usage.total_tokens
        self.by_stage[stage] = self.by_stage.get(stage, 0) + usage.total_tokens
        if self.spent > self.limit:
            raise BudgetExceeded(
                f"budget of {self.limit} tokens exceeded at stage {stage!r}: "
                f"spent {self.spent}"
            )


@dataclass
class Research:
    question: str
    sub_queries: list[str]
    notes: list[Note]
    budget: Budget
    corpus: list[Doc] = field(default_factory=list)
    dropped: int = 0


@dataclass
class Claim:
    sentence: str
    tags: list[str]
    unknown_tags: list[str]


@dataclass
class Brief:
    question: str
    text: str
    claims: list[Claim]
    uncited: list[str]
    unknown: list[str]


def number_notes(notes: list[Note]) -> list[tuple[str, Note]]:
    # Sorting by doc id and then by arrival keeps the tags stable: the same
    # notes always number the same way, whichever worker came back first.
    ordered = sorted(enumerate(notes), key=lambda pair: (pair[1].doc_id, pair[0]))
    return [(f"S{position}", note) for position, (_, note) in enumerate(ordered, start=1)]


def synthesis_messages(question: str, tagged: list[tuple[str, Note]]) -> list[dict]:
    rendered = "\n".join(f"[{tag}] {note.doc_id}: {note.quote}" for tag, note in tagged)
    return [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {
            "role": "user",
            "content": f"Question: {question}\n\nNotes:\n{rendered}",
        },
    ]


def _ends_with_abbreviation(fragment: str) -> bool:
    tail = fragment.split()[-1] if fragment.split() else ""
    return tail.lower() in _ABBREVIATIONS or bool(_INITIALS.match(tail))


def split_sentences(text: str) -> list[str]:
    pieces = [piece for piece in _BOUNDARY.split(text.strip()) if piece]
    sentences: list[str] = []
    for piece in pieces:
        # A fragment ending in an abbreviation was never a sentence end, so the
        # next piece belongs to it.
        if sentences and _ends_with_abbreviation(sentences[-1]):
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    return sentences


def parse_claims(brief_text: str, known_tags: list[str]) -> list[Claim]:
    known = set(known_tags)
    claims: list[Claim] = []
    for sentence in split_sentences(brief_text):
        tags: list[str] = []
        unknown: list[str] = []
        for match in _TAG.finditer(sentence):
            tag = match.group(0)[1:-1]
            target = tags if tag in known else unknown
            if tag not in target:
                target.append(tag)
        claims.append(Claim(sentence=sentence, tags=tags, unknown_tags=unknown))
    return claims


def write_brief(client, research: Research) -> Brief:
    tagged = number_notes(research.notes)
    known_tags = [tag for tag, _ in tagged]

    # One call. Formatting per worker is the overhead this design removes.
    response = client.chat.completions.create(
        model="mock",
        messages=synthesis_messages(research.question, tagged),
    )
    # The supervisor call is a model call, so it goes on the meter under its own
    # stage. A run that meters the workers and not the synthesis reports a
    # number that is smaller than the invoice.
    research.budget.charge("synthesis", response.usage)
    prose = (response.choices[0].message.content or "").strip()

    claims = parse_claims(prose, known_tags)
    uncited = [
        claim.sentence for claim in claims if not claim.tags and not claim.unknown_tags
    ]

    unknown: list[str] = []
    for claim in claims:
        for tag in claim.unknown_tags:
            if tag not in unknown:
                unknown.append(tag)

    cited = {tag for claim in claims for tag in claim.tags}
    sources: list[str] = []
    titles = {doc.id: doc.title for doc in research.corpus}
    for tag, note in tagged:
        if tag in cited and note.doc_id not in sources:
            sources.append(note.doc_id)

    lines = [f"Research brief: {research.question}", "", prose, "", "Sources"]
    lines.extend(f"- {doc_id}: {titles.get(doc_id, 'title unavailable')}" for doc_id in sources)

    return Brief(
        question=research.question,
        text="\n".join(lines),
        claims=claims,
        uncited=uncited,
        unknown=unknown,
    )
