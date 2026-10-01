"""
Chunking: reference solution.

Read this after your own attempt. The comments are about the decisions, not the
syntax, because the decisions are the part that transfers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SEPARATORS = ["\n\n", "\n", ". ", " "]


@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict = field(default_factory=dict)

    def with_context(self) -> str:
        # `or ""` rather than a default on get(), so a key present with the
        # value None behaves like a key that is absent. Metadata arrives from
        # document parsers and half of them write None for a missing heading.
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


def split_fixed(text: str, size: int, overlap: int = 0) -> list[str]:
    # Validate before doing any work. overlap >= size is the interesting one:
    # the step would be zero or negative and the loop would never advance, so
    # this is a hang caught at the boundary rather than in production.
    if size < 1:
        raise ValueError("size must be at least 1")
    if overlap < 0:
        raise ValueError("overlap must not be negative")
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    text = text.strip()
    if not text:
        return []

    step = size - overlap
    windows: list[str] = []
    for start in range(0, len(text), step):
        windows.append(text[start : start + size])
        # Once a window reaches the end of the text, every later start would
        # only produce a suffix of a window already emitted. That is the bug
        # overlap introduces if you leave the loop to run out on its own.
        if start + size >= len(text):
            break
    return windows


def split_recursive(
    text: str, max_size: int, separators: list[str] | None = None
) -> list[str]:
    if max_size < 1:
        raise ValueError("max_size must be at least 1")

    # `None` rather than SEPARATORS as the default value: a mutable default is
    # shared across calls, and a caller who appends to it changes the function.
    separators = SEPARATORS if separators is None else separators
    stripped = text.strip()

    if not stripped:
        return []
    if len(stripped) <= max_size:
        return [stripped]

    # No separators left. Slicing on the character count is not a good chunk
    # boundary, but returning something oversized is worse: the caller's whole
    # contract is that a chunk fits.
    if not separators:
        return [
            piece
            for start in range(0, len(stripped), max_size)
            if (piece := stripped[start : start + max_size].strip())
        ]

    separator, rest = separators[0], separators[1:]
    pieces = stripped.split(separator)

    chunks: list[str] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer.strip():
            chunks.append(buffer.strip())
        buffer = ""

    for piece in pieces:
        if not piece.strip():
            continue

        # This piece does not fit even on its own, so a finer separator has to
        # deal with it. Passing `rest` rather than `separators` is what makes
        # the recursion terminate: each level has strictly fewer options.
        if len(piece) > max_size:
            flush()
            chunks.extend(split_recursive(piece, max_size, rest))
            continue

        # Greedy fill. Joining with the separator we split on keeps the text
        # reconstructible, and keeps chunks near the size limit instead of one
        # tiny chunk per paragraph.
        candidate = f"{buffer}{separator}{piece}" if buffer else piece
        if len(candidate) <= max_size:
            buffer = candidate
        else:
            flush()
            buffer = piece

    flush()
    return chunks


def chunk_document(
    text: str,
    max_size: int = 800,
    source: str = "",
    title: str = "",
    section: str = "",
) -> list[Chunk]:
    # enumerate() supplies the index, which means the index is always the
    # position in this document's chunk list and can never drift from it.
    return [
        Chunk(
            text=piece,
            index=index,
            metadata={"source": source, "title": title, "section": section},
        )
        for index, piece in enumerate(split_recursive(text, max_size))
    ]
