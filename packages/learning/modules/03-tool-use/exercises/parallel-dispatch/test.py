"""
Tests for: parallel tool calls.

Run with `python3 test.py`.
"""

from __future__ import annotations

import json
import threading
import unittest
from types import SimpleNamespace

from mockllm import MockClient, text, tool_calls

from solution import (
    MaxStepsExceeded,
    ToolResult,
    dispatch_all,
    format_tool_messages,
    lookup_population,
    lookup_timezone,
    run_agent,
    run_one,
)

REGISTRY = {"lookup_population": lookup_population, "lookup_timezone": lookup_timezone}
TOOLS = [
    {"type": "function", "function": {"name": "lookup_population"}},
    {"type": "function", "function": {"name": "lookup_timezone"}},
]


def calls_for(specs: list[tuple]) -> list:
    """The tool calls a model would produce for one turn."""
    client = MockClient([tool_calls(specs)])
    return client.chat.completions.create(messages=[]).choices[0].message.tool_calls


def raw_call(call_id: str, name: str, arguments_json: str):
    """A call carrying arguments a real model produced and a real model got wrong."""
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=arguments_json)
    )


def gated_registry() -> dict:
    """
    Two tools where the first cannot finish until the second has run.

    Dispatched concurrently they both return. Dispatched one after another, in
    request order, the first one waits for something that has not happened yet
    and gives up.
    """
    gate = threading.Event()

    def waits() -> str:
        return "waited" if gate.wait(timeout=2.0) else "ran on its own"

    def opens() -> str:
        gate.set()
        return "opened"

    return {"waits": waits, "opens": opens}


def roles(request: dict) -> list[str]:
    return [message["role"] for message in request["messages"]]


def tool_contents(request: dict) -> list[str]:
    return [m["content"] for m in request["messages"] if m["role"] == "tool"]


class TestRunOne(unittest.TestCase):
    def test_a_working_call(self):
        call = calls_for([("lookup_population", {"city": "Paris"})])[0]
        result = run_one(REGISTRY, call)
        self.assertTrue(result.ok)
        self.assertEqual(result.name, "lookup_population")
        self.assertEqual(result.call_id, call.id)
        self.assertEqual(json.loads(result.content)["population"], 2_102_650)

    def test_a_string_result_is_not_re_encoded(self):
        call = calls_for([("lookup_timezone", {"city": "Tokyo"})])[0]
        self.assertEqual(run_one(REGISTRY, call).content, "Asia/Tokyo")

    def test_a_tool_that_raises_becomes_a_failed_result(self):
        call = calls_for([("lookup_population", {"city": "Atlantis"})])[0]
        result = run_one(REGISTRY, call)
        self.assertFalse(result.ok)
        self.assertTrue(
            result.content.startswith("error:"),
            f"a failed result's content starts with 'error: '. Got: {result.content!r}",
        )
        self.assertIn("LookupError", result.content, "name the exception type")
        self.assertIn(
            "Atlantis",
            result.content,
            "the exception's own message has to survive: it is what tells the model "
            "which argument was the problem",
        )

    def test_an_unknown_tool_becomes_a_failed_result(self):
        result = run_one(REGISTRY, raw_call("c1", "teleport", "{}"))
        self.assertFalse(result.ok)
        self.assertIn("lookup_timezone", result.content, "list what it could have called")

    def test_unparseable_arguments_become_a_failed_result(self):
        result = run_one(REGISTRY, raw_call("c1", "lookup_population", "{city: Paris"))
        self.assertFalse(result.ok)
        self.assertEqual(result.call_id, "c1", "a failed call still answers its own id")

    def test_arguments_that_are_not_an_object_become_a_failed_result(self):
        result = run_one(REGISTRY, raw_call("c1", "lookup_population", '["Paris"]'))
        self.assertFalse(result.ok)

    def test_nothing_escapes(self):
        for call in (
            raw_call("c1", "teleport", "{}"),
            raw_call("c2", "lookup_population", "{broken"),
            raw_call("c3", "lookup_population", '{"city": "Atlantis"}'),
        ):
            self.assertIsInstance(
                run_one(REGISTRY, call),
                ToolResult,
                "run_one never raises: one raise leaves the rest of the batch unanswered",
            )


