"""
The verification pass: reference solution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Everything down to the marked line is the last two exercises, unchanged.

SYNTHESIS_SYSTEM = (
    "You are writing a short research brief from numbered notes.\n"
    "Mark every factual sentence with the tag of the note it came from, like "
    "[S1], immediately before the full stop.\n"
    "A sentence may carry more than one tag when it draws on more than one note.\n"
    "Write nothing that no note supports. If the notes do not answer part of the "
    "question, say so plainly and leave that sentence untagged."
)

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
    ordered = sorted(enumerate(notes), key=lambda pair: (pair[1].doc_id, pair[0]))
    return [(f"S{position}", note) for position, (_, note) in enumerate(ordered, start=1)]


def synthesis_messages(question: str, tagged: list[tuple[str, Note]]) -> list[dict]:
    rendered = "\n".join(f"[{tag}] {note.doc_id}: {note.quote}" for tag, note in tagged)
    return [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nNotes:\n{rendered}"},
    ]


def _ends_with_abbreviation(fragment: str) -> bool:
    tail = fragment.split()[-1] if fragment.split() else ""
    return tail.lower() in _ABBREVIATIONS or bool(_INITIALS.match(tail))


def split_sentences(text: str) -> list[str]:
    pieces = [piece for piece in _BOUNDARY.split(text.strip()) if piece]
    sentences: list[str] = []
    for piece in pieces:
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

    response = client.chat.completions.create(
        model="mock",
        messages=synthesis_messages(research.question, tagged),
    )
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


# New in this exercise.

VERDICTS = ("SUPPORTED", "UNSUPPORTED", "NOT_IN_SOURCE")

JUDGE_SYSTEM = (
    "You are checking one sentence against one passage of source text.\n"
    "Answer SUPPORTED only if the passage states the sentence. Answer "
    "UNSUPPORTED if the passage does not, and NOT_IN_SOURCE if the passage is "
    "about something else entirely. Give a one line reason."
)

JUDGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "judge",
            "description": "Record a verdict on one sentence against one passage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": list(VERDICTS)},
                    "reason": {"type": "string"},
                },
                "required": ["verdict", "reason"],
            },
        },
    }
]


@dataclass
class Verification:
    tag: str
    sentence: str
    doc_id: str
    verdict: str
    reason: str
    span: tuple[int, int] | None


@dataclass
class Report:
    verifications: list[Verification]
    supported: int
    unsupported: int
    not_in_source: int
    uncited: list[str]
    ok: bool


def normalise(text: str) -> str:
    return _normalised_with_offsets(text)[0]


def _normalised_with_offsets(text: str) -> tuple[str, list[int]]:
    """
    Normalise, and remember where every surviving character came from.

    The offsets are what make the span index back into the original text.
    Normalising and then searching without them gives you a position in a
    string nobody will ever read.
    """
    characters: list[str] = []
    offsets: list[int] = []
    after_space = True

    for index, character in enumerate(text):
        if character.isspace():
            if not after_space:
                characters.append(" ")
                offsets.append(index)
                after_space = True
            continue
        if not character.isalnum():
            continue
        characters.append(character.lower())
        offsets.append(index)
        after_space = False

    while characters and characters[-1] == " ":
        characters.pop()
        offsets.pop()

    return "".join(characters), offsets


def locate(quote: str, doc: Doc) -> tuple[int, int] | None:
    haystack, offsets = _normalised_with_offsets(doc.text)
    needle = normalise(quote)
    if not needle:
        return None

    found = haystack.find(needle)
    if found == -1:
        return None

    start = offsets[found]
    end = offsets[found + len(needle) - 1] + 1
    return (start, end)


def verify_claim(
    client, claim: Claim, tag: str, note: Note, doc: Doc, budget: Budget
) -> Verification:
    span = locate(note.quote, doc)

    # The free check runs first. There is nothing for a model to judge when the
    # quote is not in the document at all, and asking anyway pays for an opinion
    # about a passage that does not exist.
    if span is None:
        return Verification(
            tag=tag,
            sentence=claim.sentence,
            doc_id=doc.id,
            verdict="NOT_IN_SOURCE",
            reason=f"the quote for {tag} does not appear in {doc.id}",
            span=None,
        )

    start, end = span
    response = client.chat.completions.create(
        model="mock",
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Sentence: {claim.sentence}\n\n"
                    f"Source {doc.id}, characters {start} to {end}:\n{doc.text[start:end]}"
                ),
            },
        ],
        tools=JUDGE_TOOLS,
    )
    # One judged claim, one charge. This is the stage that scales with the size
    # of the brief rather than with the size of the plan, so it is the one worth
    # watching when a run gets expensive.
    budget.charge("verify", response.usage)

    payload = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
    verdict = str(payload.get("verdict", ""))
    reason = str(payload.get("reason", ""))

    # A verdict off the list is a failed judgement, not a pass. Keep the reason:
    # it is the only evidence of what the model actually said.
    if verdict not in VERDICTS:
        verdict = "UNSUPPORTED"

    return Verification(
        tag=tag,
        sentence=claim.sentence,
        doc_id=doc.id,
        verdict=verdict,
        reason=reason,
        span=span,
    )


def verify_brief(
    client,
    brief: Brief,
    tagged: list[tuple[str, Note]],
    corpus: list[Doc],
    budget: Budget,
    require_all_cited: bool = True,
) -> Report:
    notes = dict(tagged)
    documents = {doc.id: doc for doc in corpus}
    verifications: list[Verification] = []

    for claim in brief.claims:
        for tag in claim.tags:
            note = notes.get(tag)
            document = documents.get(note.doc_id) if note is not None else None
            if note is None or document is None:
                verifications.append(
                    Verification(
                        tag=tag,
                        sentence=claim.sentence,
                        doc_id=note.doc_id if note is not None else "",
                        verdict="NOT_IN_SOURCE",
                        reason=f"no document on file for {tag}",
                        span=None,
                    )
                )
                continue
            verifications.append(verify_claim(client, claim, tag, note, document, budget))

        # A tag naming no note is a citation to a source that does not exist,
        # which is the same failure as a quote that is not in the document.
        for tag in claim.unknown_tags:
            verifications.append(
                Verification(
                    tag=tag,
                    sentence=claim.sentence,
                    doc_id="",
                    verdict="NOT_IN_SOURCE",
                    reason=f"{tag} names no note in this run",
                    span=None,
                )
            )

    counts = {verdict: 0 for verdict in VERDICTS}
    for verification in verifications:
        counts[verification.verdict] += 1

    uncited = list(brief.uncited)
    ok = all(verification.verdict == "SUPPORTED" for verification in verifications) and not (
        uncited and require_all_cited
    )

    return Report(
        verifications=verifications,
        supported=counts["SUPPORTED"],
        unsupported=counts["UNSUPPORTED"],
        not_in_source=counts["NOT_IN_SOURCE"],
        uncited=uncited,
        ok=ok,
    )


def redact_unverified(brief: Brief, report: Report) -> str:
    # First failing verdict per sentence. A sentence citing two notes where one
    # fails is still a sentence that cannot be shown.
    failed: dict[str, str] = {}
    for verification in report.verifications:
        if verification.verdict != "SUPPORTED":
            failed.setdefault(verification.sentence, verification.verdict)

    text = brief.text
    for sentence, verdict in failed.items():
        text = text.replace(sentence, f"[removed: {verdict}]")
    return text
