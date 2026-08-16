"""
Tests for: reading a completion.

The fixtures are built by running mockllm's script helpers through a real
client, so the objects under test are exactly the ones every later exercise
receives. The two hand built completions are the cases mockllm cannot script: a
stop turn with no content, and a finish_reason that did not exist yet.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import (
    Choice,
    Completion,
    Message,
    MockClient,
    Usage,
    text,
    tool_call,
    tool_calls,
    truncated,
)

from solution import (
    IncompleteReply,
    answer_text,
    describe,
    finish_reason,
    stopped_early,
    tool_names,
    total_tokens,
    usage_totals,
)

QUESTION = [{"role": "user", "content": "What time does the shop close?"}]


def completion_for(step, messages=None):
    """Play one scripted step through a real client and keep what comes back."""
    client = MockClient([step])
    return client.chat.completions.create(model="mock", messages=messages or QUESTION)


def hand_built(reason: str, content: str | None = "anything") -> Completion:
    """A completion mockllm has no script helper for."""
    return Completion(
        choices=[Choice(message=Message(content=content), finish_reason=reason)],
        usage=Usage(prompt_tokens=40, completion_tokens=12),
    )


class TestReadingTheChoice(unittest.TestCase):
    def test_finish_reason_of_a_text_reply(self):
        self.assertEqual(finish_reason(completion_for(text("Six on weekdays."))), "stop")

    def test_finish_reason_of_a_truncated_reply(self):
        self.assertEqual(finish_reason(completion_for(truncated("Six on week"))), "length")

    def test_finish_reason_of_a_tool_call(self):
        step = tool_call("get_hours", {"day": "monday"})
        self.assertEqual(finish_reason(completion_for(step)), "tool_calls")

    def test_stopped_early_is_true_only_for_length(self):
        self.assertTrue(stopped_early(completion_for(truncated("Six on week"))))

    def test_stopped_early_is_false_for_a_finished_reply(self):
        self.assertFalse(stopped_early(completion_for(text("Six on weekdays."))))

    def test_stopped_early_is_false_for_a_tool_call(self):
        step = tool_call("get_hours", {"day": "monday"})
        self.assertFalse(
            stopped_early(completion_for(step)),
            "a tool call is not a truncation: the model finished the turn it meant to take",
        )

    def test_answer_text_returns_the_content(self):
        self.assertEqual(answer_text(completion_for(text("Six on weekdays."))), "Six on weekdays.")

    def test_answer_text_refuses_a_truncated_reply(self):
        with self.assertRaises(IncompleteReply) as caught:
            answer_text(completion_for(truncated("Six on week")))
        self.assertEqual(
            caught.exception.finish_reason,
            "length",
            "the exception carries the reason, because the caller's next move depends on it",
        )

    def test_answer_text_refuses_a_tool_call_turn(self):
        step = tool_call("get_hours", {"day": "monday"})
        with self.assertRaises(IncompleteReply) as caught:
            answer_text(completion_for(step))
        self.assertEqual(caught.exception.finish_reason, "tool_calls")

    def test_answer_text_refuses_an_unknown_finish_reason(self):
        with self.assertRaises(IncompleteReply):
            answer_text(hand_built("content_filter"))

    def test_answer_text_of_an_empty_stop_turn_is_a_string(self):
        self.assertEqual(
            answer_text(hand_built("stop", content=None)),
            "",
            "a finished turn with no content still returns text, not None",
        )

    def test_tool_names_is_empty_on_a_text_reply(self):
        self.assertEqual(
            tool_names(completion_for(text("Six on weekdays."))),
            [],
            "tool_calls is None on a text turn, so iterating it directly raises TypeError",
        )

    def test_tool_names_reads_a_single_call(self):
        step = tool_call("get_hours", {"day": "monday"})
        self.assertEqual(tool_names(completion_for(step)), ["get_hours"])

    def test_tool_names_keeps_call_order(self):
        step = tool_calls([("get_hours", {"day": "monday"}), ("get_address", {})])
        self.assertEqual(
            tool_names(completion_for(step)),
            ["get_hours", "get_address"],
            "call order is the model describing a sequence: do not sort it",
        )


class TestUsage(unittest.TestCase):
    def test_total_tokens_adds_both_halves(self):
        self.assertEqual(total_tokens(hand_built("stop")), 52)

    def test_usage_totals_of_nothing_is_zeroes(self):
        self.assertEqual(usage_totals([]), {"prompt": 0, "completion": 0, "total": 0})

    def test_usage_totals_sums_every_turn(self):
        first, second = hand_built("stop"), hand_built("stop")
        self.assertEqual(
            usage_totals([first, second]),
            {"prompt": 80, "completion": 24, "total": 104},
            "every call is billed, so sum the list rather than reading the last entry",
        )

    def test_prompt_tokens_grow_as_the_conversation_does(self):
        client = MockClient([text("Six on weekdays."), text("Closed on Sunday.")])
        history = list(QUESTION)
        first = client.chat.completions.create(model="mock", messages=history)

        history = history + [
            {"role": "assistant", "content": "Six on weekdays."},
            {"role": "user", "content": "And Sunday? I need to know before I set off."},
        ]
        second = client.chat.completions.create(model="mock", messages=history)

        self.assertGreater(
            second.usage.prompt_tokens,
            first.usage.prompt_tokens,
            "the whole history is re-sent every turn, so the prompt half keeps growing",
        )
        summed = usage_totals([first, second])
        self.assertEqual(summed["total"], total_tokens(first) + total_tokens(second))


class TestDescribe(unittest.TestCase):
    def test_describes_a_finished_reply(self):
        completion = completion_for(text("Six on weekdays."))
        self.assertEqual(
            describe(completion),
            f'stop: "Six on weekdays." ({total_tokens(completion)} tokens)',
        )

    def test_describes_a_truncated_reply_without_pretending_it_is_an_answer(self):
        completion = completion_for(truncated("Six on week"))
        self.assertEqual(
            describe(completion),
            f"length: truncated after {total_tokens(completion)} tokens",
        )

    def test_describes_a_tool_call_turn(self):
        completion = completion_for(
            tool_calls([("get_hours", {"day": "monday"}), ("get_address", {})])
        )
        self.assertEqual(
            describe(completion),
            f"tool_calls: get_hours, get_address ({total_tokens(completion)} tokens)",
        )

    def test_names_a_finish_reason_it_does_not_know(self):
        self.assertEqual(
            describe(hand_built("content_filter")),
            "content_filter: unrecognised finish reason (52 tokens)",
            "the set of finish reasons is open: a value you have never seen must "
            "not fall through into the branch that reads it as an answer",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
