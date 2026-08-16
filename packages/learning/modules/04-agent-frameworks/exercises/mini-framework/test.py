"""
Tests for: a mini framework.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text, tool_call

from solution import (
    Agent,
    MaxStepsExceeded,
    ToolError,
    ToolRegistry,
    ToolSpecError,
    describe,
    parse_docstring,
    tool,
)


# Plain functions. The tests decorate and register them, so a half finished
# solution still gives you per test failures rather than an import error.


def get_weather(city: str, unit: str = "celsius") -> str:
    """
    Get the current weather for a city.

    Args:
        city: City name, for example 'Paris'. Not a postcode
            and not a country.
        unit: celsius or fahrenheit.

    Returns:
        A one line description.
    """
    return f"18 degrees {unit} in {city}"


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def tag_all(labels: list[str]) -> str:
    """Apply several labels at once."""
    return ",".join(labels)


def flaky() -> str:
    """A tool that always fails in a recoverable way."""
    raise ToolError("the billing service is having a moment")


def undocumented(city: str) -> str:
    return "nothing to see"


def unannotated(city) -> str:
    """Look something up."""
    return "?"


def optional_union(city: str | None) -> str:
    """Look something up, maybe."""
    return "?"


def variadic(*names) -> str:
    """Take any number of names."""
    return "?"


class TestDocstringParsing(unittest.TestCase):
    def test_summary_is_the_first_line(self):
        summary, _ = parse_docstring(get_weather.__doc__)
        self.assertEqual(summary, "Get the current weather for a city.")

    def test_reads_the_args_section(self):
        _, params = parse_docstring(get_weather.__doc__)
        self.assertEqual(
            params.get("unit"), "celsius or fahrenheit.", "each Args: line is one parameter"
        )

    def test_joins_continuation_lines(self):
        _, params = parse_docstring(get_weather.__doc__)
        self.assertEqual(
            params.get("city"),
            "City name, for example 'Paris'. Not a postcode and not a country.",
            "a line indented past the parameter lines continues the description",
        )

    def test_stops_at_the_next_section(self):
        _, params = parse_docstring(get_weather.__doc__)
        self.assertNotIn(
            "Returns", params, "a header at column zero ends the Args: section"
        )

    def test_empty_docstring(self):
        self.assertEqual(parse_docstring(None), ("", {}))
        self.assertEqual(parse_docstring("   "), ("", {}))


class TestDescribe(unittest.TestCase):
    def test_name_and_description(self):
        schema = describe(add)
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "add")
        self.assertEqual(schema["function"]["description"], "Add two integers.")

    def test_types_come_from_annotations(self):
        properties = describe(add)["function"]["parameters"]["properties"]
        self.assertEqual(properties["a"]["type"], "integer")

    def test_generics_unwrap_to_their_origin(self):
        properties = describe(tag_all)["function"]["parameters"]["properties"]
        self.assertEqual(
            properties["labels"]["type"], "array", "list[str] is an array, not a string"
        )

    def test_required_excludes_defaults(self):
        parameters = describe(get_weather)["function"]["parameters"]
        self.assertEqual(parameters["required"], ["city"], "unit has a default")

    def test_parameter_descriptions_come_from_the_docstring(self):
        properties = describe(get_weather)["function"]["parameters"]["properties"]
        self.assertEqual(properties["unit"]["description"], "celsius or fahrenheit.")

    def test_no_parameters(self):
        parameters = describe(flaky)["function"]["parameters"]
        self.assertEqual(parameters["properties"], {})
        self.assertEqual(parameters["required"], [])

    def test_refuses_a_missing_description(self):
        with self.assertRaises(ToolSpecError):
            describe(undocumented)

    def test_refuses_an_unannotated_parameter(self):
        with self.assertRaises(ToolSpecError) as caught:
            describe(unannotated)
        self.assertIn("city", str(caught.exception), "the error should name the parameter")

    def test_refuses_a_union(self):
        with self.assertRaises(ToolSpecError):
            describe(optional_union)

    def test_refuses_a_variadic_parameter(self):
        with self.assertRaises(ToolSpecError):
            describe(variadic)


class TestRegistry(unittest.TestCase):
    def test_tool_returns_the_same_function(self):
        decorated = tool(add)
        self.assertIs(decorated, add, "@tool attaches a schema, it does not wrap")
        self.assertEqual(add(2, 3), 5)
        self.assertTrue(add.is_tool)

    def test_add_works_as_a_decorator(self):
        registry = ToolRegistry()

        @registry.add
        def echo(message: str) -> str:
            """Repeat the message back."""
            return message

        self.assertEqual(echo("hi"), "hi", "add() must return the function it was given")
        self.assertEqual(registry.names, ["echo"])

    def test_keeps_registration_order(self):
        registry = ToolRegistry([get_weather, add])
        self.assertEqual(registry.names, ["get_weather", "add"])
        self.assertEqual(
            [s["function"]["name"] for s in registry.schemas], ["get_weather", "add"]
        )

    def test_rejects_a_duplicate_name(self):
        registry = ToolRegistry([add])
        with self.assertRaises(ToolSpecError):
            registry.add(add)

    def test_invoke_runs_the_tool(self):
        record = ToolRegistry([add]).invoke("add", '{"a": 2, "b": 3}')
        self.assertEqual(record.result, "5", "the result is stringified for the model")
        self.assertFalse(record.failed)
        self.assertEqual(record.arguments, {"a": 2, "b": 3})

    def test_invoke_reports_an_unknown_tool(self):
        record = ToolRegistry([add]).invoke("teleport", "{}")
        self.assertTrue(record.failed)
        self.assertTrue(
            record.result.startswith("error:"),
            "the model reads this string, so it has to say what went wrong",
        )

    def test_invoke_survives_malformed_json(self):
        record = ToolRegistry([add]).invoke("add", "{a: 2,")
        self.assertTrue(record.failed)
        self.assertEqual(record.arguments, {})

    def test_invoke_rejects_non_object_arguments(self):
        record = ToolRegistry([add]).invoke("add", "[1, 2]")
        self.assertTrue(record.failed, "a JSON array is valid JSON and still unusable")

    def test_invoke_turns_a_tool_error_into_a_result(self):
        record = ToolRegistry([flaky]).invoke("flaky", "{}")
        self.assertTrue(record.failed)
        self.assertIn("billing service", record.result)

    def test_invoke_reports_wrong_arguments(self):
        record = ToolRegistry([add]).invoke("add", '{"a": 2}')
        self.assertTrue(record.failed, "a missing argument must not raise out of invoke")


class TestAgentRun(unittest.TestCase):
    def registry(self) -> ToolRegistry:
        return ToolRegistry([get_weather, add, flaky])

    def test_direct_answer(self):
        result = Agent(MockClient([text("Paris.")])).run("Capital of France?")
        self.assertEqual(result.answer, "Paris.")
        self.assertEqual(result.steps, 1)
        self.assertEqual(result.tool_calls, [])

    def test_uses_a_tool_then_answers(self):
        client = MockClient(
            [tool_call("get_weather", {"city": "Paris"}), text("It is 18 degrees.")]
        )
        result = Agent(client, self.registry()).run("Weather in Paris?")
        self.assertEqual(result.answer, "It is 18 degrees.")
        self.assertEqual(result.steps, 2, "steps counts model calls, not tool calls")
        self.assertEqual(result.tool_calls[0].name, "get_weather")
        self.assertGreater(result.tokens_used, 0)

    def test_sends_the_system_prompt_and_the_schemas(self):
        client = MockClient([text("ok")])
        agent = Agent(client, self.registry(), system="You are terse.")
        agent.run("hi")
        sent = client.requests[0]
        self.assertEqual(sent["messages"][0], {"role": "system", "content": "You are terse."})
        self.assertEqual(sent["tools"], agent.registry.schemas)

    def test_no_system_message_when_there_is_no_prompt(self):
        client = MockClient([text("ok")])
        Agent(client).run("hi")
        self.assertEqual(client.requests[0]["messages"][0]["role"], "user")

    def test_tool_results_answer_the_assistant_turn(self):
        client = MockClient([tool_call("add", {"a": 1, "b": 2}), text("3")])
        Agent(client, self.registry()).run("1+2?")
        second = client.requests[1]["messages"]
        self.assertEqual(second[-2]["role"], "assistant", "the request is recorded first")
        self.assertEqual(second[-1]["role"], "tool", "then the result that answers it")
        self.assertIn("tool_call_id", second[-1])

    def test_a_failing_tool_does_not_end_the_run(self):
        client = MockClient([tool_call("flaky", {}), text("that did not work")])
        result = Agent(client, self.registry()).run("try it")
        self.assertEqual(result.answer, "that did not work")
        self.assertTrue(result.tool_calls[0].failed)

    def test_enforces_the_budget(self):
        client = MockClient([tool_call("add", {"a": 1, "b": 1})] * 10, strict=False)
        with self.assertRaises(MaxStepsExceeded):
            Agent(client, self.registry(), max_steps=3).run("loop")
        self.assertEqual(client.call_count, 3, "the budget bounds model calls")

    def test_rejects_a_nonsense_budget(self):
        with self.assertRaises(ValueError):
            Agent(MockClient([text("hi")]), max_steps=0)

    def test_runs_do_not_share_state(self):
        client = MockClient(
            [
                tool_call("add", {"a": 1, "b": 1}),
                text("2"),
                tool_call("add", {"a": 2, "b": 2}),
                text("4"),
            ]
        )
        agent = Agent(client, self.registry(), system="S")
        first = agent.run("1+1?")
        second = agent.run("2+2?")

        self.assertEqual(len(first.tool_calls), 1)
        self.assertEqual(len(second.tool_calls), 1, "records must not accumulate across runs")

        opening = client.requests[2]["messages"]
        self.assertEqual(
            len(opening),
            2,
            "the second run starts fresh: the system message and its own question",
        )
        self.assertEqual(opening[1]["content"], "2+2?")

    def test_two_agents_share_one_registry(self):
        registry = self.registry()
        terse = Agent(MockClient([text("18.")]), registry, system="Answer in one word.")
        chatty = Agent(MockClient([text("It is 18 degrees today.")]), registry, system="Chat.")

        self.assertEqual(terse.run("weather?").answer, "18.")
        self.assertEqual(chatty.run("weather?").answer, "It is 18 degrees today.")
        self.assertEqual(
            terse.registry.names,
            chatty.registry.names,
            "one registry, two prompts, no copied loop",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