class TestDispatchAll(unittest.TestCase):
    def test_one_result_per_call_in_request_order(self):
        calls = calls_for(
            [
                ("lookup_timezone", {"city": "Tokyo"}),
                ("lookup_timezone", {"city": "Paris"}),
                ("lookup_timezone", {"city": "Lagos"}),
            ]
        )
        results = dispatch_all(REGISTRY, calls)
        self.assertEqual([r.call_id for r in results], [c.id for c in calls])
        self.assertEqual(
            [r.content for r in results],
            ["Asia/Tokyo", "Europe/Paris", "Africa/Lagos"],
        )

    def test_an_empty_batch(self):
        self.assertEqual(dispatch_all(REGISTRY, []), [])

    def test_one_failure_does_not_take_the_batch_with_it(self):
        calls = calls_for(
            [
                ("lookup_population", {"city": "Paris"}),
                ("lookup_population", {"city": "Atlantis"}),
                ("lookup_timezone", {"city": "Tokyo"}),
            ]
        )
        results = dispatch_all(REGISTRY, calls)
        self.assertEqual(
            [r.ok for r in results],
            [True, False, True],
            "two succeeded and one failed, and you still owe the model three results",
        )

    def test_the_batch_actually_runs_concurrently(self):
        registry = gated_registry()
        calls = calls_for([("waits", {}), ("opens", {})])
        results = dispatch_all(registry, calls, max_workers=2)
        self.assertEqual(
            [r.content for r in results],
            ["waited", "opened"],
            "the first call cannot finish until the second has run, so a batch "
            "dispatched one call at a time never gets 'waited'",
        )

    def test_completion_order_does_not_reorder_the_results(self):
        registry = gated_registry()
        calls = calls_for([("waits", {}), ("opens", {})])
        results = dispatch_all(registry, calls, max_workers=2)
        self.assertEqual(
            [r.name for r in results],
            ["waits", "opens"],
            "'opens' finishes first and still comes second: request order wins",
        )


class TestFormatToolMessages(unittest.TestCase):
    def setUp(self):
        self.calls = calls_for(
            [
                ("lookup_timezone", {"city": "Tokyo"}),
                ("lookup_timezone", {"city": "Paris"}),
            ]
        )
        self.results = dispatch_all(REGISTRY, self.calls)

    def test_one_message_per_call_in_call_order(self):
        messages = format_tool_messages(self.calls, self.results)
        self.assertEqual([m["role"] for m in messages], ["tool", "tool"])
        self.assertEqual(
            [m["tool_call_id"] for m in messages], [c.id for c in self.calls]
        )

    def test_the_content_comes_from_the_result(self):
        messages = format_tool_messages(self.calls, self.results)
        self.assertEqual(messages[0]["content"], "Asia/Tokyo")

    def test_results_are_paired_by_id_not_by_position(self):
        messages = format_tool_messages(self.calls, list(reversed(self.results)))
        self.assertEqual(
            messages[0]["content"],
            "Asia/Tokyo",
            "the id pairs a result to its call; zip() only pairs by luck",
        )

    def test_an_unanswered_call_is_an_error(self):
        with self.assertRaises(ValueError):
            format_tool_messages(self.calls, self.results[:1])

    def test_a_result_for_a_call_that_was_never_made_is_an_error(self):
        stray = ToolResult("call_99_0", "lookup_timezone", "Europe/Oslo", ok=True)
        with self.assertRaises(ValueError):
            format_tool_messages(self.calls, self.results + [stray])


