"""
Tests for: check your setup.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    count_words,
    first_reply,
    last_user_message,
    role_counts,
    summarise_messages,
)

CONVERSATION = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What time does the shop close?"},
    {"role": "assistant", "content": "Six on weekdays."},
    {"role": "user", "content": "And Sunday?"},
]


class TestCountingWords(unittest.TestCase):
    def test_counts_words(self):
        self.assertEqual(count_words("hello there"), 2)

    def test_an_empty_string_is_zero(self):
        self.assertEqual(count_words(""), 0)

    def test_none_is_zero(self):
        self.assertEqual(
            count_words(None),
            0,
            "content is None on a turn that only calls a tool, so this has to "
            "return a number rather than raise",
        )

    def test_collapses_runs_of_whitespace(self):
        self.assertEqual(
            count_words("  spaced   out  words \n here "),
            4,
            "str.split() with no argument already splits on runs of whitespace; "
            'split(" ") does not and gives you empty strings',
        )

    def test_summarise_counts_messages_and_words(self):
        self.assertEqual(summarise_messages(CONVERSATION), "4 messages, 16 words")

    def test_summarise_handles_an_empty_conversation(self):
        self.assertEqual(summarise_messages([]), "0 messages, 0 words")

    def test_summarise_does_not_pluralise(self):
        one = [{"role": "user", "content": "hello there"}]
        self.assertEqual(
            summarise_messages(one),
            "1 messages, 2 words",
            "the format is fixed: N messages, M words, however many there are",
        )


class TestReadingMessages(unittest.TestCase):
    def test_role_counts_counts_each_role(self):
        self.assertEqual(
            role_counts(CONVERSATION),
            {"system": 1, "user": 2, "assistant": 1},
        )

    def test_role_counts_omits_roles_that_never_appear(self):
        counts = role_counts(CONVERSATION)
        self.assertNotIn(
            "tool",
            counts,
            "report the roles that are there, not the ones you expected",
        )

    def test_role_counts_of_an_empty_conversation_is_empty(self):
        self.assertEqual(role_counts([]), {})

    def test_last_user_message_takes_the_most_recent_one(self):
        self.assertEqual(
            last_user_message(CONVERSATION),
            "And Sunday?",
            "search from the end: the question being asked is the last user "
            "turn, not the first",
        )

    def test_last_user_message_ignores_other_roles(self):
        messages = [
            {"role": "user", "content": "the question"},
            {"role": "assistant", "content": "the answer"},
        ]
        self.assertEqual(last_user_message(messages), "the question")

    def test_last_user_message_is_none_when_there_is_no_user_turn(self):
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        self.assertIsNone(last_user_message(messages))


class TestTheMockClient(unittest.TestCase):
    def test_returns_the_assistant_text(self):
        client = MockClient([text("Hello back.")])
        self.assertEqual(first_reply(client), "Hello back.")

    def test_calls_the_model_once(self):
        client = MockClient([text("Hello back.")])
        first_reply(client)
        self.assertEqual(
            client.call_count,
            1,
            "one call, not zero and not several: every call to a real provider "
            "is a bill and a wait",
        )

    def test_sends_a_single_user_message(self):
        client = MockClient([text("Hello back.")])
        first_reply(client)
        sent = client.requests[0]["messages"]
        self.assertEqual(len(sent), 1, "send one message, not a whole conversation")
        self.assertEqual(sent[0]["role"], "user")
        self.assertEqual(sent[0]["content"], "Hello.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
