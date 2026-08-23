"""
The RAG pipeline: reference solution.

Read this after your own attempt. The comments are about the decisions, not the
syntax, because the decisions are the part that transfers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mockllm import cosine_similarity

NO_ANSWER = "I don't know based on the provided context."

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
    id: str
    title: str
    text: str


@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict = field(default_factory=dict)

    def with_context(self) -> str:
        title = self.metadata.get("title") or ""
        section = self.metadata.get("section") or ""
        parts = [part for part in (title, section) if part]
        if not parts:
            return self.text
        return f"{' > '.join(parts)}\n\n{self.text}"

    def citation(self) -> str:
        source = self.metadata.get("source") or ""
        if not source:
            return f"chunk {self.index}"
        return f"{source}#{self.index}"


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def split_paragraphs(text: str, max_size: int) -> list[str]:
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
    def __init__(self, client) -> None:
        self._client = client
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def add(self, chunks: list[Chunk]) -> None:
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
    text: str
    sources: list[str]
    grounded: bool


def ingest(
    store: VectorStore, documents: list[Document], max_size: int = 240
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        for index, piece in enumerate(split_paragraphs(document.text, max_size)):
            chunks.append(
                Chunk(
                    text=piece,
                    index=index,
                    # `section` is written empty rather than left out, so
                    # with_context() and citation() never have to guard a
                    # missing key.
                    metadata={
                        "source": document.id,
                        "title": document.title,
                        "section": "",
                    },
                )
            )

    # One add for the whole corpus, which is one embedding request. Calling
    # store.add() inside the loop would be one request per document and would
    # look identical in every test that does not count requests.
    store.add(chunks)
    return chunks


def format_context(hits: list[Hit]) -> str:
    if not hits:
        return "(no context retrieved)"

    blocks = [
        f"[{number}] {hit.chunk.citation()}\n{hit.chunk.text}"
        for number, hit in enumerate(hits, start=1)
    ]
    # A blank line between blocks. Without it two chunks read as one passage and
    # the model attributes the second one's facts to the first one's number.
    return "\n\n".join(blocks)


def build_messages(question: str, hits: list[Hit]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Context:\n\n" + format_context(hits)},
        {"role": "user", "content": question},
    ]


def answer(
    client,
    store: VectorStore,
    question: str,
    k: int = 3,
    min_score: float = DEFAULT_MIN_SCORE,
) -> Answer:
    if k < 1:
        raise ValueError("k must be at least 1")

    hits = [hit for hit in store.search(question, k=k) if hit.score >= min_score]

    # Nothing cleared the floor. Calling the model here buys a fluent paragraph
    # assembled from whatever the least bad chunks happened to say, and pays for
    # it. The instruction in SYSTEM_PROMPT asks the model to decline in this
    # situation; this is the version of that promise you can enforce.
    if not hits:
        return Answer(text=NO_ANSWER, sources=[], grounded=False)

    response = client.chat.completions.create(
        model="mock",
        messages=build_messages(question, hits),
    )

    # The sources come from the hits, not from the reply. A number the model
    # wrote is a claim; this list is a record of what was actually sent.
    return Answer(
        text=response.choices[0].message.content or "",
        sources=[hit.chunk.citation() for hit in hits],
        grounded=True,
    )
