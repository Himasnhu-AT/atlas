"""
Tests for: self-consistency.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import agree, normalise, sample, suits_self_consistency, tally


class TestNormalise(unittest.TestCase):
    def test_makes_four_spellings_of_one_answer_equal(self):
        forms = ["42", "42.", "The answer is 42", " 42 "]
        self.assertEqual(
            len({normalise(f) for f in forms}),
            1,
            "counted raw these give four groups of one and no majority",
        )

    def test_lowercases_and_trims(self):
        self.assertEqual(normalise("  Yes  "), "yes")

    def test_strips_surrounding_punctuation(self):
        self.assertEqual(normalise("yes!"), "yes")
        self.assertEqual(normalise('"yes"'), "yes")

    def test_collapses_internal_whitespace(self):
        self.assertEqual(normalise("not   sure"), "not sure")

    def test_keeps_a_worded_answer_as_words(self):
        self.assertEqual(normalise("Paris"), "paris")

    def test_does_not_collapse_two_numbers_into_one(self):
        # "between 40 and 50" is not the answer "40".
        self.assertNotEqual(normalise("between 40 and 50"), "40")

    def test_keeps_a_sentence_that_carries_meaning_besides_the_number(self):
        self.assertNotEqual(normalise("42 units were recalled in March"), "42")


class TestSample(unittest.TestCase):
    def test_asks_n_times(self):
        client = MockClient([text("42")] * 5)
        answers = sample(client, "how many?", n=5)
        self.assertEqual(len(answers), 5)
        self.assertEqual(client.call_count, 5)

    def test_passes_the_temperature_on_every_call(self):
        client = MockClient([text("42")] * 3)
        sample(client, "q", n=3, temperature=0.7)
        for request in client.requests:
            self.assertEqual(
                request.get("temperature"),
                0.7,
                "at temperature 0 every sample is identical and you have paid "
                "n times for one answer",
            )

    def test_returns_the_replies_in_order(self):
        client = MockClient([text("a"), text("b"), text("c")])
        self.assertEqual(sample(client, "q", n=3), ["a", "b", "c"])


class TestTally(unittest.TestCase):
    def test_counts_normalised_answers(self):
        self.assertEqual(tally(["42", "The answer is 42", "43"]), [("42", 2), ("43", 1)])

    def test_orders_by_count_descending(self):
        counts = [c for _, c in tally(["a", "b", "b", "c", "c", "c"])]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_breaks_a_tie_the_same_way_every_run(self):
        first = tally(["zebra", "apple"])
        second = tally(["apple", "zebra"])
        self.assertEqual(
            first,
            second,
            "a mode that moves between runs is a strange property for a method "
            "whose point is stability",
        )

    def test_empty_is_empty(self):
        self.assertEqual(tally([]), [])


class TestAgree(unittest.TestCase):
    def test_unanimous_is_high_confidence(self):
        result = agree(["42"] * 5)
        self.assertEqual(result["answer"], "42")
        self.assertEqual(result["agreement"], 1.0)
        self.assertEqual(result["confidence"], "high")
        self.assertFalse(result["escalate"])

    def test_a_three_two_split_is_marked_uncertain(self):
        result = agree(["42", "42", "42", "43", "43"])
        self.assertEqual(result["answer"], "42")
        self.assertAlmostEqual(result["agreement"], 0.6)
        self.assertEqual(result["confidence"], "split")
        self.assertTrue(
            result["escalate"],
            "reporting a three-two split as a confident answer throws away the "
            "one thing the method produced",
        )

    def test_total_scatter_is_its_own_state(self):
        result = agree(["a", "b", "c", "d", "e"])
        self.assertEqual(
            result["confidence"],
            "scatter",
            "usually means the question is underspecified or the information is "
            "not in the context, and more sampling fixes neither",
        )
        self.assertTrue(result["escalate"])

    def test_reports_the_whole_distribution(self):
        result = agree(["42", "42", "43"])
        self.assertEqual(result["distribution"], [("42", 2), ("43", 1)])

    def test_honours_the_threshold(self):
        answers = ["42", "42", "42", "42", "43"]
        self.assertEqual(agree(answers, split_threshold=0.8)["confidence"], "high")
        self.assertEqual(agree(answers, split_threshold=0.9)["confidence"], "split")

    def test_no_samples_is_not_an_answer(self):
        result = agree([])
        self.assertEqual(result["answer"], "")
        self.assertEqual(result["agreement"], 0.0)
        self.assertTrue(result["escalate"])

    def test_two_different_answers_are_a_split_not_scatter(self):
        # Two samples that disagree is not evidence of an underspecified
        # question; it is just a small sample.
        self.assertEqual(agree(["a", "b"])["confidence"], "split")

    def test_the_spread_distinguishes_two_cases_one_draw_cannot(self):
        confident = agree(["42"] * 5)
        uncertain = agree(["42", "43", "42", "44", "43"])
        self.assertEqual(confident["answer"], "42")
        self.assertEqual(uncertain["answer"], "42")
        self.assertNotEqual(
            confident["confidence"],
            uncertain["confidence"],
            "same answer, very different states, and one draw shows neither",
        )


class TestSuitability(unittest.TestCase):
    def test_short_answers_suit_it(self):
        self.assertTrue(suits_self_consistency(["42", "forty two"]))

    def test_prose_does_not(self):
        prose = [
            "The model shipped in March after a lengthy delay caused by supply "
            "problems, and sold well through the summer."
        ]
        self.assertFalse(
            suits_self_consistency(prose),
            "two summaries are never equal, and a normaliser that makes them "
            "equal is measuring nothing",
        )

    def test_one_long_answer_spoils_it(self):
        self.assertFalse(suits_self_consistency(["42", " ".join(["word"] * 20)]))

    def test_empty_does_not_suit_it(self):
        self.assertFalse(suits_self_consistency([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
