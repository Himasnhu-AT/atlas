"""
Tests for: when tools fail.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import APIError, MockClient, error, text, tool_call

from solution import (
    AgentRun,
    call_signature,
    call_with_retry,
    lookup_population,
    run_resilient_agent,
    safe_dispatch,
)

REGISTRY = {"lookup_population": lookup_population}
TOOLS = [{"type": "function", "function": {"name": "lookup_population"}}]


class Recorder:
    """A stand in for time.sleep that records what it was asked to wait."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def tool_contents(request: dict) -> list[str]:
    return [m["content"] for m in request["messages"] if m["role"] == "tool"]


class TestCallSignature(unittest.TestCase):
    def test_key_order_does_not_make_a_new_call(self):
        self.assertEqual(
            call_signature("f", '{"x": 1, "y": 2}'),
            call_signature("f", '{"y": 2, "x": 1}'),
            "canonicalize the arguments or a reordered repeat looks like progress",
        )

    def test_different_arguments_are_different_calls(self):
        self.assertNotEqual(call_signature("f", '{"x": 1}'), call_signature("f", '{"x": 2}'))

    def test_different_tools_are_different_calls(self):
        self.assertNotEqual(call_signature("f", "{}"), call_signature("g", "{}"))

    def test_the_name_is_in_the_signature(self):
        self.assertIn("lookup_population", call_signature("lookup_population", "{}"))

    def test_unparseable_arguments_still_produce_a_stable_signature(self):
        self.assertEqual(call_signature("f", "{broken"), call_signature("f", "{broken"))


class TestSafeDispatch(unittest.TestCase):
    def test_a_working_call(self):
        content, ok = safe_dispatch(REGISTRY, "lookup_population", '{"city": "Paris"}')
        self.assertTrue(ok)
        self.assertIn("2102650", content.replace(",", ""))

    def test_an_unknown_tool_says_what_exists(self):
        content, ok = safe_dispatch(REGISTRY, "lookup_pop", "{}")
        self.assertFalse(ok)
        self.assertTrue(
            content.startswith("error:"),
            f"a recoverable failure comes back as an observation starting "
            f"'error: ', not as an exception. Got: {content!r}",
        )
        self.assertIn(
            "lookup_population",
            content,
            "naming the real tool is what gets the next call right",
        )

    def test_unparseable_arguments(self):
        content, ok = safe_dispatch(REGISTRY, "lookup_population", "{city: Paris")
        self.assertFalse(ok)
        self.assertTrue(
            content.startswith("error:"),
            f"unparseable arguments are an observation, not a crash. Got: {content!r}",
        )

    def test_arguments_that_are_not_an_object(self):
        content, ok = safe_dispatch(REGISTRY, "lookup_population", '"Paris"')
        self.assertFalse(ok)

    def test_a_tool_that_raises(self):
        content, ok = safe_dispatch(REGISTRY, "lookup_population", '{"city": "Atlantis"}')
        self.assertFalse(ok)
        self.assertIn(
            "LookupError",
            content,
            "the exception type separates 'try a different city' from 'the tool is down'",
        )
        self.assertIn("paris", content, "the tool's own hint has to survive")

    def test_the_wrong_argument_names(self):
        content, ok = safe_dispatch(REGISTRY, "lookup_population", '{"town": "Paris"}')
        self.assertFalse(ok)
        self.assertIn(
            "town",
            content,
            "name the argument the function would not accept, or the model has "
            "nothing to correct",
        )

    def test_nothing_escapes(self):
        for arguments in ("{broken", '{"city": "Atlantis"}', '{"town": "Paris"}', "[]"):
            content, ok = safe_dispatch(REGISTRY, "lookup_population", arguments)
            self.assertFalse(ok)
            self.assertIsInstance(content, str)


class TestCallWithRetry(unittest.TestCase):
    def test_a_call_that_works_does_not_sleep(self):
        client = MockClient([text("hello")])
        sleep = Recorder()
        response = call_with_retry(client, [], TOOLS, sleep=sleep)
        self.assertEqual(response.choices[0].message.content, "hello")
        self.assertEqual(sleep.delays, [])

    def test_a_transient_failure_is_retried(self):
        client = MockClient([error("service unavailable", 503), text("hello")])
        sleep = Recorder()
        response = call_with_retry(client, [], TOOLS, sleep=sleep)
        self.assertEqual(response.choices[0].message.content, "hello")
        self.assertEqual(client.call_count, 2)

    def test_the_backoff_doubles(self):
        client = MockClient([error(status_code=503), error(status_code=503), text("hi")])
        sleep = Recorder()
        call_with_retry(client, [], TOOLS, attempts=3, base_delay=0.5, sleep=sleep)
        self.assertEqual(
            sleep.delays,
            [0.5, 1.0],
            "wait after a failure, not after the last one, and double each time",
        )

    def test_the_last_error_is_re_raised(self):
        client = MockClient([error(status_code=503)] * 5, strict=False)
        sleep = Recorder()
        with self.assertRaises(APIError):
            call_with_retry(client, [], TOOLS, attempts=3, sleep=sleep)
        self.assertEqual(client.call_count, 3, "attempts is total tries, not extra tries")

    def test_a_client_error_is_not_retried(self):
        client = MockClient([error("bad request", 400)] * 3, strict=False)
        sleep = Recorder()
        with self.assertRaises(APIError):
            call_with_retry(client, [], TOOLS, attempts=3, sleep=sleep)
        self.assertEqual(
            client.call_count, 1, "a 400 fails the same way three times in a row"
        )
        self.assertEqual(sleep.delays, [])

    def test_one_attempt_means_no_retry(self):
        client = MockClient([error(status_code=503), text("hi")])
        with self.assertRaises(APIError):
            call_with_retry(client, [], TOOLS, attempts=1, sleep=Recorder())

    def test_a_nonsense_attempt_count(self):
        with self.assertRaises(ValueError):
            call_with_retry(MockClient([text("hi")]), [], TOOLS, attempts=0)


