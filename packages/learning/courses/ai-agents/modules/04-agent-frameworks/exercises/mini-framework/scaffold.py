"""
A mini framework.

Every agent framework starts from the same three pieces: something that turns a
Python function into a tool schema, a registry that holds those tools, and an
object that owns a prompt and a loop. You wrote the loop in the last module, so
what is left is the scaffolding around it.

Work down the file. The first two functions are mechanical, the registry uses
them, and the Agent uses the registry.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, get_origin

#: Python annotations that have an obvious JSON Schema counterpart. Anything
#: outside this table is a deliberate error rather than a guess: see describe().
JSON_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class ToolSpecError(ValueError):
    """
    A function cannot be turned into a tool schema.

    Raised at registration time, not at call time. A tool whose schema is wrong
    produces a model that calls the wrong thing with the wrong arguments, and
    that failure is expensive and confusing. Failing while the program is
    starting is neither.
    """


class ToolError(Exception):
    """
    A tool failed in a way the model can recover from.

    "The order id does not exist" is a ToolError. A bug in your own code is not:
    let that one propagate, because feeding a stack trace back to a model just
    buys you a confident apology on top of a broken run.
    """


class MaxStepsExceeded(Exception):
    """The agent spent its whole step budget without producing an answer."""


@dataclass
class ToolCallRecord:
    """
    One tool invocation, as the run's audit trail will remember it.

    `failed` is true for anything the tool did not return normally: an unknown
    name, unparseable arguments, or a ToolError. `result` is what was sent back
    to the model either way, because the model has to be told what went wrong
    in order to try something else.
    """

    name: str
    arguments: dict
    result: str
    failed: bool = False


@dataclass
class AgentResult:
    """
    Everything one run produced, not just its last sentence.

    Returning a bare string throws away what anyone debugging the run will ask
    for first: how many model calls it took, what it called, what that cost.
    """

    answer: str
    steps: int = 0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    tokens_used: int = 0


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """
    Split a docstring into its summary line and its documented parameters.

    Args:
        doc: a raw __doc__ value, which still carries the indentation of the
            source file. inspect.cleandoc() removes that for you.

    Returns:
        A pair (summary, params). `summary` is the first non-empty line,
        stripped. `params` maps a parameter name to its description, read from
        a Google style Args: section:

            Args:
                city: City name, for example 'Paris'.
                unit: celsius or fahrenheit. Defaults to celsius.

        A line indented further than the parameter lines is a continuation and
        joins the previous description with a single space. A line at column
        zero ends the section, which is how Returns: and Raises: stop it.

        Return ("", {}) for None and for an empty docstring.

    The parameter pattern is deliberately naive: a name, an optional type in
    brackets, a colon, the rest. It will mis-read a continuation line that
    happens to contain a colon. That is the honest boundary of hand written
    docstring parsing, and it is why libraries that need this to be right pull
    in a real docstring parser instead.
    """
    raise NotImplementedError


def describe(fn: Callable) -> dict:
    """
    Derive a tool schema from a function's signature and docstring.

    The shape is the one the chat completions API takes:

        {"type": "function",
         "function": {"name": ..., "description": ...,
                      "parameters": {"type": "object",
                                     "properties": {...},
                                     "required": [...]}}}

    The description is the docstring summary. Each parameter becomes one entry
    in `properties` with a "type" from JSON_TYPES, plus a "description" taken
    from the Args: section when there is one. A parameter with no default goes
    in `required`, in signature order.

    Annotations are strings here because of `from __future__ import
    annotations`, so resolve them with inspect.get_annotations(fn,
    eval_str=True). Unwrap generics with get_origin, so list[str] is an array.

    Raises:
        ToolSpecError: the docstring has no summary, a parameter has no
            annotation, an annotation has no JSON Schema counterpart (str |
            None and your own classes are the usual ones), or the function
            takes *args or **kwargs, which JSON Schema cannot express. When the
            problem is a particular parameter, the message names that
            parameter, because "get_weather has an unannotated parameter" sends
            somebody to read a signature and "get_weather(city) has no type
            annotation" does not.

    Refusing to guess is the point. A schema that silently calls an
    unannotated parameter a string is a bug that surfaces as the model passing
    "3" where you wanted 3, three weeks later, in production.
    """
    raise NotImplementedError


def tool(fn: Callable) -> Callable:
    """
    Mark a function as a tool by attaching its schema.

    Set fn.tool_schema to describe(fn) and fn.is_tool to True, then return the
    same function object. Do not wrap it. A decorator that returns a different
    callable breaks help(), confuses debuggers, and puts an extra frame in
    every stack trace, and it buys nothing at all here.

    Raises:
        ToolSpecError: whatever describe() raises, unchanged.
    """
    raise NotImplementedError


class ToolRegistry:
    """
    The one place a tool is defined, rather than two.

    Without a registry you write the function, then write its schema, then
    write a dispatch table entry, and the three drift apart on a Friday. The
    registry derives the schema and the dispatch entry from the function, so
    there is one definition and nothing to keep in sync.
    """

    def __init__(self, tools: list[Callable] | None = None) -> None:
        """
        Build a registry, optionally adding tools in the order given.

        Raises:
            ToolSpecError: any of the usual describe() problems, or two tools
                with the same name.
        """
        raise NotImplementedError

    def add(self, fn: Callable) -> Callable:
        """
        Register one tool and return it, so this works as a decorator:

            registry = ToolRegistry()

            @registry.add
            def get_weather(city: str) -> str:
                ...

        Apply tool() to `fn` if it has not been applied already, so a plain
        function can be registered directly. Registration order is the order
        the schemas will be sent in.

        Raises:
            ToolSpecError: the function has no usable schema, or its name is
                already registered. Names are how the model addresses a tool,
                so a duplicate is not a merge, it is a coin toss.
        """
        raise NotImplementedError

    @property
    def names(self) -> list[str]:
        """The registered tool names, in registration order."""
        raise NotImplementedError

    @property
    def schemas(self) -> list[dict]:
        """The tool schemas, in registration order, ready to send."""
        raise NotImplementedError

    def invoke(self, name: str, arguments_json: str) -> ToolCallRecord:
        """
        Run one tool call from the model and record what happened.

        Args:
            name: the tool the model asked for, which may not exist.
            arguments_json: the raw JSON string the model produced, which may
                not parse and may not be an object even when it does.

        Returns:
            A ToolCallRecord. On success, `result` is str() of the return value
            and `failed` is False.

        This function never raises for a bad request from the model. Four
        things go wrong routinely: the name is unknown, the JSON is malformed,
        the JSON is valid but is not an object, and the arguments do not match
        the signature. Each becomes a record with failed=True and a `result`
        starting with "error: " that says what was wrong, because the string
        goes back to the model as the tool result and is the only chance it has
        to correct itself.

        A ToolError raised by the tool is the fifth, and is handled the same
        way: the record's `result` is "error: " followed by that exception's
        own message, unchanged. The tool wrote that sentence for the model to
        read, so replacing it with a generic one throws away the only thing
        that tells the model what to try instead.

        Everything else propagates. A KeyError from inside your own tool is a
        bug in your code, and swallowing it hides it behind a model that
        cheerfully tries something else.
        """
        raise NotImplementedError


class Agent:
    """
    A client, a registry, a prompt and a budget, configured once.

    This is the object every framework on the market is a richer version of.
    Two agents sharing one registry with different system prompts is the whole
    reason it exists: without it you copy the loop and change one string.
    """

    def __init__(
        self,
        client,
        registry: ToolRegistry | None = None,
        system: str | None = None,
        max_steps: int = 6,
    ) -> None:
        """
        Build an agent.

        Args:
            client: a mockllm.MockClient, or anything with the same
                chat.completions.create shape.
            registry: the tools this agent may call. None means no tools.
            system: standing instructions, sent as the first message.
            max_steps: how many model calls one run may make.

        Raises:
            ValueError: max_steps is less than 1. A budget of zero is a run
                that cannot answer, and it is always a configuration mistake
                rather than an intention.
        """
        raise NotImplementedError

    def run(self, question: str) -> AgentResult:
        """
        Run the loop and return everything it produced.

        The flow:
          - messages start with the system message, if there is one, then the
            question as a user message
          - up to max_steps model calls, each passing tools=self.registry.schemas
          - a reply whose finish_reason is not "tool_calls" ends the run
          - otherwise append the assistant turn including its tool_calls, then
            one {"role": "tool", "tool_call_id": ..., "content": ...} message
            per call, then loop
          - add usage.total_tokens from every call, including the last one

        Returns:
            An AgentResult whose `steps` is the number of model calls made,
            whose `tool_calls` holds one record per invocation in order, and
            whose `answer` is the final message content, or "" if the model
            returned none.

        Raises:
            MaxStepsExceeded: the budget ran out with the model still asking
                for tools. Raise rather than return the last thing you have.
                A run that quietly returns a half answer becomes a bug report
                six weeks later saying "sometimes it just does not finish".

        Keep every piece of per run state local to this method. Storing the
        message list on `self` leaks one run's conversation into the next, ties
        the object to one caller at a time, and leaves debris behind when a run
        raises. It is the most common bug in hand rolled agent objects and the
        tests check for it directly.
        """
        raise NotImplementedError
