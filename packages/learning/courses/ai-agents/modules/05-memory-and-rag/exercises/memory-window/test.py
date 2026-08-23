"""
Tests for: conversation memory.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    SUMMARY_PREFIX,
    ManagedContext,
    estimate_tokens,
    extract_facts,
    manage,
    summarize_older,
    tool_groups,
    window,
)


def conversation() -> list[dict]:
    """
    Five groups after the system message, one of which is a tool exchange.

    Fresh objects every call, because several tests compare by identity.
    """
    return [
        {"role": "system", "content": "You are a booking assistant."},
        {"role": "user", "content": "Book me a table in Lisbon for four people."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "search_restaurants",
                        "arguments": '{"city": "Lisbon", "party": 4}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "Three with space tonight: Ramiro, Belcanto, Prado.",
        },
        {"role": "assistant", "content": "Ramiro, Belcanto and Prado all have space."},
        {"role": "user", "content": "Prado, eight o'clock."},
        {"role": "assistant", "content": "Booked Prado for four at eight."},
    ]


def cost(messages: list[dict]) -> int:
    return sum(estimate_tokens(message) for message in messages)


def has_broken_exchange(messages: list[dict]) -> bool:
    """True if any tool call lost its result, or any result lost its call."""
    for position, message in enumerate(messages):
        if message.get("role") == "assistant" and message.get("tool_calls"):
            following = messages[position + 1 : position + 2]
            if not following or following[0].get("role") != "tool":
                return True
        if message.get("role") == "tool":
            previous = messages[position - 1] if position else None
            if not previous or not previous.get("tool_calls"):
                if not (previous and previous.get("role") == "tool"):
                    return True
    return False


class TestToolGroups(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(tool_groups([]), [])

    def test_plain_messages_are_groups_of_one(self):
        messages = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        self.assertEqual(tool_groups(messages), [[messages[0]], [messages[1]]])

    def test_a_tool_result_joins_the_call_that_asked_for_it(self):
        messages = conversation()
        groups = tool_groups(messages[1:])
        self.assertEqual(
            groups[1],
            [messages[2], messages[3]],
            "the assistant asking for a tool and the tool result answering it "
            "are one unit; half of that pair is not a valid request",
        )

    def test_group_count(self):
        self.assertEqual(len(tool_groups(conversation()[1:])), 5)

    def test_several_results_join_one_call(self):
        messages = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "a", "type": "function", "function": {"name": "x", "arguments": "{}"}},
                    {"id": "b", "type": "function", "function": {"name": "y", "arguments": "{}"}},
                ],
            },
            {"role": "tool", "tool_call_id": "a", "content": "1"},
            {"role": "tool", "tool_call_id": "b", "content": "2"},
        ]
        self.assertEqual(len(tool_groups(messages)), 1)

    def test_an_orphan_tool_result_gets_its_own_group(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "tool", "tool_call_id": "gone", "content": "orphan"},
        ]
        self.assertEqual(
            len(tool_groups(messages)),
            2,
            "history an earlier trim mangled still has to be handled, not "
            "crashed on",
        )

    def test_flattening_gives_the_input_back(self):
        messages = conversation()
        flat = [message for group in tool_groups(messages) for message in group]
        self.assertEqual(flat, messages)

    def test_groups_hold_the_original_objects(self):
        messages = conversation()
        self.assertIs(tool_groups(messages)[0][0], messages[0])


class TestWindow(unittest.TestCase):
    def test_everything_fits(self):
        messages = conversation()
        self.assertEqual(window(messages, cost(messages)), messages)

    def test_trims_from_the_front(self):
        messages = conversation()
        budget = cost(messages[:1]) + cost(messages[-2:])
        kept = window(messages, budget)
        self.assertEqual(kept, [messages[0], messages[-2], messages[-1]])

    def test_the_system_message_survives_any_budget(self):
        messages = conversation()
        self.assertEqual(
            window(messages, 1),
            [messages[0]],
            "the system message is the agent's instructions; dropping it to "
            "save tokens changes what the agent is",
        )

    def test_the_whole_leading_system_run_survives(self):
        messages = conversation()
        messages.insert(1, {"role": "system", "content": f"{SUMMARY_PREFIX}\nEarlier: a booking."})
        kept = window(messages, 1)
        self.assertEqual(
            kept,
            messages[:2],
            "a summary inserted after the system message has to be protected "
            "too, or the next trim drops the summary and keeps the turns it "
            "was supposed to replace",
        )

    def test_a_conversation_with_no_system_message(self):
        messages = conversation()[1:]
        kept = window(messages, cost(messages[-1:]))
        self.assertEqual(kept, messages[-1:])

    def test_never_leaves_half_a_tool_exchange(self):
        messages = conversation()
        # Room for everything after the tool exchange, plus the tool result on
        # its own but not the assistant message that asked for it.
        budget = cost(messages[:1]) + cost(messages[4:]) + estimate_tokens(messages[3])
        kept = window(messages, budget)
        self.assertNotIn(
            messages[3], kept, "the tool result must go when its call cannot fit"
        )
        self.assertNotIn(messages[2], kept)
        self.assertFalse(has_broken_exchange(kept))

    def test_keeps_the_tool_exchange_whole_when_it_fits(self):
        messages = conversation()
        budget = cost(messages[:1]) + cost(messages[2:])
        kept = window(messages, budget)
        self.assertIn(messages[2], kept)
        self.assertIn(messages[3], kept)
        self.assertNotIn(messages[1], kept)

    def test_stops_rather_than_skipping(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "old and short"},
            {"role": "assistant", "content": "x" * 4000},
            {"role": "user", "content": "recent"},
        ]
        budget = cost(messages[:2]) + estimate_tokens(messages[3])
        kept = window(messages, budget)
        self.assertNotIn(
            messages[1],
            kept,
            "skipping the oversized message to fit an older one leaves a hole "
            "in the middle of the conversation, and nothing downstream can see "
            "that the hole is there",
        )
        self.assertEqual(kept, [messages[0], messages[3]])

    def test_result_is_contiguous(self):
        messages = conversation()
        kept = window(messages, cost(messages[:1]) + cost(messages[4:]))
        tail = [message for message in messages if message in kept and message is not messages[0]]
        self.assertEqual(kept[1:], tail)

    def test_does_not_mutate_the_input(self):
        messages = conversation()
        before = len(messages)
        window(messages, 1)
        self.assertEqual(len(messages), before)

    def test_keeps_the_original_objects(self):
        messages = conversation()
        kept = window(messages, cost(messages))
        self.assertIs(kept[0], messages[0])

    def test_a_custom_estimate_is_used(self):
        messages = conversation()
        kept = window(messages, 3, estimate_fn=lambda message: 1)
        self.assertEqual(
            len(kept), 3, "the budget is whatever estimate_fn says it is"
        )


class TestSummarizeOlder(unittest.TestCase):
    def test_a_short_conversation_is_left_alone(self):
        client = MockClient([text("never used")])
        messages = conversation()[:3]
        self.assertEqual(summarize_older(client, messages, keep_recent=3), messages)

    def test_a_short_conversation_costs_no_call(self):
        client = MockClient([text("never used")])
        summarize_older(client, conversation()[:3], keep_recent=3)
        self.assertEqual(client.call_count, 0)

    def test_replaces_the_older_groups_with_one_summary(self):
        client = MockClient([text("User wants a table for four in Lisbon.")])
        messages = conversation()
        result = summarize_older(client, messages, keep_recent=2)
        self.assertEqual(result[0], messages[0])
        self.assertTrue(result[1]["content"].startswith(SUMMARY_PREFIX))
        self.assertIn("User wants a table for four in Lisbon.", result[1]["content"])
        self.assertEqual(result[2:], messages[-2:])

    def test_makes_exactly_one_call(self):
        client = MockClient([text("summary")])
        summarize_older(client, conversation(), keep_recent=2)
        self.assertEqual(client.call_count, 1)

    def test_sends_the_older_messages_to_be_summarised(self):
        client = MockClient([text("summary")])
        summarize_older(client, conversation(), keep_recent=2)
        sent = client.requests[0]["messages"][1]["content"]
        self.assertIn("Book me a table in Lisbon", sent)
        self.assertNotIn("Booked Prado for four", sent)

    def test_the_summary_sits_inside_the_protected_prefix(self):
        client = MockClient([text("summary")])
        result = summarize_older(client, conversation(), keep_recent=2)
        self.assertEqual([message["role"] for message in result[:2]], ["system", "system"])

    def test_keep_recent_counts_groups_not_messages(self):
        client = MockClient([text("summary")])
        result = summarize_older(client, conversation(), keep_recent=4)
        # The four newest groups are the tool exchange, which is two messages,
        # plus three single-message turns.
        self.assertEqual(len(result), 1 + 1 + 5)
        self.assertFalse(has_broken_exchange(result[2:]))

    def test_works_without_a_system_message(self):
        client = MockClient([text("summary")])
        messages = conversation()[1:]
        result = summarize_older(client, messages, keep_recent=1)
        self.assertTrue(result[0]["content"].startswith(SUMMARY_PREFIX))


class TestExtractFacts(unittest.TestCase):
    def test_parses_a_json_array(self):
        client = MockClient([text('["Party of four", "Prefers Prado"]')])
        self.assertEqual(
            extract_facts(client, conversation()), ["Party of four", "Prefers Prado"]
        )

    def test_strips_and_drops_empties(self):
        client = MockClient([text('["  Party of four  ", "", "   "]')])
        self.assertEqual(extract_facts(client, conversation()), ["Party of four"])

    def test_dedupes_keeping_the_first(self):
        client = MockClient([text('["a", "b", "a"]')])
        self.assertEqual(extract_facts(client, conversation()), ["a", "b"])

    def test_skips_entries_that_are_not_strings(self):
        client = MockClient([text('["a", {"fact": "b"}, 3]')])
        self.assertEqual(extract_facts(client, conversation()), ["a"])

    def test_a_reply_that_is_not_json_returns_nothing(self):
        client = MockClient([text("Sorry, I can't help with that.")])
        self.assertEqual(
            extract_facts(client, conversation()),
            [],
            "fact extraction is a background nicety; a confused model must not "
            "take down the turn the user is waiting on",
        )

    def test_json_that_is_not_a_list_returns_nothing(self):
        client = MockClient([text('{"facts": ["a"]}')])
        self.assertEqual(extract_facts(client, conversation()), [])

    def test_an_empty_conversation_costs_no_call(self):
        client = MockClient([text("never used")])
        self.assertEqual(extract_facts(client, []), [])
        self.assertEqual(client.call_count, 0)


class TestManage(unittest.TestCase):
    def test_a_conversation_that_fits_is_returned_unchanged(self):
        client = MockClient([text("never used")])
        messages = conversation()
        result = manage(client, messages, cost(messages))
        self.assertIsInstance(result, ManagedContext)
        self.assertEqual(result.messages, messages)
        self.assertEqual(result.dropped, [])
        self.assertEqual(result.facts, [])

    def test_a_conversation_that_fits_costs_no_calls(self):
        client = MockClient([text("never used")])
        messages = conversation()
        manage(client, messages, cost(messages))
        self.assertEqual(
            client.call_count, 0, "most turns fit, and the common path has to be free"
        )

    def test_trims_and_reports(self):
        client = MockClient([text("Booking a table in Lisbon."), text('["Party of four"]')])
        messages = conversation()
        result = manage(client, messages, cost(messages) // 2, keep_recent=2)
        self.assertLessEqual(cost(result.messages), cost(messages) // 2)
        self.assertTrue(result.dropped)
        self.assertEqual(result.facts, ["Party of four"])

    def test_uses_two_calls_when_it_trims(self):
        client = MockClient([text("summary"), text('["a fact"]')])
        messages = conversation()
        manage(client, messages, cost(messages) // 2, keep_recent=2)
        self.assertEqual(
            client.call_count,
            2,
            "one call to summarise and one to extract facts; a trim is not free "
            "and the cost belongs in the budget you plan for",
        )

    def test_the_summary_survives_the_window(self):
        client = MockClient([text("Booking a table in Lisbon."), text("[]")])
        messages = conversation()
        result = manage(client, messages, cost(messages) // 2, keep_recent=2)
        self.assertTrue(
            any(
                message["content"].startswith(SUMMARY_PREFIX)
                for message in result.messages
                if isinstance(message.get("content"), str)
            ),
            "the whole point of paying for a summary is that it is still there "
            "after the trim",
        )

    def test_dropped_holds_the_original_messages(self):
        client = MockClient([text("summary"), text("[]")])
        messages = conversation()
        result = manage(client, messages, cost(messages) // 2, keep_recent=2)
        for message in result.dropped:
            self.assertTrue(any(message is original for original in messages))
        for message in result.dropped:
            self.assertFalse(any(message is kept for kept in result.messages))

    def test_identical_messages_are_told_apart(self):
        client = MockClient([text("summary"), text("[]")])
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "same"},
            {"role": "assistant", "content": "x" * 800},
            {"role": "user", "content": "same"},
            {"role": "assistant", "content": "done"},
        ]
        result = manage(client, messages, 60, keep_recent=1)
        self.assertIn(
            messages[1],
            messages,
            "sanity check: the two user messages are equal and are not the same "
            "message",
        )
        self.assertTrue(
            any(dropped is messages[1] for dropped in result.dropped),
            "compare by identity: an equality check would report the surviving "
            "copy as proof that the dropped one is still there",
        )

    def test_never_leaves_half_a_tool_exchange(self):
        client = MockClient([text("summary"), text("[]")])
        messages = conversation()
        result = manage(client, messages, cost(messages) // 2, keep_recent=4)
        self.assertFalse(has_broken_exchange(result.messages))

    def test_facts_come_from_the_dropped_messages(self):
        client = MockClient([text("summary"), text('["Party of four"]')])
        messages = conversation()
        manage(client, messages, cost(messages) // 2, keep_recent=2)
        sent = client.requests[1]["messages"][1]["content"]
        self.assertIn("Book me a table in Lisbon", sent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