class TestRecovery(unittest.TestCase):
    def test_a_failing_tool_does_not_end_the_run(self):
        client = MockClient(
            [
                tool_call("lookup_population", {"city": "Atlantis"}),
                text("I have no figure for Atlantis."),
            ]
        )
        run = run_resilient_agent(client, REGISTRY, TOOLS, "Population of Atlantis?")
        self.assertIsInstance(run, AgentRun)
        self.assertTrue(run.ok)
        self.assertEqual(run.reason, "answered")
        self.assertEqual(run.answer, "I have no figure for Atlantis.")

    def test_the_error_reaches_the_model_as_a_tool_message(self):
        client = MockClient(
            [tool_call("lookup_population", {"city": "Atlantis"}), text("No data.")]
        )
        run_resilient_agent(client, REGISTRY, TOOLS, "q")
        contents = tool_contents(client.requests[1])
        self.assertEqual(len(contents), 1)
        self.assertTrue(
            contents[0].startswith("error:"),
            f"the failure reaches the model as a tool message. Got: {contents[0]!r}",
        )
        self.assertIn(
            "Atlantis",
            contents[0],
            "carrying the tool's own message, which is what lets the model pick a "
            f"different city next turn. Got: {contents[0]!r}",
        )

    def test_the_failed_result_still_carries_its_call_id(self):
        client = MockClient(
            [tool_call("lookup_population", {"city": "Atlantis"}), text("No data.")]
        )
        run_resilient_agent(client, REGISTRY, TOOLS, "q")
        sent = client.requests[1]["messages"]
        self.assertEqual(sent[2]["tool_call_id"], sent[1]["tool_calls"][0]["id"])

    def test_an_unknown_tool_is_recoverable(self):
        client = MockClient([tool_call("teleport", {}), text("I cannot do that.")])
        run = run_resilient_agent(client, REGISTRY, TOOLS, "teleport me")
        self.assertTrue(run.ok)

    def test_the_model_corrects_itself_from_the_observation(self):
        client = MockClient(
            [
                tool_call("lookup_population", {"city": "Atlantis"}),
                tool_call("lookup_population", {"city": "Paris"}),
                text("Paris has about 2.1 million people."),
            ]
        )
        run = run_resilient_agent(client, REGISTRY, TOOLS, "pick a real city")
        self.assertTrue(run.ok)
        self.assertEqual(run.steps, 3)


class TestGivingUp(unittest.TestCase):
    def test_the_same_failing_call_ends_the_run(self):
        client = MockClient(
            [tool_call("lookup_population", {"city": "Atlantis"})] * 8, strict=False
        )
        run = run_resilient_agent(
            client, REGISTRY, TOOLS, "q", max_steps=8, repeat_limit=3
        )
        self.assertFalse(run.ok)
        self.assertEqual(run.reason, "repeated_failure")
        self.assertEqual(
            client.call_count,
            3,
            "stop at the third identical failure, not at the end of the budget",
        )

    def test_different_arguments_are_not_repeats(self):
        client = MockClient(
            [
                tool_call("lookup_population", {"city": "Atlantis"}),
                tool_call("lookup_population", {"city": "Shangri-La"}),
                tool_call("lookup_population", {"city": "El Dorado"}),
                text("None of those are real places."),
            ]
        )
        run = run_resilient_agent(client, REGISTRY, TOOLS, "q", repeat_limit=3)
        self.assertTrue(run.ok, "three different calls are three attempts, not a loop")

    def test_a_spent_budget_is_reported_not_raised(self):
        client = MockClient(
            [tool_call("lookup_population", {"city": "Paris"})] * 8, strict=False
        )
        run = run_resilient_agent(client, REGISTRY, TOOLS, "q", max_steps=3)
        self.assertFalse(run.ok)
        self.assertEqual(run.reason, "max_steps")
        self.assertEqual(run.steps, 3)
        self.assertEqual(run.answer, "")

    def test_the_transcript_comes_back_either_way(self):
        client = MockClient(
            [tool_call("lookup_population", {"city": "Paris"})] * 8, strict=False
        )
        run = run_resilient_agent(client, REGISTRY, TOOLS, "q", max_steps=2)
        self.assertEqual(run.messages[0], {"role": "user", "content": "q"})
        self.assertGreater(len(run.messages), 1, "a failed run still owes you its history")

    def test_a_provider_outage_is_retried_then_answered(self):
        client = MockClient([error(status_code=503), text("Paris, about 2.1 million.")])
        sleep = Recorder()
        run = run_resilient_agent(client, REGISTRY, TOOLS, "q", sleep=sleep)
        self.assertTrue(run.ok)
        self.assertEqual(run.steps, 1, "retries inside one step are not steps")

    def test_a_provider_outage_that_does_not_clear_ends_the_run(self):
        client = MockClient([error(status_code=503)] * 6, strict=False)
        run = run_resilient_agent(
            client, REGISTRY, TOOLS, "q", attempts=2, sleep=Recorder()
        )
        self.assertFalse(run.ok)
        self.assertEqual(run.reason, "provider_error")
        self.assertEqual(
            client.call_count, 2, "the run stops after one step's attempts are gone"
        )

    def test_a_nonsense_repeat_limit(self):
        with self.assertRaises(ValueError):
            run_resilient_agent(
                MockClient([text("hi")]), REGISTRY, TOOLS, "q", repeat_limit=0
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
