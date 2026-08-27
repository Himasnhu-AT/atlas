"""
Grounded answers and the scope boundary: reference solution.
"""

from __future__ import annotations

import re

from dataclasses import dataclass

from mockllm import cosine_similarity, embed_text


@dataclass
class Article:
    """One knowledge base document. The id is what an answer cites."""

    id: str
    title: str
    body: str


@dataclass
class Reply:
    """What the agent produced for one question."""

    text: str
    cited: list[str]
    dropped: list[str]
    route: str


STOPWORDS = frozenset(
    """a am an and any are as at be been before but by can cannot did do does for from
    get got had has have how i if in is it its me my no not of on or please so still
    that the their them then there these they this to was we were what when where which
    who will with would you your just only all it's i'm""".split()
)

_WORD = re.compile(r"[a-z0-9']+")

CITATION = re.compile(r"\[(A\d+)\]")

HUMAN_QUEUE = "the human support queue"

OUT_OF_SCOPE_TEXT = (
    "Nothing in the knowledge base covers that, so I am not going to guess. "
    f"Passing this to {HUMAN_QUEUE}."
)

SYSTEM = (
    "You answer questions about this product using only the context below. "
    "Every factual sentence must carry the bracket id of the article it came "
    "from, like [A1]. If the context does not answer the question, say so "
    "plainly and do not guess."
)


def normalise(content: str) -> str:
    """Lowercase, keep words and digits, drop stopwords."""
    return " ".join(w for w in _WORD.findall(content.lower()) if w not in STOPWORDS)


def retrieve(
    articles: list[Article],
    question: str,
    k: int = 2,
    floor: float = 0.12,
) -> list[tuple[Article, float]]:
    """Find the articles most likely to answer the question."""
    query = embed_text(normalise(question))

    scored: list[tuple[Article, float]] = []
    for article in articles:
        vector = embed_text(normalise(f"{article.title} {article.body}"))
        score = cosine_similarity(query, vector)
        if score >= floor:
            scored.append((article, score))

    # Negate the score rather than reversing, so the id tie break still sorts
    # ascending. sorted(reverse=True) would reverse both keys and put the higher
    # id first on a tie, which is stable but is not the rule we published.
    scored.sort(key=lambda pair: (-pair[1], pair[0].id))
    return scored[:k]


def build_messages(question: str, hits: list[tuple[Article, float]], system: str) -> list[dict]:
    """Assemble the three messages sent to the model."""
    blocks = [f"[{article.id}] {article.title}\n{article.body}" for article, _ in hits]
    context = "Context:\n\n" + ("\n\n".join(blocks) if blocks else "(nothing retrieved)")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": context},
        # The question last and alone. A model that reads the context after the
        # question tends to answer the context.
        {"role": "user", "content": question},
    ]


def parse_citations(text: str, allowed: list[str]) -> tuple[list[str], list[str]]:
    """Split the bracket ids in a reply into the real ones and the invented ones."""
    permitted = set(allowed)
    cited: list[str] = []
    dropped: list[str] = []

    for marker in CITATION.findall(text or ""):
        bucket = cited if marker in permitted else dropped
        if marker not in bucket:
            bucket.append(marker)

    return cited, dropped


def answer(
    client,
    articles: list[Article],
    question: str,
    k: int = 2,
    floor: float = 0.12,
) -> Reply:
    """Answer one question against the knowledge base, or decline to."""
    hits = retrieve(articles, question, k=k, floor=floor)

    # No context means no grounded answer is possible, so the model call is
    # spend with a known worthless result. Refuse before paying for it.
    if not hits:
        return Reply(text=OUT_OF_SCOPE_TEXT, cited=[], dropped=[], route="out_of_scope")

    response = client.chat.completions.create(
        model="mock",
        messages=build_messages(question, hits, SYSTEM),
    )
    text = response.choices[0].message.content or ""

    cited, dropped = parse_citations(text, [article.id for article, _ in hits])

    # A reply that grounds nothing is not an answer, whatever it says. The text
    # travels with the Reply anyway so a human can see what was nearly sent.
    route = "answered" if cited else "unsupported"
    return Reply(text=text, cited=cited, dropped=dropped, route=route)
