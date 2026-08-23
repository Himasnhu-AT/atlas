"""
Tests for: the conversation loop.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text, truncated

from solution import Conversation, TruncatedReply, trim_history

SYSTEM = {"role": "system", "content": "You are terse."}

TOOL_CALL = {
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}
    ],
}
TOOL_RESULT = {"role": "tool", "tool_call_id": "call_1", "content": "42"}
SECOND_RESULT = {"role": "tool", "tool_call_id": "call_2", "content": "43"}


def user(content: str) -> dict:
    return {"role": "user", "content": content}


def assistant(content: str) -> dict:
    return {"role": "assistant", "content": content}


class TestTrimHistory(unittest.TestCase):
    def test_a_short_conversation_is_returned_whole(self):
        messages = [SYSTEM, user("one"), assistant("two")]
        self.assertEqual(trim_history(messages, 10), messages)

    def test_keeps_the_last_n_non_system_messages(self):
        messages = [SYSTEM, user("one"), assistant("two"), user("three"), assistant("four")]
        self.assertEqual(
            trim_history(messages, 2),
            [SYSTEM, user("three"), assistant("four")],
            "keep_last counts messages other than the system message",
        )

    def test_the_system_message_survives_any_window(self):
        messages = [SYSTEM] + [user(f"turn {i}") for i in range(20)]
        self.assertEqual(
            trim_history(messages, 1)[0],
            SYSTEM,
            "the system message is never what you trim",
        )

    def test_works_without_a_system_message(self):
        messages = [user("one"), assistant("two"), user("three")]
        self.assertEqual(trim_history(messages, 2), [assistant("two"), user("three")])

    def test_the_window_never_starts_on_an_orphaned_tool_result(self):
        messages = [SYSTEM, user("q"), TOOL_CALL, TOOL_RESULT, assistant("a"), user("q2")]
        trimmed = trim_history(messages, 3)
        self.assertEqual(
            trimmed[1],
            TOOL_CALL,
            "a tool result without the assistant message that requested it is "
            "rejected by the provider, so the window has to move back to include it",
        )
        self.assertEqual(len(trimmed), 5)

    def test_the_window_may_keep_more_than_keep_last(self):
        messages = [user("q"), TOOL_CALL, TOOL_RESULT, user("q2")]
        trimmed = trim_history(messages, 2)
        self.assertEqual(
            len(trimmed),
            3,
            "when honouring keep_last would split a tool exchange, keep_last loses",
        )

    def test_the_window_walks_back_over_several_tool_results(self):
        messages = [user("q"), TOOL_CALL, TOOL_RESULT, SECOND_RESULT, user("q2")]
        trimmed = trim_history(messages, 2)
        self.assertEqual(trimmed, [TOOL_CALL, TOOL_RESULT, SECOND_RESULT, user("q2")])

    def test_a_window_landing_on_an_assistant_message_is_left_alone(self):
        messages = [user("q"), TOOL_CALL, TOOL_RESULT, assistant("a"), user("q2")]
        self.assertEqual(
            trim_history(messages, 2),
            [assistant("a"), user("q2")],
            "only a leading tool message forces the window open",
        )

    def test_returns_a_new_list_of_the_same_objects(self):
        messages = [SYSTEM, user("one"), assistant("two")]
        trimmed = trim_history(messages, 10)
        self.assertIsNot(trimmed, messages)
        self.assertIs(trimmed[1], messages[1], "trimming copies the list, not the messages")

    def test_a_keep_last_below_one_is_rejected(self):
        with self.assertRaises(ValueError):
            trim_history([SYSTEM, user("one")], 0)


class TestConversation(unittest.TestCase):
    def test_a_system_message_starts_the_history(self):
        chat = Conversation(MockClient([text("hi")]), system="You are terse.")
        self.assertEqual(chat.history(), [{"role": "system", "content": "You are terse."}])

    def test_the_history_starts_empty_without_a_system_message(self):
        self.assertEqual(Conversation(MockClient([text("hi")])).history(), [])

    def test_the_token_counter_starts_at_zero(self):
        self.assertEqual(Conversation(MockClient([text("hi")])).total_tokens_used, 0)

    def test_send_returns_the_reply_text(self):
        chat = Conversation(MockClient([text("Paris.")]))
        self.assertEqual(chat.send("Capital of France?"), "Paris.")

    def test_send_records_both_turns(self):
        chat = Conversation(MockClient([text("Paris.")]))
        chat.send("Capital of France?")
        self.assertEqual(
            chat.history(),
            [user("Capital of France?"), assistant("Paris.")],
        )

    def test_every_turn_resends_the_whole_history(self):
        client = MockClient([text("one"), text("two"), text("three")])
        chat = Conversation(client, system="S")
        chat.send("first")
        chat.send("second")
        chat.send("third")
        self.assertEqual(
            [len(request["messages"]) for request in client.requests],
            [2, 4, 6],
            "the model remembers nothing, so each turn resends the system message "
            "and every prior turn",
        )

    def test_assistant_turns_come_back_in_later_requests(self):
        client = MockClient([text("one"), text("two")])
        chat = Conversation(client)
        chat.send("first")
        chat.send("second")
        self.assertEqual(
            [message["role"] for message in client.requests[1]["messages"]],
            ["user", "assistant", "user"],
        )

    def test_token_usage_accumulates_across_turns(self):
        client = MockClient([text("one"), text("two")])
        chat = Conversation(client)
        chat.send("first")
        after_one = chat.total_tokens_used
        self.assertGreater(after_one, 0)
        chat.send("second")
        self.assertGreater(chat.total_tokens_used, after_one)

    def test_history_returns_a_copy(self):
        chat = Conversation(MockClient([text("hi")]), system="S")
        snapshot = chat.history()
        snapshot.append(user("injected"))
        self.assertEqual(len(chat.history()), 1, "history() must return a new list")

    def test_mutating_a_returned_message_does_not_corrupt_the_state(self):
        chat = Conversation(MockClient([text("hi")]), system="S")
        chat.history()[0]["content"] = "tampered"
        self.assertEqual(chat.history()[0]["content"], "S", "copy the dicts too")

    def test_reset_keeps_the_system_message(self):
        chat = Conversation(MockClient([text("hi")]), system="S")
        chat.send("something")
        chat.reset()
        self.assertEqual(chat.history(), [{"role": "system", "content": "S"}])

    def test_reset_empties_a_conversation_with_no_system_message(self):
        chat = Conversation(MockClient([text("hi")]))
        chat.send("something")
        chat.reset()
        self.assertEqual(chat.history(), [])

    def test_reset_keeps_the_token_total(self):
        chat = Conversation(MockClient([text("hi")]))
        chat.send("something")
        spent = chat.total_tokens_used
        chat.reset()
        self.assertEqual(chat.total_tokens_used, spent, "spent tokens do not come back")


class TestTruncationAndTheWindow(unittest.TestCase):
    def test_a_truncated_reply_raises(self):
        chat = Conversation(MockClient([truncated("The answer is fo")]))
        with self.assertRaises(TruncatedReply):
            chat.send("A long question")

    def test_the_partial_text_is_on_the_exception(self):
        chat = Conversation(MockClient([truncated("The answer is fo")]))
        with self.assertRaises(TruncatedReply) as caught:
            chat.send("A long question")
        self.assertEqual(caught.exception.partial, "The answer is fo")

    def test_a_truncated_reply_never_reaches_the_history(self):
        chat = Conversation(MockClient([truncated("half a th")]))
        with self.assertRaises(TruncatedReply):
            chat.send("question")
        self.assertEqual(
            [message["role"] for message in chat.history()],
            ["user"],
            "a fragment must not become the thing every later turn builds on",
        )

    def test_a_truncated_reply_is_still_billed(self):
        chat = Conversation(MockClient([truncated("half a th")]))
        with self.assertRaises(TruncatedReply):
            chat.send("question")
        self.assertGreater(
            chat.total_tokens_used, 0, "those tokens were generated and charged for"
        )

    def test_keep_last_bounds_what_is_sent(self):
        client = MockClient([text("one"), text("two"), text("three")])
        chat = Conversation(client, system="S", keep_last=3)
        chat.send("first")
        chat.send("second")
        chat.send("third")
        self.assertEqual(
            [len(request["messages"]) for request in client.requests],
            [2, 4, 4],
            "with a window the request stops growing instead of growing forever",
        )

    def test_the_window_always_contains_the_newest_question(self):
        client = MockClient([text("one"), text("two"), text("three")])
        chat = Conversation(client, system="S", keep_last=1)
        chat.send("first")
        chat.send("second")
        chat.send("third")
        self.assertEqual(
            client.requests[2]["messages"],
            [{"role": "system", "content": "S"}, user("third")],
            "trim after appending, so the question can never be trimmed away",
        )

    def test_a_keep_last_below_one_is_rejected(self):
        with self.assertRaises(ValueError):
            Conversation(MockClient([text("hi")]), keep_last=0)

    def test_no_keep_last_means_no_window(self):
        client = MockClient([text("one"), text("two")])
        chat = Conversation(client)
        chat.send("first")
        chat.send("second")
        self.assertEqual(len(chat.history()), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
