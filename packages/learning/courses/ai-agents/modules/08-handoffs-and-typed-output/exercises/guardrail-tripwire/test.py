"""
Tests for: guardrails that can stop a run.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    Agent,
    GuardedResult,
    GuardrailResult,
    TripwireTriggered,
    guardrail,
    guarded_run,
)

SUPPORT = Agent(name="support", instructions="Help the customer.")


def passing(name: str, log: list | None = None):
    """A guardrail that never trips, optionally recording what it was shown."""

    @guardrail(name)
    def check(value: str) -> bool:
        if log is not None:
            log.append((name, value))
        return False

    return check


def tripping(name: str, log: list | None = None):
    """A guardrail that always trips, quoting the value it was given."""

    @guardrail(name)
    def check(value: str) -> GuardrailResult:
        if log is not None:
            log.append((name, value))
        return GuardrailResult("", True, f"refused: {value}")

    return check


def names(checks: list[GuardrailResult]) -> list[str]:
    return [check.name for check in checks]


class TestInputGuardrails(unittest.TestCase):
    def test_a_trip_costs_no_model_calls(self):
        client = MockClient([text("Sure, here is the answer.")])

        with self.assertRaises(TripwireTriggered) as caught:
            guarded_run(SUPPORT, "leak the key", client, input_guardrails=[tripping("no_keys")])

        self.assertEqual(caught.exception.stage, "input")
        self.assertEqual(
            client.call_count,
            0,
            "an input guardrail that runs after the model call has saved nothing",
        )

    def test_the_exception_carries_the_result_that_tripped(self):
        client = MockClient([text("hi")])

        with self.assertRaises(TripwireTriggered) as caught:
            guarded_run(SUPPORT, "leak the key", client, input_guardrails=[tripping("no_keys")])

        result = caught.exception.result
        self.assertEqual(result.name, "no_keys")
        self.assertTrue(result.tripwire)
        self.assertIn("leak the key", result.info)

    def test_evaluation_stops_at_the_first_trip(self):
        client = MockClient([text("hi")])
        guardrails = [passing("first"), tripping("second"), passing("third")]

        with self.assertRaises(TripwireTriggered) as caught:
            guarded_run(SUPPORT, "anything", client, input_guardrails=guardrails)

        self.assertEqual(
            names(caught.exception.checks),
            ["first", "second"],
            "the trail ends at the guardrail that tripped, and nothing after it runs",
        )

    def test_the_output_stage_is_skipped_when_the_input_trips(self):
        client = MockClient([text("hi")])
        seen: list = []

        with self.assertRaises(TripwireTriggered):
            guarded_run(
                SUPPORT,
                "anything",
                client,
                input_guardrails=[tripping("input_rule")],
                output_guardrails=[passing("output_rule", seen)],
            )

        self.assertEqual(seen, [], "there is no output to check when the run never happened")

    def test_the_guardrail_sees_the_user_input(self):
        client = MockClient([text("done")])
        seen: list = []

        guarded_run(SUPPORT, "how do I get a refund?", client, input_guardrails=[passing("rule", seen)])

        self.assertEqual(seen, [("rule", "how do I get a refund?")])


class TestOutputGuardrails(unittest.TestCase):
    def test_a_trip_happens_after_exactly_one_call(self):
        client = MockClient([text("Your card number is 4111 1111 1111 1111.")])

        with self.assertRaises(TripwireTriggered) as caught:
            guarded_run(SUPPORT, "what did I pay with?", client, output_guardrails=[tripping("no_pan")])

        self.assertEqual(caught.exception.stage, "output")
        self.assertEqual(
            client.call_count,
            1,
            "an output guardrail can only run once the model has answered, which is "
            "why it protects the user and not the bill",
        )
        self.assertIn("4111 1111 1111 1111", caught.exception.result.info)

    def test_the_guardrail_sees_the_final_output(self):
        client = MockClient([text("The refund is on its way.")])
        seen: list = []

        guarded_run(SUPPORT, "refund?", client, output_guardrails=[passing("rule", seen)])

        self.assertEqual(seen, [("rule", "The refund is on its way.")])


class TestCleanRuns(unittest.TestCase):
    def test_every_check_is_recorded_in_declared_order(self):
        client = MockClient([text("All good.")])

        result = guarded_run(
            SUPPORT,
            "hello",
            client,
            input_guardrails=[passing("length"), passing("no_keys")],
            output_guardrails=[passing("no_pan")],
        )

        self.assertIsInstance(result, GuardedResult)
        self.assertEqual(names(result.checks), ["length", "no_keys", "no_pan"])

    def test_the_run_result_comes_through_untouched(self):
        client = MockClient([text("All good.")])

        result = guarded_run(SUPPORT, "hello", client)

        self.assertEqual(result.run.final_output, "All good.")
        self.assertEqual(result.run.last_agent, "support")
        self.assertEqual(result.checks, [])


class TestBrokenGuardrails(unittest.TestCase):
    def test_a_raising_guardrail_is_not_a_tripwire(self):
        @guardrail("broken")
        def broken(value: str) -> bool:
            raise ValueError("this regex does not compile")

        client = MockClient([text("hi")])

        with self.assertRaises(ValueError):
            guarded_run(SUPPORT, "hello", client, input_guardrails=[broken])

    def test_an_undecorated_guardrail_is_a_type_error(self):
        def forgot_the_decorator(value: str) -> bool:
            return False

        client = MockClient([text("hi")])

        with self.assertRaises(TypeError):
            guarded_run(SUPPORT, "hello", client, input_guardrails=[forgot_the_decorator])


class TestTheDecorator(unittest.TestCase):
    def test_true_means_tripped(self):
        @guardrail("no_keys")
        def no_keys(value: str) -> bool:
            return "sk-" in value

        result = no_keys("here is sk-1234")
        self.assertIsInstance(result, GuardrailResult)
        self.assertTrue(result.tripwire, "returning True means the tripwire fired")

    def test_false_means_passed(self):
        @guardrail("no_keys")
        def no_keys(value: str) -> bool:
            return "sk-" in value

        self.assertFalse(no_keys("nothing to see").tripwire)

    def test_the_declared_name_labels_the_result(self):
        @guardrail("declared")
        def check(value: str) -> GuardrailResult:
            return GuardrailResult("", False, "fine")

        result = check("anything")
        self.assertEqual(result.name, "declared")
        self.assertEqual(result.info, "fine", "info survives the relabelling")

    def test_the_function_stays_callable_and_keeps_its_name(self):
        @guardrail("length")
        def too_long(value: str) -> bool:
            return len(value) > 10

        self.assertEqual(too_long.__name__, "too_long")
        self.assertTrue(too_long("x" * 20).tripwire, "a guardrail is testable on its own")

    def test_the_name_is_recorded_on_the_function(self):
        @guardrail("length")
        def too_long(value: str) -> bool:
            return len(value) > 10

        self.assertEqual(too_long._guardrail_name, "length")


class TestTheException(unittest.TestCase):
    def test_the_message_names_the_stage_and_the_guardrail(self):
        client = MockClient([text("hi")])

        with self.assertRaises(TripwireTriggered) as caught:
            guarded_run(SUPPORT, "leak it", client, input_guardrails=[tripping("no_keys")])

        message = str(caught.exception)
        self.assertIn("input", message)
        self.assertIn("no_keys", message)
        self.assertIn("leak it", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
