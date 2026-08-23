"""
Writing the brief.

The workers came back with raw notes. One supervisor call turns them into prose,
and every factual sentence carries the tag of the note it came from.

`Doc`, `Note`, `Budget` and `Research` are the ones you wrote last time and are
given here. `Research` has grown one field: `corpus`, the documents the run
searched, because a sources block needs titles and a note only carries a doc id.

Run `python3 test.py` when you think you have it.

Gotcha: `from __future__ import annotations` makes annotations strings, so
`list[tuple[str, Note]]` is never evaluated and never checked. The tests are the
only thing that will tell you the shape is wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Doc:
    """One document in the corpus. Given to you."""

    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Note:
    """One quote a worker took from one document. Given to you."""

    sub_query: str
    doc_id: str
    quote: str
    worker: str


class BudgetExceeded(RuntimeError):
    """The run spent more than it was allowed to spend. Given to you."""

    def __init__(self, message: str, notes: list[Note] | None = None) -> None:
        super().__init__(message)
        self.notes: list[Note] = list(notes or [])


@dataclass
class Budget:
    """The meter from the last exercise. Given to you."""

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
    """What one research run gathered. Given to you."""

    question: str
    sub_queries: list[str]
    notes: list[Note]
    budget: Budget
    corpus: list[Doc] = field(default_factory=list)
    dropped: int = 0


@dataclass
class Claim:
    """
    One sentence of the brief and the tags it carries.

    Declare three fields, in this order:

        sentence: str
        tags: list[str]           tags naming a real note, in the order they appear
        unknown_tags: list[str]   tags naming no note at all
    """


@dataclass
class Brief:
    """
    The finished brief, and everything wrong with it.

    Declare five fields, in this order:

        question: str
        text: str              the assembled brief, including the sources block
        claims: list[Claim]
        uncited: list[str]     sentences carrying no tag at all
        unknown: list[str]     tags naming no note, deduplicated, in order
    """


def number_notes(notes: list[Note]) -> list[tuple[str, Note]]:
    """
    Give every note a stable tag: S1, S2, S3 and so on.

    Order the notes by `doc_id` first, then by the position they arrived in, and
    number them from 1 in that order. Return a list of `(tag, note)` pairs.

    Stability is the whole point. Two runs over the same notes have to produce
    the same tags, or a citation in a brief you saved yesterday points somewhere
    else today. Sorting by doc id also makes the sources block come out in order
    for free.

    Python's sort is stable, so sorting by doc id alone already keeps arrival
    order within a document. Being explicit about it costs nothing and says what
    you meant.
    """
    raise NotImplementedError


def synthesis_messages(question: str, tagged: list[tuple[str, Note]]) -> list[dict]:
    """
    Build the one prompt the supervisor sends.

    Return a list of message dicts. Between them they must contain:
      - the question
      - every note, rendered exactly as `[S1] <doc_id>: <quote>`, one per line
      - an instruction to mark every factual sentence with the tag it came from
      - an instruction to write nothing that no note supports, and to say so
        plainly, untagged, when the notes do not answer part of the question

    That last instruction is what makes an untagged sentence mean something. If
    the model is told to tag everything and it leaves a sentence bare, the bare
    sentence is a finding, not prose.

    Two words in those instructions are load bearing, because the tests read the
    prompt you built. Use the word "tag" rather than "label" or "marker", since
    "tag" is what the rest of this pipeline calls these things and consistency
    in a prompt is worth more than variety. And phrase the prohibition with
    "nothing" or "only": "write nothing that no note supports" or "write only
    what the notes support".
    """
    raise NotImplementedError


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences, keeping the terminator on each one.

    Use `re`. A boundary is `.`, `!` or `?` followed by whitespace, which means
    `15.5` never splits: there is no whitespace after that full stop.

    An abbreviation does have whitespace after it, so `e.g. vessel day rates`
    would split without a second pass. After splitting, merge a fragment back
    into the previous one when the previous one ends in a known abbreviation or
    in initials like `J. R.`. The abbreviations to know are `e.g.`, `i.e.`,
    `etc.`, `vs.`, `cf.`, `fig.`, `no.` and `al.`, which is the same set the
    next exercise carries forward.

    Empty or whitespace only text returns an empty list.

    You are not writing a sentence tokenizer for all of English. You are writing
    one that does not mangle a research brief, and the two cases above are the
    ones that actually show up.
    """
    raise NotImplementedError


def parse_claims(brief_text: str, known_tags: list[str]) -> list[Claim]:
    """
    Turn the model's prose into one Claim per sentence.

    For each sentence from `split_sentences`, find every `[S<number>]` marker.
    A marker whose tag is in `known_tags` goes into `tags`; anything else goes
    into `unknown_tags`, never into `tags`. Keep the order the markers appear in
    and record a repeated tag once.

    Return a Claim for EVERY sentence, including sentences with no markers. The
    caller needs those to report what went uncited, and a parser that silently
    drops them hides exactly the sentences worth looking at.

    Strip the brackets: the tag is `S3`, not `[S3]`.
    """
    raise NotImplementedError


def write_brief(client, research: Research) -> Brief:
    """
    Turn the notes into a brief with exactly one model call.

    Steps:
      1. `tagged = number_notes(research.notes)`
      2. one `client.chat.completions.create(...)` call with
         `synthesis_messages(...)`, and no tools: this call writes prose
      3. charge that call to `research.budget` under the stage `'synthesis'`
      4. `parse_claims` over the reply, with the tags from step 1 as known
      5. assemble `Brief.text` yourself, as:
             a first line reading `Research brief: <question>`
             a blank line
             the model's prose, unchanged
             a blank line
             a line reading `Sources`
             one line per cited document, `- <doc_id>: <title>`, each document
             once, in tag order, and only documents something actually cited
      6. return the Brief, with `uncited` holding every sentence that carried no
         marker at all and `unknown` holding every tag that named no note

    Three rules that look like details and are not.

    Step 3 is not optional bookkeeping. The workers are metered, so a run that
    skips the supervisor call reports a total smaller than the invoice, and the
    stage that goes missing is the one carrying every note at once. A meter with
    a hole in it is worse than no meter, because it looks like a number.

    The prose goes into `Brief.text` unchanged. The verification pass in the next
    lesson replaces failed sentences in this exact string, so reflowing it here
    breaks that.

    An uncited sentence stays in the text and is also reported. Deleting it would
    make a brief with a hole in it look like a clean one.

    Assemble the title and the sources block in Python, not in the prompt. The
    model cannot be trusted to list only the sources it actually used, and this
    part is a `join`.
    """
    raise NotImplementedError
