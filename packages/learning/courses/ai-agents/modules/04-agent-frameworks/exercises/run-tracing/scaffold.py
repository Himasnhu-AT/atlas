"""
Hooks and a trace.

The loop from the last exercise, with five places where something else can
listen, and one listener that writes down what happened. Everything a framework
calls observability is built out of these two ideas.

`Hook` and `Toolbox` below are given. You write the tracer that turns hook calls
into records, the two functions that read those records, and the agent that
emits them in the right order, including when the run fails.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import dataclasses
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

#: What a redacted value is replaced with. A constant rather than an empty
#: string, so a reader of the trace can tell "we removed this" apart from "the
#: model said nothing".
REDACTED = "[redacted]"

#: The StepRecord attributes redact() will blank. Everything else on a record
#: is a count, an index or a name, which is why a redacted trace still adds up.
TEXT_FIELDS = frozenset({"response_text", "error"})


class ToolError(Exception):
    """A tool failed in a way the model can recover from."""


class MaxStepsExceeded(Exception):
    """The agent spent its whole step budget without producing an answer."""


@dataclass
class StepRecord:
    """
    One model call and everything that happened because of it.

    One record per step, not one per run and not one per tool call. A run that
    went wrong on step four of six is a question you can only answer from a
    record shaped like this: what step four was sent, what came back, what it
    called, what it cost, and how long it took.

    Attributes:
        index: which step this was, counting from 1.
        messages: a copy of what was sent to the model.
        response_text: the assistant's text, or None when it asked for tools.
        finish_reason: "stop", "tool_calls", "length", and so on.
        tool_calls: the names called during this step, in order. Names repeat
            when the tool was called twice.
        prompt_tokens, completion_tokens: from the response's usage.
        elapsed_ms: how long the step took, in whole milliseconds.
        error: the string form of the exception that ended the run, or None.
    """

    index: int
    messages: list[dict] = field(default_factory=list)
    response_text: str | None = None
    finish_reason: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_ms: int = 0
    error: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class Hook:
    """
    Five places to stand. Given complete, so subclass it and override what you
    care about.

    Five, and not more, because these are the boundaries where the agent stops
    being in control: either it is about to hand work to a model, or it is
    about to hand work to a tool, or something has thrown. Every counter,
    logger, cache, rate limiter and approval gate anyone has wanted so far
    hangs off one of the five.

    The default implementations do nothing. A hook that only wants token counts
    overrides one method and ignores the rest, which is what makes a list of
    hooks composable in a way that subclassing the agent is not.
    """

    def before_model(self, index: int, messages: list[dict]) -> None:
        """About to call the model with `messages`."""

    def after_model(self, index: int, response: Any) -> None:
        """The model returned. Not called when the call raised."""

    def before_tool(self, index: int, name: str, arguments: dict) -> None:
        """About to run a tool the model asked for."""

    def after_tool(self, index: int, name: str, result: str, failed: bool) -> None:
        """A tool returned. `failed` is true for a ToolError or a bad request."""

    def on_error(self, index: int, error: BaseException) -> None:
        """The run is about to end abnormally. The exception still propagates."""


class Toolbox:
    """
    The registry from the previous exercise, trimmed to what this one needs.
    Given complete.

    The schemas here carry a name and a description and no parameters, because
    deriving parameters is the previous exercise and nothing below depends on
    it.
    """

    def __init__(self, tools: list[Callable] | None = None) -> None:
        self._tools: dict[str, Callable] = {fn.__name__: fn for fn in tools or []}

    @property
    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": (fn.__doc__ or "").strip().split("\n")[0],
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
            for name, fn in self._tools.items()
        ]

    @staticmethod
    def decode(arguments_json: str) -> dict:
        """The model's raw argument string as a dict. Never raises: {} on junk."""
        try:
            arguments = json.loads(arguments_json)
        except (json.JSONDecodeError, ValueError):
            return {}
        return arguments if isinstance(arguments, dict) else {}

    def run(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Run one tool. Returns (result, failed). Never raises for bad input."""
        if name not in self._tools:
            return f"error: unknown tool {name!r}", True
        try:
            return str(self._tools[name](**arguments)), False
        except ToolError as error:
            return f"error: {error}", True
        except TypeError as error:
            return f"error: wrong arguments for {name}: {error}", True


def summarise(records: Iterable[StepRecord]) -> dict:
    """
    Roll a run's records up into the numbers somebody will ask you for.

    Returns a dict with exactly these keys:

        steps            how many records there are
        failed_steps     how many carry an error
        prompt_tokens    summed across the records
        completion_tokens
        total_tokens     the sum of the two above
        elapsed_ms       summed across the records
        tool_calls       {tool name: how many times it was called}, with the
                         keys in alphabetical order

    An empty run gives zeros and an empty dict rather than raising. That is
    what makes this safe to call from an exception handler, which is where it
    is most useful.

    This is the cost ledger. Nothing about it is about money, and yet a token
    count per run and a call count per tool is the whole of what a spend
    dashboard needs, which is the argument for getting the record shape right
    once rather than adding a counter every time somebody asks a question.
    """
    raise NotImplementedError


def redact(record: StepRecord, fields: Iterable[str]) -> StepRecord:
    """
    Return a copy of `record` with the named fields blanked to REDACTED.

    A name in `fields` does two things. If it is one of TEXT_FIELDS it blanks
    that attribute of the record. Either way it blanks that key in every
    message: redacting "content" empties the text of every message that was
    sent, without touching the roles or the tool call ids that make the
    sequence readable.

    The copy has to be deep enough to be a copy: a new record, a new list of
    messages, and a new dict for each message. Blanking the caller's dicts in
    place would redact the live conversation the agent is still running.

    What survives is the point. Indexes, token counts, elapsed times, finish
    reasons and tool names are all still there, so summarise() returns exactly
    the same numbers for a redacted trace as for the original. That is what
    lets you keep ninety days of traces without keeping ninety days of somebody
    else's personal data, and it is a much easier conversation to have with a
    security reviewer than "we turn tracing off in production".
    """
    raise NotImplementedError


class Tracer(Hook):
    """
    The hook that writes the trace. One StepRecord per model call.

    Tracing is not a special case inside the agent, it is the first hook
    anybody writes. If the agent had to know about the tracer, the second thing
    that wanted to watch a run would need the agent changed again.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        """
        Build a tracer.

        Args:
            clock: returns a monotonically increasing number of seconds.
                Defaults to time.monotonic. It is a parameter so tests can hand
                in a counter: a trace that reads the wall clock is a trace no
                test can assert on, and timing is exactly the thing you most
                want a regression test for.

        Set up `self.records`, the list of finished records, and whatever you
        need to hold the step currently in flight.

        Read the clock exactly twice per step: once in before_model, once in
        whichever of after_model or on_error closes that step. The tests hand
        in a clock with a fixed number of readings, so a third read is an
        error the tests will show you.
        """
        raise NotImplementedError

    def before_model(self, index: int, messages: list[dict]) -> None:
        """
        Open a record for this step and start its timer.

        Copy `messages`: a new list, and a new dict for each message. The agent
        keeps appending to the list you were handed, so a record that stores it
        by reference ends up claiming that step one sent the whole
        conversation. This is the same reason MockClient snapshots the requests
        it records.
        """
        raise NotImplementedError

    def after_model(self, index: int, response: Any) -> None:
        """
        Close the record: text, finish reason, usage, and elapsed time.

        `response.choices[0].message.content` is None when the model asked for
        tools, and that None is worth keeping as None rather than as "".
        """
        raise NotImplementedError

    def before_tool(self, index: int, name: str, arguments: dict) -> None:
        """Nothing to record here. The name goes in on the way out."""

    def after_tool(self, index: int, name: str, result: str, failed: bool) -> None:
        """
        Append `name` to the current step's tool_calls.

        Append rather than add to a set. Two calls to the same tool in one step
        is the signal that something is looping, and a set throws it away.
        """
        raise NotImplementedError

    def records_for(self, index: int) -> list[StepRecord]:
        """Finished records for one step. A convenience for the tests."""
        return [record for record in self.records if record.index == index]

    def on_error(self, index: int, error: BaseException) -> None:
        """
        Put str(error) on the step that was in progress.

        Two cases, and they are not the same. If the model call raised, this
        step has no record yet: close it here, with its elapsed time, and keep
        it. A step whose call failed is the one somebody will actually read, so
        dropping it removes the whole reason to have a trace.

        If the step already closed normally and the run failed afterwards,
        which is what a spent budget looks like, the record exists already.
        Mark it and stop. Appending a second record for one model call would
        make every count in summarise() wrong.

        Do nothing at all when no step has been opened.
        """
        raise NotImplementedError


class TracedAgent:
    """The agent from the last exercise, with the five hook points wired in."""

    def __init__(
        self,
        client,
        toolbox: Toolbox | None = None,
        system: str | None = None,
        max_steps: int = 6,
        hooks: list[Hook] | None = None,
    ) -> None:
        """
        Build an agent.

        Args:
            client: a mockllm.MockClient.
            toolbox: the tools this agent may call. None means no tools.
            system: standing instructions, sent as the first message.
            max_steps: how many model calls one run may make.
            hooks: listeners, called in the order given. None means none, and
                an agent with no hooks must behave exactly as it did before
                hooks existed.

        Raises:
            ValueError: max_steps is less than 1.
        """
        raise NotImplementedError

    def run(self, question: str) -> str:
        """
        Run the loop, emitting hook calls, and return the final answer.

        Per step, in this order, with the step index counting from 1:

          - before_model(index, messages)
          - the model call. If it raises, on_error(index, exception) and then
            let the exception out. after_model must not fire for a step whose
            call raised.
          - after_model(index, response)
          - if the reply is not asking for tools, return its content, or "" if
            it has none
          - otherwise append the assistant turn, then for each requested call:
            arguments = Toolbox.decode(raw), before_tool(index, name,
            arguments), toolbox.run(...), after_tool(index, name, result,
            failed), and append the tool message

        When the budget is spent, build a MaxStepsExceeded, pass it to
        on_error, and raise it.

        Every hook is called, in list order, and an exception from one of them
        is swallowed. A counter with a bug in it must not take down a run that
        is otherwise fine, and a hook is by definition the part of the system
        nobody tested. The cost of this choice is real: a broken hook goes
        quiet rather than loud, so anything you would be upset to lose belongs
        in the run, not in a hook.

        Returns:
            The model's final text.

        Raises:
            MaxStepsExceeded: the budget ran out with the model still asking
                for tools.
            Anything the client raises, unchanged and after the hooks have
                seen it.
        """
        raise NotImplementedError
