"""
Chunking.

A retriever returns chunks, and a chunk is what ends up in the prompt. Where you
put the boundaries decides what the model gets to read, so splitting is not a
preprocessing detail: it is the first place a retrieval system goes wrong.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Tried in order, coarsest first. Splitting on a blank line keeps a paragraph
#: whole; splitting on a space keeps nothing. You only fall through to a finer
#: separator when a piece is still too large after the coarser one.
SEPARATORS = ["\n\n", "\n", ". ", " "]


@dataclass
class Chunk:
    """
    A retrievable piece of a document, carrying enough to cite it.

    Attributes:
        text: the piece itself, already stripped.
        index: position within its document, counting from 0.
        metadata: where it came from. `source` is the document id, `title` and
            `section` are headings above the text. Values may be empty strings,
            which count as absent.

    The metadata is not decoration. A chunk with no idea which document it came
    from can be retrieved and put in a prompt, but it cannot be cited, and an
    answer you cannot trace back to a source is an answer you cannot check.
    """

    text: str
    index: int
    metadata: dict = field(default_factory=dict)

    def with_context(self) -> str:
        """
        The text to embed, prefixed with its title and section.

        Chunk four of a pricing page might read "It costs $49 per month" and
        nothing else. Embedded on its own it matches a query about $49 and
        nothing about pricing, because the words that would have matched are in
        a heading two hundred characters earlier. Prefixing the headings is the
        cheapest retrieval improvement available.

        Format, using the `title` and `section` keys of metadata:

            "<title> > <section>\\n\\n<text>"   both present
            "<title>\\n\\n<text>"               title only
            "<section>\\n\\n<text>"             section only
            "<text>"                           neither

        A missing key and an empty string are the same thing here.
        """
        raise NotImplementedError

    def citation(self) -> str:
        """
        A short label naming where this chunk came from.

        Returns "<source>#<index>" when metadata has a non-empty `source`, and
        "chunk <index>" when it does not. This string is what a caller puts next
        to a sentence in an answer, so it has to be stable and it has to be
        derived from the chunk rather than from anything the model said.
        """
        raise NotImplementedError


def split_fixed(text: str, size: int, overlap: int = 0) -> list[str]:
    """
    Split text into fixed length character windows, optionally overlapping.

    The blunt baseline. It ignores every boundary the document has and cuts on a
    counter, which is why it is worth writing once: it gives you something to
    compare a structure aware splitter against, and on genuinely unstructured
    text it is not much worse.

    Step forward by (size - overlap) characters each time. Overlap is what stops
    a sentence that straddles a boundary from being lost to both windows, and it
    costs you storage and duplicate hits in the results.

    Args:
        text: the document. Stripped before splitting.
        size: window length in characters. Must be at least 1.
        overlap: characters repeated from the end of the previous window. Must
            be at least 0 and strictly less than size, because an overlap equal
            to size means the window never advances.

    Returns:
        The windows in document order. The last one may be shorter than `size`.
        Never returns an empty string, and returns [] for input that is empty or
        only whitespace.

    Raises:
        ValueError: if size < 1, overlap < 0, or overlap >= size.
    """
    raise NotImplementedError


def split_recursive(
    text: str, max_size: int, separators: list[str] | None = None
) -> list[str]:
    """
    Split on the coarsest separator that produces pieces small enough to keep.

    This is the strategy most retrieval stacks land on, because it respects the
    document's own structure where the document has any and degrades to fixed
    slicing where it does not.

    The algorithm:
      1. Strip. If the result is empty, return []. If it already fits in
         max_size, return [it].
      2. Take the first separator and split on it.
      3. Walk the pieces, greedily joining consecutive ones back together while
         the join still fits max_size. Without this step a document of short
         paragraphs becomes a list of one-line chunks, each too small to carry
         its own meaning.
      4. A single piece still longer than max_size is split again with the
         REMAINING separators, not with the whole list, or you loop forever on
         the separator that did not help.
      5. With no separators left, slice on the character count.

    Args:
        text: the document.
        max_size: the largest chunk to produce, in characters.
        separators: defaults to SEPARATORS.

    Returns:
        Chunks in document order, each stripped and non-empty. Every chunk is at
        most max_size characters, except where a single unbreakable run of
        characters is longer than that on its own.

    Raises:
        ValueError: if max_size < 1.
    """
    raise NotImplementedError


def chunk_document(
    text: str,
    max_size: int = 800,
    source: str = "",
    title: str = "",
    section: str = "",
) -> list[Chunk]:
    """
    Split a document and attach citation metadata to every piece.

    Splits with split_recursive, then wraps each piece in a Chunk whose `index`
    is its position from 0 and whose metadata carries `source`, `title` and
    `section`. Write all three keys even when their values are empty, so callers
    can read metadata["source"] without guarding every access.

    The index is per document, not global. Two documents each produce a chunk 0,
    and the pair (source, index) is what identifies a chunk.
    """
    raise NotImplementedError
