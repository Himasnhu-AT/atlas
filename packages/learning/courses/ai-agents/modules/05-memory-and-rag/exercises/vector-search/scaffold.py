"""
Vector search.

An index, a ranked search over it, a threshold that lets the search return
nothing, and a verdict that says out loud when the top two results are too close
to call. The last one is the part most retrieval code skips, and it is the part
that stops a weak match from being handed to a model as though it were an answer.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mockllm import cosine_similarity

#: Below this, a result is not worth putting in a prompt. There is no universal
#: value: it depends on your embedding model, your corpus and how much a wrong
#: answer costs you. This one is a starting point for the embeddings in this
#: course, and the only honest way to set it is to look at what it drops.
DEFAULT_THRESHOLD = 0.25

#: How far ahead the top hit has to be before you treat it as the answer rather
#: than as one of several candidates.
DEFAULT_MIN_MARGIN = 0.05

CONFIDENT = "confident"
AMBIGUOUS = "ambiguous"
NO_MATCH = "no_match"


@dataclass(frozen=True)
class Document:
    """Something retrievable, with an id you can cite."""

    id: str
    text: str


@dataclass(frozen=True)
class Hit:
    """A document and how well it matched, from -1 to 1."""

    document: Document
    score: float


@dataclass
class Index:
    """
    Documents and their vectors, positionally aligned.

    `documents[i]` is described by `vectors[i]`. Keeping them as two lists
    rather than one list of pairs is what a real vector store does under the
    covers, because the vectors are the only part it has to scan.
    """

    documents: list[Document] = field(default_factory=list)
    vectors: list[list[float]] = field(default_factory=list)


@dataclass(frozen=True)
class Verdict:
    """
    What retrieval is willing to say about a query.

    Attributes:
        label: CONFIDENT, AMBIGUOUS or NO_MATCH.
        hits: the surviving hits, best first. Empty for NO_MATCH.
        margin: the gap between the top two hits, or None when there are fewer
            than two. None means the question does not apply, which is not the
            same as a gap of zero, and collapsing the two is how you end up
            reporting every single-result query as ambiguous.
    """

    label: str
    hits: list[Hit]
    margin: float | None


def build_index(client, documents: list[Document]) -> Index:
    """
    Embed every document once and return an index over them.

    Send all the texts in a single `client.embeddings.create(input=[...])` call.
    Embedding APIs are billed and rate limited per request as well as per token,
    and a loop that makes one call per document turns a one second ingest into a
    ten minute one for no benefit.

    Read each vector back through the `index` field on the response rather than
    trusting the order of `data`. The order usually matches; relying on it is a
    bug that only appears under load, and pairing the wrong vector with the wrong
    document produces a search that is subtly, silently wrong.

    An empty document list returns an empty Index without calling the API at all.
    """
    raise NotImplementedError


def search(client, index: Index, query: str, k: int = 3) -> list[Hit]:
    """
    Rank every document in the index against the query.

    Embed the query with the same client, score it against every stored vector
    with cosine_similarity, and return the best k as Hits, highest score first.

    The query has to go through the same embedding model as the documents. Two
    models produce vectors in different spaces, and comparing across them gives
    you numbers that look like similarities and mean nothing.

    Ties break toward the document added first, so the same query over the same
    index always returns the same order. A retriever that reorders itself
    between runs makes every test above it flaky and every bug report useless.

    Returns:
        Up to k hits. All of them when k exceeds the size of the index, and []
        when the index is empty or k is 0 or less. No threshold is applied here:
        this function ranks, it does not judge.
    """
    raise NotImplementedError


def search_above(
    client,
    index: Index,
    query: str,
    k: int = 3,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[Hit]:
    """
    Rank as `search` does, then drop anything scoring below `threshold`.

    Returning nothing is a valid, useful answer. Without a floor, a query about
    something the corpus has never heard of still comes back with three
    documents, because there is always a least bad one, and the model downstream
    has no way to tell that result from a real match.

    Comparison is `>= threshold`, so a hit exactly on the line survives.
    """
    raise NotImplementedError


def assess(
    client,
    index: Index,
    query: str,
    k: int = 3,
    threshold: float = DEFAULT_THRESHOLD,
    min_margin: float = DEFAULT_MIN_MARGIN,
) -> Verdict:
    """
    Retrieve, then say how much you trust what came back.

    Uses search_above, then labels the result:

      NO_MATCH   nothing survived the threshold. hits is [], margin is None.
      AMBIGUOUS  two or more hits survived and the gap between the top two is
                 strictly less than min_margin. The retriever found candidates
                 and cannot choose between them.
      CONFIDENT  anything else, including exactly one surviving hit.

    `margin` is hits[0].score - hits[1].score when there are at least two hits,
    and None otherwise.

    AMBIGUOUS is not a failure. Near duplicate documents are normal in any real
    corpus, and a pair of near duplicates that both answer the question is a
    perfectly good outcome. What matters is that the caller is told, so it can
    show both, ask which one, or send the query to a person. The failure is
    picking one at random and presenting it as the answer.
    """
    raise NotImplementedError
