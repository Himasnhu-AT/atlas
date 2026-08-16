"""
The verification pass.

Re-read the source before believing the citation. The cheap deterministic checks
run first, the model only judges passages that actually exist, and a brief that
fails ships redacted rather than confident.

Everything down to the line marked "New in this exercise" is the last two
exercises, given to you unchanged. You are writing the pass that reads the
sources back.

Run `python3 test.py` when you think you have it.

Gotcha: `from __future__ import annotations` makes annotations strings, so
`tuple[int, int] | None` is fine on any Python 3.10 and is never checked at
runtime. Returning a list where a tuple belongs will pass silently here and
break the first thing that unpacks it.
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

#: The only three answers a verification may carry. Fill this in:
#: 'SUPPORTED', 'UNSUPPORTED', 'NOT_IN_SOURCE', in that order.
VERDICTS: tuple[str, ...] = ()

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
    """
    One verdict on one citation.

    Declare six fields, in this order:

        tag: str
        sentence: str
        doc_id: str
        verdict: str                 one of VERDICTS
        reason: str
        span: tuple[int, int] | None  where the quote sits in the source, if it does
    """


@dataclass
class Report:
    """
    What the verification pass found across a whole brief.

    Declare six fields, in this order:

        verifications: list[Verification]
        supported: int
        unsupported: int
        not_in_source: int
        uncited: list[str]
        ok: bool
    """


def normalise(text: str) -> str:
    """
    Reduce text to the form two spellings of the same sentence share.

    Lowercase it, drop every character that is not alphanumeric and not
    whitespace, and collapse each run of whitespace to a single space, with no
    leading or trailing space.

    `normalise("Prices Fell, sharply!")` is `"prices fell sharply"`.

    This is the whole reason a citation check can work at all. A quote copied out
    of a wrapped paragraph carries different whitespace and often a lost comma,
    and comparing raw strings would reject it.
    """
    raise NotImplementedError


def locate(quote: str, doc: Doc) -> tuple[int, int] | None:
    """
    Find where a quote sits in a document, or report that it does not.

    Return `(start, end)` as character offsets into the ORIGINAL `doc.text`, such
    that `doc.text[start:end]` is the quoted passage with its original
    punctuation and line breaks. Return None when the quote is not there, and
    when the quote normalises to nothing.

    Search the normalised text, because that is the only version where the quote
    and the source agree. Then map the match back: the start of the span is the
    original index of the character the match began at, and the end is the
    original index of its last character, plus one.

    Getting that mapping needs a normalised string and a parallel list holding,
    for each surviving character, the index it came from in the original. Write
    that pass once and have `normalise` return the string half of it, rather
    than writing the rule out twice. Two normalisations that drift apart is the
    failure this exercise is least able to survive: `normalise` reports that a
    quote is present, `locate` cannot find it, and an honest citation is
    redacted out of the brief as though it were a fabrication. The words that
    catch it are the ordinary ones, `don't` and `co-operate`, where a pass that
    treats dropped punctuation as a separator disagrees with one that drops it.

    Returning offsets into the normalised string instead is the other tempting
    bug. They are positions in a string nobody will ever read, and a redaction
    built on them cuts the document in the wrong place.
    """
    raise NotImplementedError


def verify_claim(
    client, claim: Claim, tag: str, note: Note, doc: Doc, budget: Budget
) -> Verification:
    """
    Check one sentence against the source its citation names.

    Order matters, and it is the point of the exercise:

      1. `locate` the note's quote in the document. If it is not there, return a
         `NOT_IN_SOURCE` verification, with `span=None`, WITHOUT calling the
         model. A quote that is not in the document is settled by string search,
         and paying a model to have an opinion about a passage that does not
         exist is the most expensive way to learn nothing.
      2. Otherwise, make ONE model call with `tools=JUDGE_TOOLS`, showing it the
         claim's sentence and the located passage, `doc.text[start:end]`. Send
         the passage, not the whole document: the judgement is about that span.
      3. Charge that call to `budget` under the stage `'verify'`.
      4. Read `tool_call('judge', {'verdict': ..., 'reason': ...})` out of the
         reply. If the verdict is not one of `VERDICTS`, record `UNSUPPORTED`
         and keep the model's reason exactly as given.

    Step 3 only happens on the path that made a call. The free check in step 1
    costs nothing and charges nothing, which is exactly what makes `by_stage`
    worth reading: `verify` grows with the number of claims a model had to judge,
    not with the number of claims the brief contained.

    Step 4 has one wrong answer that looks reasonable: treating an unrecognised
    verdict as SUPPORTED because the model did not say no. A judgement you could
    not parse is a judgement that did not happen.
    """
    raise NotImplementedError


def verify_brief(
    client,
    brief: Brief,
    tagged: list[tuple[str, Note]],
    corpus: list[Doc],
    budget: Budget,
    require_all_cited: bool = True,
) -> Report:
    """
    Verify every citation in a brief and decide whether it may ship.

    For each claim, in order: verify every tag in `claim.tags` against the note
    it names and the document that note came from, passing `budget` through so
    the judged calls land on the meter. A tag whose note or document is missing,
    and every tag in `claim.unknown_tags`, is `NOT_IN_SOURCE` with `span=None`
    and no model call, because a citation to a source that does not exist fails
    for the same reason a missing quote does.

    Count the verdicts, carry `brief.uncited` through, and set `ok` to True only
    when every verdict is `SUPPORTED` and, when `require_all_cited` is set, there
    are no uncited sentences.

    `ok` is deliberately blunt. A brief that is ninety percent verified is a
    brief with an unverified claim in it, and the caller can read the counts if
    it wants to be more forgiving than that.
    """
    raise NotImplementedError


def redact_unverified(brief: Brief, report: Report) -> str:
    """
    Return the brief's text with every failed sentence replaced.

    A sentence carrying any verdict other than `SUPPORTED` is replaced, in
    place, by `[removed: <verdict>]`, using the first failing verdict recorded
    for it. Every other character of `brief.text` is left exactly as it was:
    same title line, same sources block, same line count.

    This is what shipping a partially verified brief looks like. The reader sees
    where something was cut, which is honest, rather than a confident paragraph
    with a fabrication in the middle of it.
    """
    raise NotImplementedError
