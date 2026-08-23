"""
Tests for: the ReAct loop, from scratch.

Run with `python3 test.py`.
"""

from __future__ import annotations

import json
import unittest

from mockllm import MockClient, text, tool_call, tool_calls, truncated

from solution import (
    MaxStepsExceeded,
    ToolError,
    TruncatedAnswer,
    assistant_turn,
    calculator,
    lookup_population,
    run_agent,
    to_tool_content,
    tool_result_turn,
)

REGISTRY = {"calculator": calculator, "lookup_population": lookup_population}
TOOLS = [
    {
        "type": "function",
        "function": {"name": "calculator", "description": "Evaluate arithmetic."},
    },
    {
        "type": "function",
        "function": {"name": "lookup_population", "description": "Population of a city."},
    },
]


def roles(request: dict) -> list[str]:
    return [message["role"] for message in request["messages"]]


class TestTools(unittest.TestCase):
    """
    These four check the tools the scaffold provides, not the work you are
    doing. They pass before you write a line, which is deliberate: they are here
    so a red test elsewhere is never the fixtures. Count your progress from the
    other four classes.
    """

    def test_calculator_evaluates(self):
        self.assertEqual(calculator("(19 * 42) - 8"), "790")

    def test_calculator_refuses_anything_that_is_not_arithmetic(self):
        self.assertTrue(
            calculator("__import__('os')").startswith("error:"),
            "the character allowlist is what keeps this from being a way to run "
            "arbitrary code: never hand model output to a bare eval()",
        )

    def test_population_lookup_returns_a_dict(self):
        self.assertEqual(lookup_population("Paris")["population"], 2_102_650)

    def test_population_miss_is_still_a_result(self):
        self.assertFalse(lookup_population("Atlantis")["found"])


class TestToolContent(unittest.TestCase):
    def test_a_string_passes_through(self):
        self.assertEqual(to_tool_content("790"), "790")

    def test_a_dict_becomes_json(self):
        self.assertEqual(
            to_tool_content({"b": 2, "a": 1}),
            '{"a": 1, "b": 2}',
            "JSON, with sorted keys, not Python's repr",
        )

    def test_a_list_becomes_json(self):
        self.assertEqual(to_tool_content(["a", "b"]), '["a", "b"]')

    def test_booleans_serialize_the_way_the_model_reads_them(self):
        self.assertIn(
            "true",
            to_tool_content({"found": True}),
            "str() would send Python's True, which is not JSON",
        )

    def test_anything_else_becomes_a_string(self):
        self.assertEqual(to_tool_content(4), "4")


class TestMessageBuilders(unittest.TestCase):
    def _choice(self):
        client = MockClient([tool_call("calculator", {"expression": "1+1"})])
        return client.chat.completions.create(messages=[]).choices[0]

    def test_assistant_turn_shape(self):
        turn = assistant_turn(self._choice())
        self.assertEqual(turn["role"], "assistant")
        self.assertEqual(len(turn["tool_calls"]), 1)
        self.assertEqual(turn["tool_calls"][0]["type"], "function")
        self.assertEqual(turn["tool_calls"][0]["function"]["name"], "calculator")

    def test_assistant_turn_keeps_the_call_id(self):
        choice = self._choice()
        turn = assistant_turn(choice)
        self.assertEqual(turn["tool_calls"][0]["id"], choice.message.tool_calls[0].id)

    def test_assistant_turn_keeps_the_raw_argument_string(self):
        choice = self._choice()
        turn = assistant_turn(choice)
        self.assertEqual(
            turn["tool_calls"][0]["function"]["arguments"],
            choice.message.tool_calls[0].function.arguments,
            "send back the JSON string the model produced, not your own re-encoding",
        )

    def test_tool_result_turn_shape(self):
        self.assertEqual(
            tool_result_turn("call_1_0", "790"),
            {"role": "tool", "tool_call_id": "call_1_0", "content": "790"},
        )


