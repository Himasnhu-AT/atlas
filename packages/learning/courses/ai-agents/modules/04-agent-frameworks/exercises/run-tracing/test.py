"""
Tests for: hooks and a trace.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import APIError, MockClient, error, text, tool_call, tool_calls

from solution import (
    REDACTED,
    Hook,
    MaxStepsExceeded,
    StepRecord,
    Toolbox,
    TracedAgent,
    Tracer,
    redact,
    summarise,
)


class FakeClock:
    """
    Deterministic seconds. Hands out each reading in turn, then repeats the
    last one forever, and counts how many times it was asked.
    """

    def __init__(self, *readings: float) -> None:
        self.readings = list(readings) or [0.0]
        self.calls = 0

    def __call__(self) -> float:
        value = self.readings[min(self.calls, len(self.readings) - 1)]
        self.calls += 1
        return value


class RecordingHook(Hook):
    """A hook that writes down what it was told, and when."""

    def __init__(self, label: str = "h", events: list | None = None) -> None:
        self.label = label
        self.events = events if events is not None else []

    def before_model(self, index, messages):
        self.events.append((self.label, "before_model", index))

    def after_model(self, index, response):
        self.events.append((self.label, "after_model", index))

    def before_tool(self, index, name, arguments):
        self.events.append((self.label, "before_tool", name))

    def after_tool(self, index, name, result, failed):
        self.events.append((self.label, "after_tool", name))

    def on_error(self, index, error):
        self.events.append((self.label, "on_error", index))


class BrokenHook(Hook):
    """The hook somebody wrote at five to six on a Friday."""

    def after_model(self, index, response):
        raise RuntimeError("this counter has a bug in it")


def ping() -> str:
    """Answer with pong."""
    return "pong"


def toolbox() -> Toolbox:
    return Toolbox([ping])


def a_record(**overrides) -> StepRecord:
    values = {"index": 1, "prompt_tokens": 10, "completion_tokens": 4, "elapsed_ms": 30}
    values.update(overrides)
    return StepRecord(**values)


class TestSummarise(unittest.TestCase):
    def test_an_empty_run(self):
        self.assertEqual(
            summarise([]),
            {
                "steps": 0,
                "failed_steps": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "elapsed_ms": 0,
                "tool_calls": {},
            },
            "summarise must be safe to call from an exception handler",
        )

    def test_totals(self):
        result = summarise([a_record(), a_record(index=2, prompt_tokens=20)])
        self.assertEqual(result["steps"], 2)
        self.assertEqual(result["prompt_tokens"], 30)
        self.assertEqual(result["total_tokens"], 38)
        self.assertEqual(result["elapsed_ms"], 60)

    def test_counts_every_call_to_a_tool(self):
        records = [
            a_record(tool_calls=["ping", "ping"]),
            a_record(index=2, tool_calls=["lookup"]),
        ]
        self.assertEqual(
            summarise(records)["tool_calls"],
            {"lookup": 1, "ping": 2},
            "two calls to one tool is the signal that something is looping",
        )

    def test_counts_failed_steps(self):
        records = [a_record(), a_record(index=2, error="boom")]
        self.assertEqual(summarise(records)["failed_steps"], 1)


class TestRedact(unittest.TestCase):
    def record(self) -> StepRecord:
        return a_record(
            messages=[
                {"role": "user", "content": "my card is 4111 1111 1111 1111"},
                {"role": "tool", "tool_call_id": "call_1", "content": "declined"},
            ],
            response_text="I can see the card ending 1111.",
            tool_calls=["ping"],
        )

    def test_blanks_the_named_message_key(self):
        redacted = redact(self.record(), ["content"])
        self.assertEqual([m["content"] for m in redacted.messages], [REDACTED, REDACTED])

    def test_keeps_the_structure_readable(self):
        redacted = redact(self.record(), ["content"])
        self.assertEqual(redacted.messages[0]["role"], "user", "roles are not the secret")
        self.assertEqual(redacted.messages[1]["tool_call_id"], "call_1")

    def test_blanks_a_text_attribute(self):
        self.assertEqual(redact(self.record(), ["response_text"]).response_text, REDACTED)

    def test_does_not_touch_the_original(self):
        original = self.record()
        redact(original, ["content", "response_text"])
        self.assertEqual(
            original.messages[0]["content"],
            "my card is 4111 1111 1111 1111",
            "redact returns a copy: the agent is still using the messages you were handed",
        )

    def test_the_numbers_survive(self):
        original = self.record()
        redacted = redact(original, ["content", "response_text"])
        self.assertEqual(
            summarise([redacted]),
            summarise([original]),
            "a redacted trace has to add up the same, or it is not worth keeping",
        )


class TestTracer(unittest.TestCase):
    def test_one_record_per_model_call(self):
        tracer = Tracer(clock=FakeClock(0.0))
        client = MockClient([tool_call("ping", {}), text("pong to you too")])
        TracedAgent(client, toolbox(), hooks=[tracer]).run("ping?")

        self.assertEqual([r.index for r in tracer.records], [1, 2], "indexes count from 1")

    def test_records_what_that_step_actually_sent(self):
        tracer = Tracer(clock=FakeClock(0.0))
        client = MockClient([tool_call("ping", {}), text("done")])
        TracedAgent(client, toolbox(), hooks=[tracer]).run("ping?")

        self.assertEqual(
            len(tracer.records[0].messages),
            1,
            "step one sent one message; a record holding the live list would show three",
        )
        self.assertEqual(len(tracer.records[1].messages), 3)

    def test_records_the_response(self):
        tracer = Tracer(clock=FakeClock(0.0))
        TracedAgent(MockClient([text("hello")]), hooks=[tracer]).run("hi")

        record = tracer.records[0]
        self.assertEqual(record.response_text, "hello")
        self.assertEqual(record.finish_reason, "stop")
        self.assertGreater(record.total_tokens, 0)

    def test_records_tool_names_in_order(self):
        tracer = Tracer(clock=FakeClock(0.0))
        client = MockClient([tool_calls([("ping", {}), ("ping", {})]), text("done")])
        TracedAgent(client, toolbox(), hooks=[tracer]).run("twice")

        self.assertEqual(
            tracer.records[0].tool_calls,
            ["ping", "ping"],
            "a set would throw away the repeat, which is the interesting part",
        )
        self.assertEqual(tracer.records[1].tool_calls, [])

    def test_elapsed_comes_from_the_clock(self):
        clock = FakeClock(0.0, 0.25, 1.0, 1.1)
        tracer = Tracer(clock=clock)
        client = MockClient([tool_call("ping", {}), text("done")])
        TracedAgent(client, toolbox(), hooks=[tracer]).run("ping?")

        self.assertEqual([r.elapsed_ms for r in tracer.records], [250, 100])
        self.assertEqual(clock.calls, 4, "two readings per step, and no more")


class TestHookOrder(unittest.TestCase):
    def test_the_five_points_fire_in_order(self):
        hook = RecordingHook()
        client = MockClient([tool_call("ping", {}), text("done")])
        TracedAgent(client, toolbox(), hooks=[hook]).run("ping?")

        self.assertEqual(
            hook.events,
            [
                ("h", "before_model", 1),
                ("h", "after_model", 1),
                ("h", "before_tool", "ping"),
                ("h", "after_tool", "ping"),
                ("h", "before_model", 2),
                ("h", "after_model", 2),
            ],
        )

    def test_hooks_run_in_list_order(self):
        events: list = []
        first = RecordingHook("first", events)
        second = RecordingHook("second", events)
        TracedAgent(MockClient([text("ok")]), hooks=[first, second]).run("hi")

        self.assertEqual([label for label, _, _ in events], ["first", "second"] * 2)

    def test_an_agent_with_no_hooks_still_answers(self):
        self.assertEqual(TracedAgent(MockClient([text("ok")])).run("hi"), "ok")

    def test_a_broken_hook_does_not_break_the_run(self):
        tracer = Tracer(clock=FakeClock(0.0))
        agent = TracedAgent(MockClient([text("ok")]), hooks=[BrokenHook(), tracer])

        self.assertEqual(agent.run("hi"), "ok", "a bug in a counter is not a failed run")
        self.assertEqual(len(tracer.records), 1, "and it must not stop the next hook")

    def test_a_model_error_reaches_on_error_and_still_propagates(self):
        hook = RecordingHook()
        tracer = Tracer(clock=FakeClock(0.0, 0.5))
        agent = TracedAgent(MockClient([error("upstream is down")]), hooks=[hook, tracer])

        with self.assertRaises(APIError):
            agent.run("hi")

        self.assertEqual(
            hook.events,
            [("h", "before_model", 1), ("h", "on_error", 1)],
            "after_model must not fire for a call that raised",
        )
        self.assertEqual(len(tracer.records), 1, "the failed step is the one worth keeping")
        self.assertIn("upstream is down", tracer.records[0].error)
        self.assertEqual(tracer.records[0].elapsed_ms, 500)

    def test_a_spent_budget_marks_the_last_step(self):
        tracer = Tracer(clock=FakeClock(0.0))
        client = MockClient([tool_call("ping", {})] * 5, strict=False)
        agent = TracedAgent(client, toolbox(), max_steps=2, hooks=[tracer])

        with self.assertRaises(MaxStepsExceeded):
            agent.run("loop")

        summary = summarise(tracer.records)
        self.assertEqual(summary["steps"], 2, "one record per model call, not one extra")
        self.assertEqual(summary["failed_steps"], 1)
        self.assertIsNotNone(tracer.records[-1].error)

    def test_rejects_a_nonsense_budget(self):
        with self.assertRaises(ValueError):
            TracedAgent(MockClient([text("hi")]), max_steps=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
