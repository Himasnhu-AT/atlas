"""
Grounded answers and the scope boundary.

The first slice of the support agent. Retrieve first, answer second, and treat a
reply that cites nothing as a failure rather than as an answer.

Nothing here reads from disk. The test file owns the knowledge base and hands it
to you as a list of Article, which is how the real thing should work too: the
retrieval layer takes documents, it does not go looking for them.

Run `python3 test.py` when you think you have it.
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
    """
    What the agent produced for one question.

    Attributes:
        text: what the customer would see.
        cited: article ids the reply cited, that were actually retrieved.
        dropped: bracket ids the reply cited that were NOT retrieved. A model
            inventing an id is the most useful hallucination signal you get,
            because it is exact rather than a judgement call.
        route: one of "answered", "out_of_scope", "unsupported". Nothing else.
    """

    text: str
    cited: list[str]
    dropped: list[str]
    route: str


# Given to you. Retrieval quality here is mostly preprocessing, and mockllm's
# embed_text() is the hashing trick: it buckets words, so "the" and "is" carry as
# much weight as "refund" unless you take them out first. Strip them and the
# scores separate cleanly. A real embedding model does this for you, along with
# handling synonyms, which this one cannot.
STOPWORDS = frozenset(
    """a am an and any are as at be been before but by can cannot did do does for from
    get got had has have how i if in is it its me my no not of on or please so still
    that the their them then there these they this to was we were what when where which
    who will with would you your just only all it's i'm""".split()
)

_WORD = re.compile(r"[a-z0-9']+")

#: Matches a citation marker and captures the id inside it: "[A1]" -> "A1".
CITATION = re.compile(r"\[(A\d+)\]")

#: Where an unanswerable question goes. Named in the out of scope reply so the
#: customer is told what happens next rather than just being refused.
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
    """Lowercase, keep words and digits, drop stopwords. Given to you."""
    return " ".join(w for w in _WORD.findall(content.lower()) if w not in STOPWORDS)


def retrieve(
    articles: list[Article],
    question: str,
    k: int = 2,
    floor: float = 0.12,
) -> list[tuple[Article, float]]:
    """
    Find the articles most likely to answer the question.

    Embed normalise(article.title + " " + article.body) for each article and
    normalise(question) for the question, score them with cosine_similarity,
    then return at most k (article, score) pairs.

    Ordering is score descending. Ties break on article.id ascending, so the
    same corpus and the same question always produce the same list. Retrieval
    that reorders itself between runs turns every downstream test flaky, and you
    will spend an afternoon blaming the model for it.

    Anything scoring strictly below floor is dropped, including when that leaves
    nothing. An empty list is a real answer to "what do we know about this",
    and the caller depends on getting it.

    Args:
        articles: the corpus. Never mutate it.
        question: the customer's message.
        k: how many hits to keep after filtering.
        floor: minimum score to keep a hit.

    Returns:
        Up to k (article, score) pairs, best first.
    """
    raise NotImplementedError


def build_messages(question: str, hits: list[tuple[Article, float]], system: str) -> list[dict]:
    """
    Assemble the three messages sent to the model.

    Returns exactly:
        [
          {"role": "system", "content": system},
          {"role": "user", "content": <the context block>},
          {"role": "user", "content": question},
        ]

    The context block starts with the line "Context:" and then renders each hit,
    separated by a blank line, as:

        [<article.id>] <article.title>
        <article.body>

    Render the hits in the order they arrive. With no hits at all the block is
    "Context:\\n\\n(nothing retrieved)", though answer() never gets that far.

    The question goes last and on its own. Burying it above a wall of context is
    the single most reliable way to make a model answer a different question
    from the one that was asked.
    """
    raise NotImplementedError


def parse_citations(text: str, allowed: list[str]) -> tuple[list[str], list[str]]:
    """
    Split the bracket ids in a reply into the real ones and the invented ones.

    Use the CITATION pattern above. Keep first appearance order and remove
    duplicates, so "[A1] ... [A2] ... [A1]" yields ["A1", "A2"].

    Args:
        text: the model's reply.
        allowed: the ids that were actually retrieved for this question.

    Returns:
        (cited, dropped). cited holds the ids that appear in allowed, dropped
        holds the ids that do not. Both keep first appearance order and neither
        contains duplicates.
    """
    raise NotImplementedError


def answer(
    client,
    articles: list[Article],
    question: str,
    k: int = 2,
    floor: float = 0.12,
) -> Reply:
    """
    Answer one question against the knowledge base, or decline to.

    Flow:
      1. hits = retrieve(articles, question, k, floor)
      2. if there are no hits, return
         Reply(OUT_OF_SCOPE_TEXT, [], [], "out_of_scope") WITHOUT calling the
         model. You already know the answer cannot be grounded, so the call
         cannot do anything except cost money and produce something plausible
         that nothing supports.
      3. otherwise call the model once:
         client.chat.completions.create(
             model="mock",
             messages=build_messages(question, hits, SYSTEM),
         )
      4. take choice.message.content, using "" when it is None
      5. cited, dropped = parse_citations(text, [a.id for a, _ in hits])
      6. route is "answered" when cited is non-empty, otherwise "unsupported"

    An unsupported reply still carries the model's text. Throwing it away leaves
    a human staring at an empty ticket with no idea what the agent nearly said.
    Deciding whether to show that text to the customer is the caller's problem,
    and the next exercise makes that decision.

    Returns:
        A Reply. It is never None, on any path.
    """
    raise NotImplementedError