class TestRunAgent(unittest.TestCase):
    def test_an_answer_with_no_tools_costs_one_call(self):
        client = MockClient([text("Paris is the capital of France.")])
        answer = run_agent(client, REGISTRY, TOOLS, "Capital of France?")
        self.assertEqual(answer, "Paris is the capital of France.")
        self.assertEqual(client.call_count, 1)

    def test_one_tool_then_an_answer(self):
        client = MockClient(
            [
                tool_call("calculator", {"expression": "(19 * 42) - 8"}),
                text("The answer is 790."),
            ]
        )
        answer = run_agent(client, REGISTRY, TOOLS, "What is (19 * 42) - 8?")
        self.assertEqual(answer, "The answer is 790.")
        self.assertEqual(client.call_count, 2)

    def test_the_assistant_turn_comes_before_the_result(self):
        client = MockClient(
            [tool_call("calculator", {"expression": "2+2"}), text("It is 4.")]
        )
        run_agent(client, REGISTRY, TOOLS, "2+2?")
        self.assertEqual(
            roles(client.requests[1]),
            ["user", "assistant", "tool"],
            "a tool message that answers no assistant request is a 400 from the provider",
        )

    def test_the_result_carries_the_id_of_the_call_it_answers(self):
        client = MockClient(
            [tool_call("calculator", {"expression": "2+2"}), text("It is 4.")]
        )
        run_agent(client, REGISTRY, TOOLS, "2+2?")
        sent = client.requests[1]["messages"]
        self.assertEqual(sent[2]["tool_call_id"], sent[1]["tool_calls"][0]["id"])

    def test_the_result_content_is_the_serialized_tool_output(self):
        client = MockClient(
            [tool_call("lookup_population", {"city": "Paris"}), text("About 2.1 million.")]
        )
        run_agent(client, REGISTRY, TOOLS, "Population of Paris?")
        content = client.requests[1]["messages"][2]["content"]
        self.assertEqual(json.loads(content)["population"], 2_102_650)

    def test_a_second_tool_call_reads_the_first_result(self):
        client = MockClient(
            [
                tool_call("lookup_population", {"city": "Paris"}),
                tool_call("lookup_population", {"city": "Tokyo"}),
                text("Tokyo is much larger."),
            ]
        )
        answer = run_agent(client, REGISTRY, TOOLS, "Compare Paris and Tokyo")
        self.assertEqual(answer, "Tokyo is much larger.")
        self.assertEqual(client.call_count, 3)
        self.assertEqual(
            roles(client.requests[2]), ["user", "assistant", "tool", "assistant", "tool"]
        )

    def test_every_call_in_one_turn_gets_a_result(self):
        client = MockClient(
            [
                tool_calls(
                    [
                        ("lookup_population", {"city": "Paris"}),
                        ("lookup_population", {"city": "Tokyo"}),
                    ]
                ),
                text("Tokyo is larger."),
            ]
        )
        run_agent(client, REGISTRY, TOOLS, "Which is bigger?")
        sent = client.requests[1]["messages"]
        requested = [call["id"] for call in sent[1]["tool_calls"]]
        answered = [m["tool_call_id"] for m in sent if m["role"] == "tool"]
        self.assertEqual(requested, answered, "every call in a turn must be answered")

    def test_the_tools_go_out_on_every_call(self):
        client = MockClient([tool_call("calculator", {"expression": "1+1"}), text("2.")])
        run_agent(client, REGISTRY, TOOLS, "1+1?")
        for request in client.requests:
            self.assertEqual(
                request["tools"], TOOLS, "the API is stateless: it forgets your tools too"
            )

    def test_every_step_resends_the_whole_conversation(self):
        client = MockClient([tool_call("calculator", {"expression": "1+1"}), text("2.")])
        run_agent(client, REGISTRY, TOOLS, "1+1?")
        first = client.requests[0]["messages"]
        second = client.requests[1]["messages"]
        self.assertEqual(
            second[: len(first)],
            first,
            "the second call resends the first call's messages and appends to them",
        )
        self.assertGreater(len(second), len(first))


class TestStopping(unittest.TestCase):
    def _looping_client(self, times: int = 10):
        return MockClient(
            [tool_call("calculator", {"expression": "1+1"})] * times, strict=False
        )

    def test_the_budget_raises(self):
        with self.assertRaises(MaxStepsExceeded):
            run_agent(self._looping_client(), REGISTRY, TOOLS, "loop", max_steps=3)

    def test_the_budget_counts_model_calls(self):
        client = self._looping_client()
        with self.assertRaises(MaxStepsExceeded):
            run_agent(client, REGISTRY, TOOLS, "loop", max_steps=3)
        self.assertEqual(
            client.call_count, 3, "max_steps is model calls, not tool calls or rounds"
        )

    def test_the_failure_carries_the_transcript(self):
        client = self._looping_client()
        with self.assertRaises(MaxStepsExceeded) as caught:
            run_agent(client, REGISTRY, TOOLS, "loop", max_steps=3)
        self.assertEqual(caught.exception.steps, 3)
        self.assertGreater(
            len(caught.exception.messages),
            1,
            "attach the messages: which tool it kept calling is the only clue",
        )

    def test_a_budget_of_one_allows_exactly_one_call(self):
        client = MockClient([tool_call("calculator", {"expression": "1+1"})])
        with self.assertRaises(MaxStepsExceeded):
            run_agent(client, REGISTRY, TOOLS, "1+1?", max_steps=1)
        self.assertEqual(client.call_count, 1)

    def test_a_budget_below_one_is_a_caller_bug(self):
        with self.assertRaises(ValueError):
            run_agent(MockClient([text("hi")]), REGISTRY, TOOLS, "q", max_steps=0)

    def test_a_truncated_reply_is_not_an_answer(self):
        client = MockClient([truncated("The population of Paris is approximately 2,1")])
        with self.assertRaises(TruncatedAnswer):
            run_agent(client, REGISTRY, TOOLS, "Population of Paris?")

    def test_a_tool_error_ends_the_run_for_now(self):
        client = MockClient([tool_call("teleport", {})])
        with self.assertRaises(ToolError):
            run_agent(client, REGISTRY, TOOLS, "teleport me")


if __name__ == "__main__":
    unittest.main(verbosity=2)
