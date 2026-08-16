"""
Tests for: chunking.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import Chunk, chunk_document, split_fixed, split_recursive

DOC = (
    "The Pro plan includes unlimited projects and priority support.\n\n"
    "It costs $49 per month, billed annually.\n\n"
    "The Free plan is limited to three projects and community support only."
)


class TestChunkMetadata(unittest.TestCase):
    def test_title_and_section(self):
        chunk = Chunk("Body text.", 0, {"title": "Pricing", "section": "Pro plan"})
        self.assertEqual(chunk.with_context(), "Pricing > Pro plan\n\nBody text.")

    def test_title_only(self):
        chunk = Chunk("Body text.", 0, {"title": "Pricing", "section": ""})
        self.assertEqual(chunk.with_context(), "Pricing\n\nBody text.")

    def test_section_only(self):
        chunk = Chunk("Body text.", 0, {"title": "", "section": "Pro plan"})
        self.assertEqual(chunk.with_context(), "Pro plan\n\nBody text.")

    def test_no_metadata_at_all(self):
        self.assertEqual(Chunk("Body text.", 0, {}).with_context(), "Body text.")

    def test_none_counts_as_absent(self):
        chunk = Chunk("Body text.", 0, {"title": None, "section": None})
        self.assertEqual(
            chunk.with_context(),
            "Body text.",
            "document parsers write None for a missing heading as often as they "
            "write an empty string, and both mean the same thing",
        )

    def test_citation_uses_the_source_and_index(self):
        chunk = Chunk("Body text.", 3, {"source": "pricing.md"})
        self.assertEqual(chunk.citation(), "pricing.md#3")

    def test_citation_without_a_source(self):
        self.assertEqual(Chunk("Body text.", 3, {}).citation(), "chunk 3")

    def test_citation_ignores_the_headings(self):
        chunk = Chunk("Body text.", 0, {"source": "pricing.md", "title": "Pricing"})
        self.assertEqual(
            chunk.citation(),
            "pricing.md#0",
            "a citation names the document, not the heading: two sections of one "
            "file must not produce two different sources",
        )


class TestSplitFixed(unittest.TestCase):
    def test_splits_into_windows(self):
        self.assertEqual(split_fixed("abcdefghij", 5), ["abcde", "fghij"])

    def test_final_window_may_be_short(self):
        self.assertEqual(split_fixed("abcdefg", 5), ["abcde", "fg"])

    def test_overlap_repeats_the_tail(self):
        self.assertEqual(
            split_fixed("abcdefghij", 5, overlap=2),
            ["abcde", "defgh", "ghij"],
            "each window starts (size - overlap) characters after the last one",
        )

    def test_overlap_does_not_emit_a_trailing_suffix(self):
        windows = split_fixed("abcdefghij", 5, overlap=3)
        self.assertEqual(
            windows[-1],
            "ghij",
            "stop once a window reaches the end of the text; carrying on emits "
            "windows that are suffixes of one already returned",
        )

    def test_text_shorter_than_the_window(self):
        self.assertEqual(split_fixed("abc", 10), ["abc"])

    def test_empty_input(self):
        self.assertEqual(split_fixed("", 10), [])
        self.assertEqual(split_fixed("   \n ", 10), [])

    def test_no_empty_windows(self):
        for window in split_fixed(DOC, 20, overlap=5):
            self.assertTrue(window, "an empty window is a hit that can never match")

    def test_cuts_through_a_sentence(self):
        # Not a bug, the point of the comparison: a counter does not know where
        # the answer is. split_recursive is tested for the opposite behaviour.
        windows = split_fixed(DOC, 70)
        self.assertFalse(
            any("It costs $49 per month, billed annually." in w for w in windows),
            "at this size a fixed split lands inside the price sentence",
        )

    def test_rejects_a_zero_size(self):
        with self.assertRaises(ValueError):
            split_fixed("abc", 0)

    def test_rejects_negative_overlap(self):
        with self.assertRaises(ValueError):
            split_fixed("abc", 5, overlap=-1)

    def test_rejects_overlap_at_or_above_size(self):
        with self.assertRaises(ValueError):
            split_fixed("abc", 5, overlap=5)


class TestSplitRecursive(unittest.TestCase):
    def test_short_text_is_one_chunk(self):
        self.assertEqual(split_recursive("short text", 100), ["short text"])

    def test_empty_input(self):
        self.assertEqual(split_recursive("", 100), [])
        self.assertEqual(split_recursive("  \n\n ", 100), [])

    def test_respects_the_size_limit(self):
        for chunk in split_recursive(DOC, 70):
            self.assertLessEqual(len(chunk), 70, f"chunk too long: {chunk!r}")

    def test_prefers_paragraph_boundaries(self):
        self.assertIn(
            "It costs $49 per month, billed annually.",
            split_recursive(DOC, 70),
            "the blank line is the best boundary available here, so the price "
            "sentence should survive whole",
        )

    def test_greedily_fills_chunks(self):
        self.assertEqual(
            len(split_recursive("aaa\n\nbbb\n\nccc", 100)),
            1,
            "three tiny paragraphs that fit in one chunk belong in one chunk",
        )

    def test_greedy_fill_stops_at_the_limit(self):
        chunks = split_recursive("aaaa\n\nbbbb\n\ncccc", 10)
        self.assertEqual(chunks, ["aaaa\n\nbbbb", "cccc"])

    def test_falls_through_to_finer_separators(self):
        text = "one sentence here. two sentence here. three sentence here."
        chunks = split_recursive(text, 25)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 25)

    def test_hard_splits_an_unbreakable_run(self):
        chunks = split_recursive("x" * 100, 30)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(
                len(chunk),
                30,
                "with no separator left, slice on the count rather than return "
                "something the caller cannot fit in a prompt",
            )

    def test_honours_a_custom_separator_list(self):
        chunks = split_recursive("a|b|c|d", 3, separators=["|"])
        self.assertEqual(chunks, ["a|b", "c|d"])

    def test_chunks_are_stripped_and_non_empty(self):
        for chunk in split_recursive(DOC, 50):
            self.assertEqual(chunk, chunk.strip())
            self.assertTrue(chunk)

    def test_preserves_order(self):
        chunks = split_recursive(DOC, 70)
        self.assertIn("Pro plan", chunks[0])
        self.assertIn("Free plan", chunks[-1])

    def test_no_content_is_lost(self):
        chunks = split_recursive(DOC, 40)
        rejoined = "".join(chunks).replace(" ", "")
        original = DOC.replace(" ", "").replace("\n", "")
        self.assertEqual(
            rejoined, original, "splitting rearranges text, it does not drop it"
        )

    def test_rejects_a_zero_max_size(self):
        with self.assertRaises(ValueError):
            split_recursive("abc", 0)


class TestChunkDocument(unittest.TestCase):
    def test_returns_chunks(self):
        chunks = chunk_document(DOC, max_size=70)
        self.assertTrue(all(isinstance(chunk, Chunk) for chunk in chunks))

    def test_indexes_are_sequential_from_zero(self):
        chunks = chunk_document(DOC, max_size=70)
        self.assertEqual([chunk.index for chunk in chunks], list(range(len(chunks))))

    def test_attaches_metadata_to_every_chunk(self):
        chunks = chunk_document(
            DOC, max_size=70, source="pricing.md", title="Pricing", section="Plans"
        )
        for chunk in chunks:
            self.assertEqual(chunk.metadata["source"], "pricing.md")
            self.assertEqual(chunk.metadata["title"], "Pricing")
            self.assertEqual(chunk.metadata["section"], "Plans")

    def test_metadata_keys_exist_even_when_empty(self):
        chunk = chunk_document("short", max_size=100)[0]
        for key in ("source", "title", "section"):
            self.assertIn(
                key,
                chunk.metadata,
                "always write the key: a caller that has to guard every read of "
                "metadata will eventually forget one",
            )

    def test_indexes_are_per_document(self):
        first = chunk_document(DOC, max_size=70, source="a.md")
        second = chunk_document(DOC, max_size=70, source="b.md")
        self.assertEqual(first[0].index, second[0].index)
        self.assertNotEqual(
            first[0].citation(),
            second[0].citation(),
            "the index is local to its document, so the source is what makes a "
            "citation unique across the corpus",
        )

    def test_context_prefix_works_end_to_end(self):
        chunk = chunk_document(DOC, max_size=70, title="Pricing")[1]
        self.assertTrue(chunk.with_context().startswith("Pricing\n\n"))

    def test_empty_document(self):
        self.assertEqual(chunk_document("", max_size=100), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
