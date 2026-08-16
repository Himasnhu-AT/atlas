"""
Vector search: reference solution.

Read this after your own attempt. The comments are about the decisions, not the
syntax, because the decisions are the part that transfers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mockllm import cosine_similarity

DEFAULT_THRESHOLD = 0.25
DEFAULT_MIN_MARGIN = 0.05

CONFIDENT = "confident"
AMBIGUOUS = "ambiguous"
NO_MATCH = "no_match"


@dataclass(frozen=True)
class Document:
    id: str
    text: str


@dataclass(frozen=True)
class Hit:
    document: Document
    score: float


@dataclass
class Index:
    documents: list[Document] = field(default_factory=list)
    vectors: list[list[float]] = field(default_factory=list)


@dataclass(frozen=True)
class Verdict:
    label: str
    hits: list[Hit]
    margin: float | None


def build_index(client, documents: list[Document]) -> Index:
    documents = list(documents)
    # An empty batch is still a request: it costs a round trip and some
    # providers reject it outright.
    if not documents:
        return Index()

    response = client.embeddings.create(input=[document.text for document in documents])

    # Sort by the index the provider sent back rather than trusting the order
    # of `data`. This costs one sort per ingest and removes an entire class of
    # bug where document 3 is searched by document 7's vector.
    ordered = sorted(response.data, key=lambda item: item.index)
    return Index(documents=documents, vectors=[item.embedding for item in ordered])


def search(client, index: Index, query: str, k: int = 3) -> list[Hit]:
    if k <= 0 or not index.documents:
        return []

    # The query goes through the same client, so it lands in the same vector
    # space as the documents. This is one call per search and it is the reason
    # retrieval latency has a floor.
    query_vector = client.embeddings.create(input=query).data[0].embedding

    # Carrying the position into the sort key is what makes ties deterministic.
    # Sorting on the score alone leaves equal scores in whatever order the
    # underlying sort happened to produce, which is stable in CPython today and
    # is not something to build a test suite on.
    scored = [
        (cosine_similarity(query_vector, vector), position, document)
        for position, (vector, document) in enumerate(zip(index.vectors, index.documents))
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))

    return [Hit(document=document, score=score) for score, _, document in scored[:k]]


def search_above(
    client,
    index: Index,
    query: str,
    k: int = 3,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[Hit]:
    # Rank first, then filter. Filtering first would mean scoring everything
    # anyway, and taking the top k before the threshold keeps the two decisions
    # separate: k is how much context you can afford, the threshold is what you
    # are willing to call a match.
    return [hit for hit in search(client, index, query, k=k) if hit.score >= threshold]


def assess(
    client,
    index: Index,
    query: str,
    k: int = 3,
    threshold: float = DEFAULT_THRESHOLD,
    min_margin: float = DEFAULT_MIN_MARGIN,
) -> Verdict:
    hits = search_above(client, index, query, k=k, threshold=threshold)

    if not hits:
        return Verdict(label=NO_MATCH, hits=[], margin=None)

    if len(hits) < 2:
        # Nothing to compare against, so there is no gap to report. Returning
        # 0.0 here would be read as "the top two are identical" by any caller
        # that looks at the number instead of the label.
        return Verdict(label=CONFIDENT, hits=hits, margin=None)

    margin = hits[0].score - hits[1].score
    label = AMBIGUOUS if margin < min_margin else CONFIDENT
    return Verdict(label=label, hits=hits, margin=margin)
