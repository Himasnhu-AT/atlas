"""
Tests for: typed output and the retry loop.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from mockllm import MockClient, text, tool_call

from solution import (
    OutputValidationFailed,
    RunContext,
    TypedResult,
    ValidationError,
    build_tool_schema,
    json_schema_for,
    run_typed,
    validate_into,
)


@dataclass
class Ticket:
    """The fixture output type. Two required fields, two with defaults."""

    title: str = field(metadata={"description": "One line summary of the problem"})
    severity: int = field(metadata={"description": "1 is lowest, 5 is highest"})
    tags: list[str] = field(default_factory=list, metadata={"description": "Short labels"})
    assignee: str | None = field(default=None, metadata={"description": "Who owns it"})


@dataclass
class Measurement:
    """A second fixture, for the types Ticket does not cover."""

    celsius: float
    verified: bool = False


@dataclass
class Assignment:
    """
    A third fixture, for the case the other two cannot reach.

    Every `X | None` field in Ticket carries a default, so nothing there
    distinguishes "the annotation allows None" from "the field is optional".
    Those are separate questions and this fixture asks the second one on its own.
    """

    owner: str | None
    note: str = ""


@dataclass
class Unmappable:
    lookup: dict


DEPS = {"customers": {"7": {"name": "Ada Lovelace", "plan": "pro"}}}


def lookup_customer(ctx: RunContext, customer_id: str) -> str:
    """Look up a customer by id."""
    row = ctx.deps["customers"].get(customer_id)
    if row is None:
        return f"no customer {customer_id}"
    return f"{row['name']} is on the {row['plan']} plan"


def word_count(sentence: str, unique: bool = False) -> str:
    """Count the words in a sentence."""
    words = sentence.split()
    return str(len(set(words)) if unique else len(words))


GOOD_TICKET = {"title": "Printer on fire", "severity": 4, "tags": ["hardware"]}


class TestJsonSchemaFor(unittest.TestCase):
    def test_matches_the_expected_schema_exactly(self):
        self.assertEqual(
            json_schema_for(Ticket),
            {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "One line summary of the problem",
                    },
                    "severity": {
                        "type": "integer",
                        "description": "1 is lowest, 5 is highest",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Short labels",
                    },
                    "assignee": {"type": "string", "description": "Who owns it"},
                },
                "required": ["title", "severity"],
                "additionalProperties": False,
            },
        )

    def test_required_follows_declaration_order(self):
        self.assertEqual(
            json_schema_for(Ticket)["required"],
            ["title", "severity"],
            "a field with a default or a default_factory is never required",
        )

    def test_an_optional_annotation_without_a_default_is_still_required(self):
        schema = json_schema_for(Assignment)
        self.assertEqual(
            schema["properties"]["owner"],
            {"type": "string"},
            "X | None contributes the schema for X and nothing else",
        )
        self.assertEqual(
            schema["required"],
            ["owner"],
            "requiredness is decided by the default and by nothing else: a field "
            "the model may answer with null is not a field it may leave out",
        )

    def test_floats_and_bools_map_to_number_and_boolean(self):
        schema = json_schema_for(Measurement)
        self.assertEqual(schema["properties"]["celsius"], {"type": "number"})
        self.assertEqual(schema["properties"]["verified"], {"type": "boolean"})
        self.assertEqual(schema["required"], ["celsius"])

    def test_a_field_without_metadata_gets_no_description(self):
        self.assertNotIn("description", json_schema_for(Measurement)["properties"]["celsius"])

    def test_an_unmappable_type_raises(self):
        with self.assertRaises(TypeError):
            json_schema_for(Unmappable)


class TestValidateInto(unittest.TestCase):
    def test_builds_the_object(self):
        ticket = validate_into(Ticket, GOOD_TICKET)
        self.assertEqual(ticket.title, "Printer on fire")
        self.assertEqual(ticket.severity, 4)
        self.assertEqual(ticket.tags, ["hardware"])

    def test_defaults_fill_in_absent_optional_fields(self):
        ticket = validate_into(Ticket, {"title": "Slow login", "severity": 2})
        self.assertEqual(ticket.tags, [])
        self.assertIsNone(ticket.assignee)

    def test_every_problem_is_collected_into_one_message(self):
        with self.assertRaises(ValidationError) as caught:
            validate_into(Ticket, {"severity": "high"})

        problems = caught.exception.problems
        self.assertEqual(
            len(problems),
            2,
            "one round trip per mistake is one round trip too many: report both",
        )
        message = str(caught.exception)
        self.assertIn("title", message)
        self.assertIn("severity", message)

    def test_a_missing_required_field_is_reported_by_name(self):
        with self.assertRaises(ValidationError) as caught:
            validate_into(Ticket, {"severity": 3})
        self.assertIn("title: missing", caught.exception.problems)

    def test_an_unknown_key_is_a_problem(self):
        with self.assertRaises(ValidationError) as caught:
            validate_into(Ticket, dict(GOOD_TICKET, priority="urgent"))
        self.assertIn("priority: unknown field", caught.exception.problems)

    def test_a_bool_is_not_an_int(self):
        with self.assertRaises(ValidationError) as caught:
            validate_into(Ticket, {"title": "x", "severity": True})
        self.assertIn(
            "severity: expected integer, got bool",
            caught.exception.problems,
            "bool subclasses int in Python, so this needs an explicit check",
        )

    def test_an_int_is_acceptable_where_a_float_is_wanted(self):
        measurement = validate_into(Measurement, {"celsius": 21})
        self.assertEqual(measurement.celsius, 21.0)
        self.assertIsInstance(measurement.celsius, float)

    def test_null_is_allowed_for_an_optional_field(self):
        ticket = validate_into(Ticket, dict(GOOD_TICKET, assignee=None))
        self.assertIsNone(ticket.assignee)

    def test_an_optional_annotation_without_a_default_is_reported_missing(self):
        with self.assertRaises(ValidationError) as caught:
            validate_into(Assignment, {})
        self.assertIn(
            "owner: missing",
            caught.exception.problems,
            "the annotation allows None as a value, not the key's absence",
        )

    def test_the_same_field_accepts_an_explicit_null(self):
        assignment = validate_into(Assignment, {"owner": None})
        self.assertIsNone(assignment.owner)

    def test_a_list_with_a_bad_element_is_one_problem(self):
        with self.assertRaises(ValidationError) as caught:
            validate_into(Ticket, dict(GOOD_TICKET, tags=["hardware", 7]))
        self.assertEqual(len(caught.exception.problems), 1)
        self.assertIn("tags", caught.exception.problems[0])


class TestBuildToolSchema(unittest.TestCase):
    def test_types_come_from_the_hints(self):
        schema = build_tool_schema(word_count)["function"]
        self.assertEqual(schema["name"], "word_count")
        self.assertEqual(schema["description"], "Count the words in a sentence.")
        self.assertEqual(
            schema["parameters"]["properties"],
            {"sentence": {"type": "string"}, "unique": {"type": "boolean"}},
        )
        self.assertEqual(schema["parameters"]["required"], ["sentence"])

    def test_the_context_parameter_is_not_advertised(self):
        schema = build_tool_schema(lookup_customer)["function"]
        self.assertEqual(
            schema["parameters"]["properties"],
            {"customer_id": {"type": "string"}},
            "RunContext is the framework's argument; the model must not see it",
        )
        self.assertEqual(schema["parameters"]["required"], ["customer_id"])


class TestRunTyped(unittest.TestCase):
    def test_a_valid_first_payload_returns_the_object(self):
        client = MockClient([tool_call("final_output", GOOD_TICKET)])

        result = run_typed(client, "Log the printer problem", Ticket)

        self.assertIsInstance(result, TypedResult)
        self.assertIsInstance(result.output, Ticket)
        self.assertEqual(result.output.severity, 4)
        self.assertEqual(result.retries, 0)
        self.assertEqual(client.call_count, 1)

    def test_the_final_output_tool_carries_the_schema(self):
        client = MockClient([tool_call("final_output", GOOD_TICKET)])
        run_typed(client, "Log it", Ticket)

        offered = client.requests[0]["tools"]
        final = offered[-1]["function"]
        self.assertEqual(final["name"], "final_output")
        self.assertEqual(
            final["parameters"],
            json_schema_for(Ticket),
            "structured output is a tool call whose parameters are your schema",
        )

    def test_ordinary_tools_are_offered_alongside_it(self):
        client = MockClient([tool_call("final_output", GOOD_TICKET)])
        run_typed(client, "Log it", Ticket, tools=[word_count])

        offered = [schema["function"]["name"] for schema in client.requests[0]["tools"]]
        self.assertEqual(offered, ["word_count", "final_output"])

    def test_a_bad_payload_is_retried(self):
        client = MockClient(
            [
                tool_call("final_output", {"title": "Printer on fire", "severity": "high"}),
                tool_call("final_output", GOOD_TICKET),
            ]
        )

        result = run_typed(client, "Log it", Ticket)

        self.assertEqual(result.output.severity, 4)
        self.assertEqual(result.retries, 1)
        self.assertEqual(client.call_count, 2)

    def test_the_validation_error_goes_back_to_the_model(self):
        client = MockClient(
            [
                tool_call("final_output", {"title": "Printer on fire", "severity": "high"}),
                tool_call("final_output", GOOD_TICKET),
            ]
        )
        run_typed(client, "Log it", Ticket)

        last = client.requests[1]["messages"][-1]
        self.assertEqual(last["role"], "tool")
        self.assertIn(
            "severity",
            last["content"],
            "the retry only works if the model reads the error; a log line will not do",
        )

    def test_a_context_tool_receives_the_deps(self):
        client = MockClient(
            [
                tool_call("lookup_customer", {"customer_id": "7"}),
                tool_call("final_output", GOOD_TICKET),
            ]
        )

        run_typed(client, "Who is customer 7?", Ticket, tools=[lookup_customer], deps=DEPS)

        results = [
            message["content"]
            for message in client.requests[1]["messages"]
            if message["role"] == "tool"
        ]
        self.assertEqual(results, ["Ada Lovelace is on the pro plan"])

    def test_a_plain_tool_is_called_with_its_arguments_only(self):
        client = MockClient(
            [
                tool_call("word_count", {"sentence": "the printer is on fire"}),
                tool_call("final_output", GOOD_TICKET),
            ]
        )

        run_typed(client, "How long is it?", Ticket, tools=[word_count], deps=DEPS)

        results = [
            message["content"]
            for message in client.requests[1]["messages"]
            if message["role"] == "tool"
        ]
        self.assertEqual(results, ["5"])

    def test_the_retries_run_out(self):
        client = MockClient(
            [
                tool_call("final_output", {"title": "a", "severity": "high"}),
                tool_call("final_output", {"title": "a", "severity": []}),
                tool_call("final_output", {"severity": 2}),
            ]
        )

        with self.assertRaises(OutputValidationFailed) as caught:
            run_typed(client, "Log it", Ticket, max_retries=2)

        self.assertEqual(client.call_count, 3, "max_retries=2 allows three payloads")
        self.assertIn(
            "title",
            caught.exception.last_error,
            "last_error carries the final problem, not a count of attempts",
        )

    def test_prose_instead_of_a_tool_call_fails(self):
        client = MockClient([text("I think the severity is about a four.")])

        with self.assertRaises(OutputValidationFailed):
            run_typed(client, "Log it", Ticket)

    def test_the_history_holds_the_whole_exchange(self):
        client = MockClient(
            [
                tool_call("final_output", {"title": "a", "severity": "high"}),
                tool_call("final_output", GOOD_TICKET),
            ]
        )

        result = run_typed(client, "Log it", Ticket)

        roles = [message["role"] for message in result.messages]
        self.assertEqual(
            roles,
            ["user", "assistant", "tool", "assistant"],
            "the rejected payload and the error stay in the history, which is what "
            "stops the model repeating the mistake",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
