"""
Hooks and a trace: reference solution.

Read this after your own attempt. The comments are about why the ordering and
the copying are what they are, because those are the two things that make a
trace either trustworthy or decorative.
"""

from __future__ import annotations

import dataclasses
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

REDACTED = "[redacted]"

TEXT_FIELDS = frozenset({"response_text", "error"})


class ToolError(Exception):
    """A tool failed in a way the model can recover from."""


class MaxStepsExceeded(Exception):
    """The agent spent its whole step budget without producing an answer."""


@dataclass
class StepRecord:
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
    """Five places to stand. The defaults do nothing."""

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
    """The registry from the previous exercise, trimmed."""

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
        try:
            arguments = json.loads(arguments_json)
        except (json.JSONDecodeError, ValueError):
            return {}
        return arguments if isinstance(arguments, dict) else {}

    def run(self, name: str, arguments: dict) -> tuple[str, bool]:
        if name not in self._tools:
            return f"error: unknown tool {name!r}", True
        try:
            return str(self._tools[name](**arguments)), False
        except ToolError as error:
            return f"error: {error}", True
        except TypeError as error:
            return f"error: wrong arguments for {name}: {error}", True


def summarise(records: Iterable[StepRecord]) -> dict:
    steps = list(records)
    tool_counts: dict[str, int] = {}
    for record in steps:
        for name in record.tool_calls:
            tool_counts[name] = tool_counts.get(name, 0) + 1

    prompt_tokens = sum(record.prompt_tokens for record in steps)
    completion_tokens = sum(record.completion_tokens for record in steps)

    return {
        "steps": len(steps),
        "failed_steps": sum(1 for record in steps if record.error is not None),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "elapsed_ms": sum(record.elapsed_ms for record in steps),
        # Sorted so two runs of the same shape produce byte identical output.
        # A summary that reorders itself is a summary nobody can diff.
        "tool_calls": {name: tool_counts[name] for name in sorted(tool_counts)},
    }


def redact(record: StepRecord, fields: Iterable[str]) -> StepRecord:
    names = set(fields)

    # New dicts, not the caller's. The agent is still appending to the message
    # list these came from, and blanking in place would edit a live run.
    messages = [
        {key: (REDACTED if key in names else value) for key, value in message.items()}
        for message in record.messages
    ]

    values = {f.name: getattr(record, f.name) for f in dataclasses.fields(record)}
    values["messages"] = messages
    values["tool_calls"] = list(record.tool_calls)
    for name in names & TEXT_FIELDS:
        values[name] = REDACTED

    # Only the text fields are blanked, so every number and every name on the
    # record survives. summarise(redact(r)) == summarise(r), always.
    return StepRecord(**values)


class Tracer(Hook):
    """The hook that writes the trace. One StepRecord per model call."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self.records: list[StepRecord] = []
        self.clock = clock or time.monotonic
        self._current: StepRecord | None = None
        self._kept = False
        self._started_at: float = 0.0

    def before_model(self, index: int, messages: list[dict]) -> None:
        self._current = StepRecord(
            index=index,
            # A copy at two levels. One level would still share the dicts, and
            # a shared dict is enough for a later turn to rewrite an earlier
            # record.
            messages=[dict(message) for message in messages],
        )
        self._kept = False
        self._started_at = self.clock()

    def after_model(self, index: int, response: Any) -> None:
        record = self._current
        if record is None:
            return
        choice = response.choices[0]
        record.response_text = choice.message.content
        record.finish_reason = choice.finish_reason
        record.prompt_tokens = response.usage.prompt_tokens
        record.completion_tokens = response.usage.completion_tokens
        record.elapsed_ms = self._elapsed()
        # The record is kept the moment the model returns, not when the step
        # finishes. Tool calls land on it afterwards through after_tool, which
        # works because the list is on the object rather than on a copy.
        self.records.append(record)
        self._kept = True

    def before_tool(self, index: int, name: str, arguments: dict) -> None:
        """Nothing to record here. The name goes in on the way out."""

    def after_tool(self, index: int, name: str, result: str, failed: bool) -> None:
        if self._current is not None:
            self._current.tool_calls.append(name)

    def records_for(self, index: int) -> list[StepRecord]:
        return [record for record in self.records if record.index == index]

    def on_error(self, index: int, error: BaseException) -> None:
        record = self._current
        if record is None:
            return
        record.error = str(error)
        if not self._kept:
            # The model call itself raised, so this record has never been
            # kept. Close it now: a step whose call failed is the one somebody
            # will want to read, and dropping it loses the whole reason to
            # have a trace.
            record.elapsed_ms = self._elapsed()
            self.records.append(record)
            self._kept = True

    def _elapsed(self) -> int:
        return int(round((self.clock() - self._started_at) * 1000))


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
        if max_steps < 1:
            raise ValueError(f"max_steps must be at least 1, got {max_steps}")
        self.client = client
        self.toolbox = toolbox if toolbox is not None else Toolbox()
        self.system = system
        self.max_steps = max_steps
        # A list, not a subclass and not a single handler. Adding a second
        # listener is appending to a list; adding a second behaviour to a
        # subclass is editing a class two other things already inherit from.
        self.hooks = list(hooks or [])

    def _emit(self, event: str, *args) -> None:
        for hook in self.hooks:
            try:
                getattr(hook, event)(*args)
            except Exception:
                # Deliberate. A broken counter must not fail a run that the
                # model and the tools got right. The price is that a hook can
                # fail silently, which is why nothing load bearing goes in one.
                pass

    def run(self, question: str) -> str:
        messages: list[dict] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": question})

        schemas = self.toolbox.schemas
        step = 0

        for step in range(1, self.max_steps + 1):
            self._emit("before_model", step, messages)

            try:
                response = self.client.chat.completions.create(
                    model="mock", messages=messages, tools=schemas
                )
            except Exception as error:
                # The hooks see it before the caller does, and the exception
                # goes up unchanged. Swallowing it here would turn a provider
                # outage into a run that returned "" for no stated reason.
                self._emit("on_error", step, error)
                raise

            self._emit("after_model", step, response)
            choice = response.choices[0]

            if choice.finish_reason != "tool_calls":
                return choice.message.content or ""

            messages.append(
                {
                    "role": "assistant",
                    "content": choice.message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in choice.message.tool_calls
                    ],
                }
            )

            for call in choice.message.tool_calls:
                name = call.function.name
                arguments = Toolbox.decode(call.function.arguments)
                self._emit("before_tool", step, name, arguments)
                result, failed = self.toolbox.run(name, arguments)
                self._emit("after_tool", step, name, result, failed)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )

        exhausted = MaxStepsExceeded(
            f"the agent used all {self.max_steps} model call(s) and was still asking for tools"
        )
        self._emit("on_error", step, exhausted)
        raise exhausted