class TestRunAgent(unittest.TestCase):
    def test_three_calls_in_one_turn_produce_three_tool_messages(self):
        client = MockClient(
            [
                tool_calls(
                    [
                        ("lookup_population", {"city": "Paris"}),
                        ("lookup_population", {"city": "Tokyo"}),
                        ("lookup_population", {"city": "Lagos"}),
                    ]
                ),
                text("Lagos is the largest of the three."),
            ]
        )
        answer = run_agent(client, REGISTRY, TOOLS, "Which of the three is largest?")
        self.assertEqual(answer, "Lagos is the largest of the three.")
        self.assertEqual(
            roles(client.requests[1]),
            ["user", "assistant", "tool", "tool", "tool"],
            "one assistant message carrying every call, then one tool message per call",
        )

    def test_every_call_is_answered_with_its_own_id_in_order(self):
        client = MockClient(
            [
                tool_calls(
                    [
                        ("lookup_timezone", {"city": "Paris"}),
                        ("lookup_timezone", {"city": "Tokyo"}),
                    ]
                ),
                text("done"),
            ]
        )
        run_agent(client, REGISTRY, TOOLS, "timezones?")
        sent = client.requests[1]["messages"]
        requested = [call["id"] for call in sent[1]["tool_calls"]]
        answered = [m["tool_call_id"] for m in sent if m["role"] == "tool"]
        self.assertEqual(requested, answered)

    def test_a_partial_failure_still_answers_every_call(self):
        client = MockClient(
            [
                tool_calls(
                    [
                        ("lookup_population", {"city": "Paris"}),
                        ("lookup_population", {"city": "Atlantis"}),
                        ("lookup_timezone", {"city": "Tokyo"}),
                    ]
                ),
                text("I could not find Atlantis, but here are the other two."),
            ]
        )
        answer = run_agent(client, REGISTRY, TOOLS, "three lookups")
        self.assertEqual(
            answer,
            "I could not find Atlantis, but here are the other two.",
            "a batch with a failure in it still ends by returning the model's final "
            "content, unchanged. Checking for a substring of that text would pass on "
            "any answer the fixture happens to contain",
        )

        contents = tool_contents(client.requests[1])
        self.assertEqual(len(contents), 3)
        self.assertTrue(
            contents[1].startswith("error:"),
            "the failure goes back in the slot the failing call asked for",
        )
        self.assertIn(
            "Atlantis",
            contents[1],
            "and it carries the failing tool's own message, so the model can see "
            f"which call failed and why. Got: {contents[1]!r}",
        )
        self.assertFalse(contents[0].startswith("error:"), "the others are unaffected")

    def test_a_batch_turn_and_a_single_turn_in_one_run(self):
        client = MockClient(
            [
                tool_calls(
                    [
                        ("lookup_population", {"city": "Paris"}),
                        ("lookup_population", {"city": "Tokyo"}),
                    ]
                ),
                tool_calls([("lookup_timezone", {"city": "Tokyo"})]),
                text("Tokyo is larger and nine hours ahead."),
            ]
        )
        run_agent(client, REGISTRY, TOOLS, "compare them")
        self.assertEqual(
            roles(client.requests[2]),
            ["user", "assistant", "tool", "tool", "assistant", "tool"],
        )

    def test_one_assistant_message_per_turn(self):
        client = MockClient(
            [
                tool_calls(
                    [
                        ("lookup_timezone", {"city": "Paris"}),
                        ("lookup_timezone", {"city": "Tokyo"}),
                    ]
                ),
                text("done"),
            ]
        )
        run_agent(client, REGISTRY, TOOLS, "q")
        assistants = [m for m in client.requests[1]["messages"] if m["role"] == "assistant"]
        self.assertEqual(len(assistants), 1)
        self.assertEqual(
            len(assistants[0]["tool_calls"]),
            2,
            "both calls belong to the same assistant message",
        )

    def test_the_budget_still_applies(self):
        client = MockClient(
            [tool_calls([("lookup_timezone", {"city": "Paris"})])] * 8, strict=False
        )
        with self.assertRaises(MaxStepsExceeded):
            run_agent(client, REGISTRY, TOOLS, "loop", max_steps=3)
        self.assertEqual(client.call_count, 3)

    def test_a_worker_count_below_one_is_a_caller_bug(self):
        with self.assertRaises(ValueError):
            run_agent(MockClient([text("hi")]), REGISTRY, TOOLS, "q", max_workers=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
