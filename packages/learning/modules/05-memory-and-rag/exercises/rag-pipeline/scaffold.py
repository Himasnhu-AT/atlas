"""
The RAG pipeline.

Ingest documents, retrieve against a question, assemble the retrieved chunks into
a prompt, and generate an answer that is allowed to be "I don't know". The
chunking and the vector store are already here, done the way you did them in the
last two exercises. What is left is the part every tutorial hurries past: how the
context is laid out, what the instruction around it says, and what happens when
retrieval comes back with nothing.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mockllm import cosine_similarity

#: Returned verbatim when nothing retrieved clears the bar, and repeated in the
#: system prompt so the model has the same sentence available.
NO_ANSWER = "I don't know based on the provided context."

#: The retrieval floor. Corpus specific, like every threshold in this module.
DEFAULT_MIN_SCORE = 0.15

SYSTEM_PROMPT = (
    "You answer questions using only the context provided in this conversation.\n"
    "Every factual sentence must end with the bracketed number of the source it "
    "came from, like [1].\n"
    f'If the context does not answer the question, reply exactly: "{NO_ANSWER}"\n'
    "Do not use anything you know outside the context."
)


@dataclass(frozen=True)
class Document:
    """A source document before it has been split."""

    id: str
    title: str
    text: str


@dataclass
class Chunk:
    """A retrievable piece of a document. Same shape as the chunking exercise."""

    text: str
    index: int
    metadata: dict = field(default_factory=dict)

    def with_context(self) -> str:
        """Given. The text to embed, prefixed with its headings."""
        title = self.metadata.get("title") or ""
        section = self.metadata.get("section") or ""
        parts = [part for part in (title, section) if part]
        if not parts:
            return self.text
        return f"{' > '.join(parts)}\n\n{self.text}"

    def citation(self) -> str:
        """Given. "<source>#<index>", or "chunk <index>" without a source."""
        source = self.metadata.get("source") or ""
        if not source:
            return f"chunk {self.index}"
        return f"{source}#{self.index}"


@dataclass(frozen=True)
class Hit:
    """A chunk and how well it matched."""

    chunk: Chunk
    score: float


def split_paragraphs(text: str, max_size: int) -> list[str]:
    """
    Given. The chunking exercise, cut down to what this pipeline needs.

    Splits on blank lines, greedily rejoins consecutive paragraphs while they
    fit, and slices anything still oversized on the character count.
    """
    chunks: list[str] = []
    buffer = ""
    for piece in text.split("\n\n"):
        piece = piece.strip()
        if not piece:
            continue
        while len(piece) > max_size:
            chunks.append(piece[:max_size].strip())
            piece = piece[max_size:].strip()
        if not piece:
            continue
        candidate = f"{buffer}\n\n{piece}" if buffer else piece
        if len(candidate) <= max_size:
            buffer = candidate
        else:
            chunks.append(buffer)
            buffer = piece
    if buffer:
        chunks.append(buffer)
    return chunks


class VectorStore:
    """
    Given. Chunks and their embeddings, searchable by cosine similarity.

    Brute force over every stored vector, which is correct and fast enough for
    anything up to tens of thousands of chunks. An approximate index is what you
    reach for when you have measured that this is too slow, not before.
    """

    def __init__(self, client) -> None:
        self._client = client
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def add(self, chunks: list[Chunk]) -> None:
        """Embed a batch of chunks and keep them. Cumulative across calls."""
        chunks = list(chunks)
        if not chunks:
            return
        response = self._client.embeddings.create(
            input=[chunk.with_context() for chunk in chunks]
        )
        for item in sorted(response.data, key=lambda entry: entry.index):
            self._vectors.append(item.embedding)
        self._chunks.extend(chunks)

    def search(self, query: str, k: int = 3) -> list[Hit]:
        """The k best matching chunks, best first, ties toward the earlier chunk."""
        if k <= 0 or not self._chunks:
            return []
        query_vector = self._client.embeddings.create(input=query).data[0].embedding
        scored = [
            (cosine_similarity(query_vector, vector), position, chunk)
            for position, (vector, chunk) in enumerate(zip(self._vectors, self._chunks))
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [Hit(chunk=chunk, score=score) for score, _, chunk in scored[:k]]


@dataclass(frozen=True)
class Answer:
    """
    What the pipeline gives back.

    Attributes:
        text: the model's reply, or NO_ANSWER when no model was called.
        sources: the citation string for each chunk that was sent, in the order
            they were numbered in the prompt. sources[0] is what "[1]" refers
            to. Your code built this list from the hits, so it is true whatever
            the model wrote.
        grounded: whether any context was sent at all. False means retrieval
            found nothing and the model was never asked.
    """

    text: str
    sources: list[str]
    grounded: bool


def ingest(store: VectorStore, documents: list[Document], max_size: int = 240) -> list[Chunk]:
    """
    Split every document, tag the pieces, and put them in the store.

    For each document, split its text with split_paragraphs and wrap each piece
    in a Chunk whose `index` is its position within that document, counting from
    0, and whose metadata is {"source": document.id, "title": document.title,
    "section": ""}.

    Add every chunk from every document to the store in one `store.add` call.
    Ingest is where batching matters most: it is the one step that touches the
    whole corpus, and one embedding request per chunk is how a ten second ingest
    becomes an hour.

    Returns:
        Every chunk created, in document order then chunk order. An empty
        document list adds nothing and returns [].
    """
    raise NotImplementedError


def format_context(hits: list[Hit]) -> str:
    """
    Lay the retrieved chunks out as the block that goes in the prompt.

    Exact format, because the tests check it. Sources are numbered from 1 in the
    order given, each block is the number and the chunk's citation on one line
    followed by the chunk text, and blocks are separated by a blank line:

        [1] pricing.md#1
        The Pro plan costs $49 per month when billed annually.

        [2] pricing.md#0
        The Pro plan includes unlimited projects and priority support.

    With no hits, return "(no context retrieved)".

    Two things are doing work here. The number is what the model cites, and the
    citation string next to it is what turns that number back into a document
    when someone asks where an answer came from. The blank line is what stops
    two chunks reading as one continuous passage, which is how a retrieved
    sentence ends up attributed to the wrong source.

    Note what is not here: the chunk text goes in unmodified. Escaping or
    reformatting it to look tidier changes the text the model is answering from,
    and then the quote in the answer does not match the document.
    """
    raise NotImplementedError


def build_messages(question: str, hits: list[Hit]) -> list[dict]:
    """
    Build the three messages that get sent.

    Exactly, in this order:

        {"role": "system", "content": SYSTEM_PROMPT}
        {"role": "user", "content": "Context:\\n\\n" + format_context(hits)}
        {"role": "user", "content": question}

    The context and the question are separate messages rather than one, and the
    question is last. A question buried above a wall of retrieved text is the
    most reliable way to get a fluent answer to something nobody asked.
    """
    raise NotImplementedError


def answer(
    client,
    store: VectorStore,
    question: str,
    k: int = 3,
    min_score: float = DEFAULT_MIN_SCORE,
) -> Answer:
    """
    Retrieve, decide whether to answer, and answer.

    Flow:
      1. search the store for k hits
      2. drop every hit scoring below min_score
      3. if nothing survives, return Answer(NO_ANSWER, [], grounded=False)
         WITHOUT calling the model
      4. otherwise send build_messages(question, hits) as a single chat call and
         return Answer(reply_text, [hit.chunk.citation() for hit in hits], True)

    Step 3 is the exercise. The instruction in SYSTEM_PROMPT tells the model to
    decline when the context does not answer the question, and models mostly
    comply, but "mostly" is not a guarantee and the call still costs money. A
    threshold is the part of that promise you can actually enforce, and it is
    what the instruction leans on.

    Use the reply's content as it comes back, or "" if it is None. Do not fall
    back to NO_ANSWER for an empty reply: a grounded call that produced nothing
    is a different problem from a question you refused to answer, and telling
    them apart in a log is worth more than the tidier return value.

    Raises:
        ValueError: if k < 1.
    """
    raise NotImplementedError
