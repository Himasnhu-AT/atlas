"""
Tests for: prompt assembly.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import assemble, build_messages, select_examples, similarity, tokenize

#: A deliberately lopsided bank: half of it is billing. That imbalance is what
#: the per label cap exists to survive.
TICKETS = [
    ("The app crashes on startup after the update.", "bug"),
    ("I was charged twice this month.", "billing"),
    ("Can you add dark mode?", "feature"),
    ("My invoice shows the wrong VAT rate.", "billing"),
    ("The export button does nothing when I click it.", "bug"),
    ("I want a refund because sync ate my data.", "billing"),
]

#: Overlaps all three billing tickets and nothing else.
BILLING_QUERY = "I was charged twice and my invoice is wrong"


class TestOverlap(unittest.TestCase):
    def test_tokenize_lowercases_and_splits(self):
        self.assertEqual(tokenize("The Cat SAT"), {"the", "cat", "sat"})

    def test_tokenize_keeps_apostrophes_and_digits(self):
        self.assertEqual(tokenize("doesn't work in v2"), {"doesn't", "work", "in", "v2"})

    def test_tokenize_drops_punctuation_and_duplicates(self):
        self.assertEqual(tokenize("hello, hello world!"), {"hello", "world"})

    def test_tokenize_of_empty_string(self):
        self.assertEqual(tokenize(""), set())

    def test_identical_strings_score_one(self):
        self.assertEqual(similarity("the cat sat", "the cat sat"), 1.0)

    def test_no_overlap_scores_zero(self):
        self.assertEqual(similarity("cat", "dog"), 0.0)

    def test_partial_overlap(self):
        # shared {the, cat} = 2, union {the, cat, sat, ran} = 4
        self.assertAlmostEqual(similarity("the cat sat", "the cat ran"), 0.5)

    def test_empty_side_scores_zero(self):
        self.assertEqual(
            similarity("", "the cat"),
            0.0,
            "an empty input is unusable, not similar to everything",
        )

    def test_is_symmetric(self):
        a, b = "the quick brown fox", "the lazy brown dog"
        self.assertAlmostEqual(similarity(a, b), similarity(b, a))


class TestSelectExamples(unittest.TestCase):
    def test_returns_k_examples(self):
        self.assertEqual(len(select_examples(TICKETS, BILLING_QUERY, k=3)), 3)

    def test_most_similar_comes_last(self):
        chosen = select_examples(TICKETS, BILLING_QUERY, k=3)
        self.assertEqual(
            chosen[-1][0],
            "I was charged twice this month.",
            "the closest example belongs nearest the real question, so the list is "
            "least similar first: a plain descending sort is backwards",
        )

    def test_picks_the_relevant_examples(self):
        chosen = select_examples(TICKETS, BILLING_QUERY, k=3)
        self.assertEqual(
            [label for _, label in chosen],
            ["billing", "billing", "billing"],
            "without a cap, nearest neighbours over a lopsided bank are lopsided",
        )

    def test_a_cap_forces_variety(self):
        chosen = select_examples(TICKETS, BILLING_QUERY, k=3, max_per_label=1)
        labels = [label for _, label in chosen]
        self.assertEqual(
            sorted(labels),
            ["billing", "bug", "feature"],
            "with max_per_label=1 the second and third billing tickets are skipped "
            "and the next best of another label takes the slot",
        )

    def test_a_cap_does_not_change_the_ordering_rule(self):
        chosen = select_examples(TICKETS, BILLING_QUERY, k=3, max_per_label=1)
        self.assertEqual(chosen[-1][1], "billing", "the strongest example still goes last")

    def test_a_cap_can_return_fewer_than_k(self):
        bank = [("charged twice", "billing"), ("wrong invoice", "billing")]
        chosen = select_examples(bank, "my invoice is wrong", k=2, max_per_label=1)
        self.assertEqual(
            len(chosen), 1, "when the cap binds, return fewer rather than backfilling past it"
        )

    def test_no_cap_by_default(self):
        chosen = select_examples(TICKETS, BILLING_QUERY, k=2)
        self.assertEqual([label for _, label in chosen], ["billing", "billing"])

    def test_k_larger_than_the_bank_returns_everything(self):
        self.assertEqual(len(select_examples(TICKETS, "anything", k=99)), len(TICKETS))

    def test_empty_bank_and_zero_k_return_empty(self):
        self.assertEqual(select_examples([], "anything", k=3), [])
        self.assertEqual(select_examples(TICKETS, "anything", k=0), [])

    def test_ties_break_toward_the_earlier_example(self):
        bank = [("alpha", "1"), ("beta", "2"), ("gamma", "3")]
        self.assertEqual(
            select_examples(bank, "nothing matches here", k=2),
            [("beta", "2"), ("alpha", "1")],
            "all three score zero, so the first two in the bank are chosen, and the "
            "result is reversed on the way out",
        )

    def test_selection_is_repeatable(self):
        first = select_examples(TICKETS, BILLING_QUERY, k=3, max_per_label=2)
        second = select_examples(TICKETS, BILLING_QUERY, k=3, max_per_label=2)
        self.assertEqual(first, second, "a prompt that reorders itself cannot be measured")


class TestAssembly(unittest.TestCase):
    def test_system_message_comes_first(self):
        messages = build_messages("Classify tickets.", [], "help")
        self.assertEqual(messages[0], {"role": "system", "content": "Classify tickets."})

    def test_no_system_message_when_none_or_empty(self):
        self.assertEqual([m["role"] for m in build_messages(None, [], "help")], ["user"])
        self.assertEqual([m["role"] for m in build_messages("", [], "help")], ["user"])

    def test_examples_alternate_user_and_assistant(self):
        messages = build_messages(None, [("in one", "out one"), ("in two", "out two")], "real")
        self.assertEqual(
            [m["role"] for m in messages],
            ["user", "assistant", "user", "assistant", "user"],
            "the alternation is the delimiter, so it has to hold for every pair",
        )

    def test_example_content_is_preserved_in_order(self):
        messages = build_messages(None, [("in one", "out one")], "real")
        self.assertEqual(messages[0]["content"], "in one")
        self.assertEqual(messages[1]["content"], "out one")

    def test_real_input_comes_last_and_alone(self):
        messages = build_messages("S", [("a", "b")], "the real question")
        self.assertEqual(messages[-1], {"role": "user", "content": "the real question"})

    def test_build_messages_does_not_reorder_examples(self):
        given = [("z", "1"), ("a", "2")]
        messages = build_messages(None, given, "real")
        self.assertEqual(
            [messages[0]["content"], messages[2]["content"]],
            ["z", "a"],
            "select_examples already decided the order; re-sorting here undoes it",
        )

    def test_assemble_matches_its_two_halves(self):
        chosen = select_examples(TICKETS, BILLING_QUERY, k=2, max_per_label=1)
        self.assertEqual(
            assemble("Classify.", TICKETS, BILLING_QUERY, k=2, max_per_label=1),
            build_messages("Classify.", chosen, BILLING_QUERY),
        )

    def test_assemble_produces_the_expected_shape(self):
        messages = assemble("Classify support tickets.", TICKETS, BILLING_QUERY, k=2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1]["content"], BILLING_QUERY)
        self.assertEqual(len(messages), 1 + 2 * 2 + 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
