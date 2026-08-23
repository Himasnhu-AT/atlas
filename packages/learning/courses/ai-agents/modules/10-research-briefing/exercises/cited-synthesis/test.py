"""
Tests for: writing the brief.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    Brief,
    Budget,
    Claim,
    Doc,
    Note,
    Research,
    number_notes,
    parse_claims,
    split_sentences,
    synthesis_messages,
    write_brief,
)

CORPUS = [
    Doc("d-solar", "Solar module prices", "Solar module prices fell 41 percent last year."),
    Doc("d-storage", "Grid battery storage", "Grid battery storage additions doubled."),
    Doc("d-queue", "Interconnection queue", "The median wait is now five years."),
    Doc("d-wind", "Offshore wind costs", "Offshore wind costs rose for the third year."),
]

# Deliberately not in doc id order, and with two notes from one document, so the
# numbering has something to sort.
NOTES = [
    Note("solar prices", "d-solar", "Solar module prices fell 41 percent last year.", "w1"),
    Note("storage", "d-storage", "Grid battery storage additions doubled.", "w2"),
    Note("solar prices", "d-solar", "Installers passed half of the decline on.", "w1"),
    Note("queue", "d-queue", "The median wait is now five years.", "w3"),
]

QUESTION = "What happened to renewable project economics last year?"

# S1 is the queue note, S2 and S3 are the two solar notes, S4 is storage.
PROSE = (
    "Module prices fell while storage additions doubled [S2] [S4]. "
    "Costs rose 15.5 percent for offshore wind [S9]. "
    "The median wait for interconnection is now five years [S1]. "
    "The notes do not cover policy changes."
)


def research(notes=None, corpus=None):
    return Research(
        question=QUESTION,
        sub_queries=["solar prices", "storage", "queue"],
        notes=NOTES if notes is None else notes,
        budget=Budget(limit=100_000),
        corpus=CORPUS if corpus is None else corpus,
    )


class TestNumberNotes(unittest.TestCase):
    def test_tags_run_from_s1_in_order(self):
        tagged = number_notes(NOTES)
        self.assertEqual([tag for tag, _ in tagged], ["S1", "S2", "S3", "S4"])

    def test_notes_are_ordered_by_doc_id(self):
        tagged = number_notes(NOTES)
        self.assertEqual(
            [note.doc_id for _, note in tagged],
            ["d-queue", "d-solar", "d-solar", "d-storage"],
            "notes must be numbered in doc id order so a brief's sources read in order",
        )

    def test_ties_break_on_first_appearance(self):
        tagged = dict(number_notes(NOTES))
        self.assertEqual(tagged["S2"].quote, "Solar module prices fell 41 percent last year.")
        self.assertEqual(tagged["S3"].quote, "Installers passed half of the decline on.")

    def test_numbering_is_stable_across_calls(self):
        first = [(tag, note.quote) for tag, note in number_notes(NOTES)]
        second = [(tag, note.quote) for tag, note in number_notes(NOTES)]
        self.assertEqual(
            first,
            second,
            "two runs over the same notes must produce the same tags, or a citation "
            "means something different every time you regenerate the brief",
        )


class TestSynthesisMessages(unittest.TestCase):
    def test_each_note_is_rendered_with_its_tag(self):
        messages = synthesis_messages(QUESTION, number_notes(NOTES))
        blob = "\n".join(message["content"] for message in messages)
        self.assertIn("[S1] d-queue: The median wait is now five years.", blob)
        self.assertIn("[S4] d-storage: Grid battery storage additions doubled.", blob)

    def test_the_question_is_in_the_prompt(self):
        messages = synthesis_messages(QUESTION, number_notes(NOTES))
        blob = "\n".join(message["content"] for message in messages)
        self.assertIn(QUESTION, blob)

    def test_the_model_is_told_to_tag_and_to_invent_nothing(self):
        messages = synthesis_messages(QUESTION, number_notes(NOTES))
        blob = "\n".join(message["content"] for message in messages).lower()
        self.assertIn("tag", blob, "the instruction to tag every factual sentence is missing")
        self.assertTrue(
            "nothing" in blob or "only" in blob,
            "the prompt must forbid writing what no note supports",
        )


class TestSplitSentences(unittest.TestCase):
    def test_splits_on_terminators_and_keeps_them(self):
        self.assertEqual(
            split_sentences("Prices fell. Storage doubled! Did it? Yes."),
            ["Prices fell.", "Storage doubled!", "Did it?", "Yes."],
        )

    def test_a_decimal_does_not_end_a_sentence(self):
        self.assertEqual(
            split_sentences("Costs rose 15.5 percent."),
            ["Costs rose 15.5 percent."],
            "15.5 is one number, not the end of a sentence",
        )

    def test_an_abbreviation_does_not_end_a_sentence(self):
        self.assertEqual(
            split_sentences("Some costs rose, e.g. vessel day rates. Others fell."),
            ["Some costs rose, e.g. vessel day rates.", "Others fell."],
        )

    def test_newlines_are_boundaries_too(self):
        self.assertEqual(
            split_sentences("Prices fell.\nStorage doubled."),
            ["Prices fell.", "Storage doubled."],
        )

    def test_empty_text_gives_no_sentences(self):
        self.assertEqual(split_sentences("   "), [])


class TestParseClaims(unittest.TestCase):
    def test_two_tags_in_one_sentence_keep_their_order(self):
        claims = parse_claims("Prices fell and storage doubled [S2] [S1].", ["S1", "S2"])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].tags, ["S2", "S1"])

    def test_an_unknown_tag_is_routed_away_from_tags(self):
        claims = parse_claims("Wind costs rose [S9].", ["S1", "S2"])
        self.assertEqual(claims[0].tags, [], "S9 names no note, so it cites nothing")
        self.assertEqual(claims[0].unknown_tags, ["S9"])

    def test_an_untagged_sentence_has_neither(self):
        claims = parse_claims("Policy changes are not covered.", ["S1"])
        self.assertEqual(claims[0].tags, [])
        self.assertEqual(claims[0].unknown_tags, [])

    def test_a_repeated_tag_is_recorded_once(self):
        claims = parse_claims("Prices fell [S1] and fell again [S1].", ["S1"])
        self.assertEqual(claims[0].tags, ["S1"])

    def test_every_sentence_becomes_a_claim(self):
        claims = parse_claims(PROSE, ["S1", "S2", "S3", "S4"])
        self.assertEqual(len(claims), 4)
        self.assertIsInstance(claims[0], Claim)


class TestWriteBrief(unittest.TestCase):
    def setUp(self):
        self.client = MockClient([text(PROSE)])
        self.research = research()
        self.brief = write_brief(self.client, self.research)

    def test_the_synthesis_call_goes_on_the_meter(self):
        budget = self.research.budget
        self.assertIn(
            "synthesis",
            budget.by_stage,
            "the supervisor call is a model call. A run that meters the workers and "
            "not the synthesis reports a total smaller than the invoice, and the "
            "stage it loses is the one carrying every note at once",
        )
        self.assertGreater(budget.by_stage["synthesis"], 0)
        self.assertEqual(
            budget.spent,
            sum(budget.by_stage.values()),
            "the total and the per stage figures must describe the same run",
        )

    def test_exactly_one_model_call(self):
        self.assertEqual(
            self.client.call_count,
            1,
            "the supervisor formats once. Per worker formatting is the overhead this "
            "design exists to remove",
        )
        self.assertIsInstance(self.brief, Brief)

    def test_the_prose_survives_verbatim(self):
        self.assertIn(
            PROSE,
            self.brief.text,
            "the verification pass edits this text later, so it has to be the model's "
            "words unchanged",
        )

    def test_a_two_tag_sentence_records_both(self):
        self.assertEqual(self.brief.claims[0].tags, ["S2", "S4"])

    def test_an_unknown_tag_surfaces_on_the_brief(self):
        self.assertEqual(self.brief.unknown, ["S9"])
        self.assertNotIn("S9", self.brief.claims[1].tags)

    def test_an_uncited_sentence_is_reported_and_kept(self):
        self.assertIn("The notes do not cover policy changes.", self.brief.uncited)
        self.assertIn(
            "The notes do not cover policy changes.",
            self.brief.text,
            "deleting the sentence would hide the problem instead of reporting it",
        )

    def test_the_sources_block_lists_cited_documents_once(self):
        self.assertIn("Sources", self.brief.text)
        self.assertIn("d-solar: Solar module prices", self.brief.text)
        self.assertIn("d-queue: Interconnection queue", self.brief.text)
        self.assertEqual(
            self.brief.text.count("d-solar:"),
            1,
            "two notes from one document is still one source",
        )

    def test_the_sources_block_omits_uncited_documents(self):
        self.assertNotIn(
            "d-wind",
            self.brief.text,
            "nothing cited the wind document, so listing it claims support that is "
            "not there",
        )

    def test_the_title_line_carries_the_question(self):
        self.assertIn(QUESTION, self.brief.text.splitlines()[0])
        self.assertEqual(self.brief.question, QUESTION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
