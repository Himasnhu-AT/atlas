"""
Tests for: context budget.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    conversation_tokens,
    estimate_tokens,
    headroom,
    loop_cost,
    message_tokens,
    trim_to_budget,
)


def user(content: str) -> dict:
    return {"role": "user", "content": content}


def assistant(content: str) -> dict:
    return {"role": "assistant", "content": content}


SYSTEM = {"role": "system", "content": "You are terse."}


class TestCounting(unittest.TestCase):
    def test_empty_text_is_free(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("   \n  "), 0)

    def test_cost_scales_with_word_count(self):
        self.assertEqual(estimate_tokens("one two three"), 4)
        self.assertEqual(estimate_tokens("a b c d e f g h i j"), 13)

    def test_a_single_word_costs_at_least_one(self):
        self.assertEqual(
            estimate_tokens("hello"), 1, "round(1.3) is 1, and the floor keeps it there"
        )

    def test_a_message_pays_the_role_overhead(self):
        self.assertEqual(message_tokens(user("one two three")), 7)

    def test_a_message_with_no_content_still_costs_the_overhead(self):
        self.assertEqual(
            message_tokens({"role": "assistant"}),
            3,
            "an assistant message carrying only tool calls is not free",
        )
        self.assertEqual(message_tokens({"role": "assistant", "content": None}), 3)

    def test_a_conversation_is_the_sum_of_its_messages(self):
        messages = [SYSTEM, user("one two three"), assistant("ok")]
        self.assertEqual(
            conversation_tokens(messages),
            sum(message_tokens(message) for message in messages),
        )

    def test_an_empty_conversation_costs_nothing(self):
        self.assertEqual(conversation_tokens([]), 0)


class TestBudgetArithmetic(unittest.TestCase):
    def test_headroom_subtracts_both_the_history_and_the_reserve(self):
        messages = [SYSTEM, user("one two three")]
        spent = conversation_tokens(messages)
        self.assertEqual(headroom(messages, 1000, 200), 1000 - 200 - spent)

    def test_headroom_goes_negative_on_an_overrun(self):
        messages = [user(" ".join(["word"] * 500))]
        self.assertLess(
            headroom(messages, 100, 20),
            0,
            "an overrun must report its size, not clamp to zero",
        )

    def test_headroom_rejects_an_impossible_configuration(self):
        with self.assertRaises(ValueError):
            headroom([], 0, 0)
        with self.assertRaises(ValueError):
            headroom([], 1000, -1)
        with self.assertRaises(ValueError):
            headroom([], 1000, 1000)

    def test_a_loop_of_no_steps_costs_nothing(self):
        self.assertEqual(loop_cost(500, 100, 0), 0)

    def test_one_step_sends_only_the_base_prompt(self):
        self.assertEqual(loop_cost(500, 100, 1), 500)

    def test_each_step_resends_everything_before_it(self):
        # 500 + 600 + 700 + 800
        self.assertEqual(
            loop_cost(500, 100, 4),
            2600,
            "step n sends the base prompt plus everything the earlier steps added",
        )

    def test_cost_grows_quadratically_in_the_step_count(self):
        small = loop_cost(0, 100, 10)
        large = loop_cost(0, 100, 20)
        self.assertEqual(small, 4500)
        self.assertEqual(large, 19000)
        self.assertGreater(
            large / small,
            4.0,
            "doubling the step count should more than quadruple the resend cost",
        )

    def test_loop_cost_rejects_negative_arguments(self):
        with self.assertRaises(ValueError):
            loop_cost(-1, 100, 4)
        with self.assertRaises(ValueError):
            loop_cost(500, 100, -4)


class TestTrimToBudget(unittest.TestCase):
    def test_returns_everything_when_it_fits(self):
        messages = [SYSTEM, user("hello"), assistant("hi")]
        self.assertEqual(trim_to_budget(messages, 1000), messages)

    def test_handles_an_empty_conversation(self):
        self.assertEqual(trim_to_budget([], 100), [])

    def test_keeps_the_system_message_first(self):
        messages = [SYSTEM] + [assistant(f"filler number {i}") for i in range(20)]
        messages.append(user("the real question"))
        trimmed = trim_to_budget(messages, 40)
        self.assertEqual(trimmed[0], SYSTEM, "the system message must stay first")

    def test_always_keeps_the_latest_user_message(self):
        messages = [SYSTEM] + [assistant(f"filler number {i}") for i in range(50)]
        messages.append(user("the real question"))
        trimmed = trim_to_budget(messages, 20)
        self.assertIn(user("the real question"), trimmed)

    def test_drops_the_oldest_first(self):
        messages = [
            user("oldest message here"),
            assistant("middle message here"),
            user("newest message here"),
        ]
        trimmed = trim_to_budget(messages, 14)
        self.assertNotIn(messages[0], trimmed, "the oldest should go first")
        self.assertIn(messages[2], trimmed)

    def test_stops_rather_than_skipping_past_a_message_that_does_not_fit(self):
        # Working backwards: the question is pinned, "tiny" fits, the long
        # message does not. "reachable" is small enough to fit in what is left,
        # and taking it would leave a hole where the long message was.
        messages = [
            user("reachable"),
            assistant(" ".join(["long"] * 30)),
            assistant("tiny"),
            user("question"),
        ]
        trimmed = trim_to_budget(messages, 20)
        self.assertNotIn(
            messages[0],
            trimmed,
            "stop at the first message that does not fit: reaching past it leaves a "
            "hole the model cannot see",
        )
        self.assertEqual([m["content"] for m in trimmed], ["tiny", "question"])

    def test_preserves_original_order(self):
        messages = [SYSTEM, user("first"), assistant("second"), user("third")]
        trimmed = trim_to_budget(messages, 1000)
        self.assertEqual([m["content"] for m in trimmed], [m["content"] for m in messages])

    def test_respects_the_budget(self):
        messages = [SYSTEM] + [assistant(f"filler number {i}") for i in range(40)]
        messages.append(user("q"))
        budget = 60
        trimmed = trim_to_budget(messages, budget)
        total = conversation_tokens(trimmed)
        self.assertLessEqual(total, budget, f"kept {total} tokens against a budget of {budget}")

    def test_returns_the_pinned_messages_even_when_they_overflow(self):
        long_system = {"role": "system", "content": " ".join(["word"] * 100)}
        question = user(" ".join(["question"] * 100))
        self.assertEqual(
            trim_to_budget([long_system, question], 10),
            [long_system, question],
            "over budget with the question intact beats answering nothing",
        )

    def test_does_not_mutate_the_input(self):
        messages = [SYSTEM, user("hello"), assistant("hi"), user("bye")]
        before = list(messages)
        trim_to_budget(messages, 5)
        self.assertEqual(messages, before, "trim_to_budget must not modify its argument")

    def test_returns_the_original_message_objects(self):
        messages = [SYSTEM, user("hello"), user("bye")]
        trimmed = trim_to_budget(messages, 1000)
        self.assertIs(
            trimmed[-1], messages[-1], "hand back the same dicts, just fewer of them"
        )

    def test_works_without_a_system_message(self):
        messages = [user("first one here"), assistant("second"), user("third one here")]
        trimmed = trim_to_budget(messages, 12)
        self.assertIn(messages[2], trimmed)
        self.assertLessEqual(conversation_tokens(trimmed), 12)

    def test_a_conversation_with_no_user_message_still_trims(self):
        messages = [SYSTEM] + [assistant(f"note number {i}") for i in range(10)]
        trimmed = trim_to_budget(messages, 25)
        self.assertEqual(trimmed[0], SYSTEM)
        self.assertLessEqual(conversation_tokens(trimmed), 25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
