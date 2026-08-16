"""
The ReAct loop, from scratch.

Call the model, run what it asks for, put the result back in the conversation,
call the model again. Every agent framework you will ever use is this loop with
more logging, so it is worth building once with nothing hiding behind it.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import json
from typing import Any, Callable


class MaxStepsExceeded(Exception):
    """
    The step budget ran out before the model produced a final answer.

    Written for you, and worth reading before you use it. It carries the
    transcript, because the only useful thing about a runaway agent is what it
    was doing on the way round: which tool it kept reaching for, and with what
    arguments. An exception that says "budget exceeded" and nothing else throws
    away the whole investigation.
    """

    def __init__(self, steps: int, messages: list[dict]) -> None:
        super().__init__(
            f"the agent used all {steps} model calls without producing an answer"
        )
        self.steps = steps
        self.messages = messages


class TruncatedAnswer(Exception):
    """
    The model was cut off by its output limit part way through a reply.

    A finish_reason of "length" means the text you got is the beginning of a
    sentence, not an answer. Returning it as though it were finished is the bug
    this class exists to make impossible.
    """


class ToolError(Exception):
    """A tool call could not be honoured. Raised by dispatch, below."""


def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression.

    Only digits, spaces and + - * / ( ) . are allowed, which is what keeps this
    from being a way to run arbitrary code. Never hand model output to a bare
    eval().

    Args:
        expression: The arithmetic to evaluate, for example "(19 * 42) - 8".
    """
    allowed = set("0123456789.+-*/() ")
    if not expression or any(character not in allowed for character in expression):
        return f"error: expression contains disallowed characters: {expression!r}"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as error:
        return f"error: {error}"


def lookup_population(city: str) -> dict:
    """Look up the population of a city.

    Args:
        city: City name on its own, in English.
    """
    table = {"paris": 2_102_650, "tokyo": 13_960_000, "lagos": 15_388_000}
    found = table.get(city.strip().lower())
    if found is None:
        return {"city": city, "found": False}
    return {"city": city, "population": found, "found": True}


def dispatch(registry: dict[str, Callable], name: str, arguments_json: str) -> Any:
    """
    Run one tool call and return whatever the tool returns.

    Provided for you: this is the previous exercise, trimmed. Note that it
    returns the tool's own value and not a string, which is deliberate. Turning
    that value into something a model can read is your job, one function down.
    """
    if name not in registry:
        available = ", ".join(sorted(registry)) or "none"
        raise ToolError(f"unknown tool: {name!r}. Available tools: {available}")
    try:
        arguments = json.loads(arguments_json)
    except (json.JSONDecodeError, ValueError) as error:
        raise ToolError(f"arguments for {name} were not valid JSON: {error}") from error
    if not isinstance(arguments, dict):
        raise ToolError(f"arguments for {name} must be a JSON object")
    return registry[name](**arguments)


def to_tool_content(result: Any) -> str:
    """
    Turn a tool's return value into the text that goes back to the model.

    A tool message carries a string. There is nowhere in the wire format for a
    dict, so something has to serialize, and if you leave it to str() you send
    the model Python's repr: single quotes, True instead of true, and a shape
    no model was ever trained to read.

    Rules:
      - a str goes back as itself, untouched
      - a dict or a list goes back as json.dumps(...) with sort_keys=True, so
        the same result serializes the same way on every run
      - anything else goes back as str(...)

    sort_keys matters more than it looks. Two runs that send byte identical
    prompts can be served from a provider's prompt cache; two runs that differ
    only in key order cannot.
    """
    raise NotImplementedError


def assistant_turn(choice: Any) -> dict:
    """
    Build the assistant message that records what the model asked for.

    This message goes into the history BEFORE any tool result. A tool message
    answers a request, and providers reject a conversation where a tool message
    answers nothing: send the results without this turn and you get a 400 back,
    not a bad answer.

    Args:
        choice: response.choices[0] from the client.

    Returns:
        {
          "role": "assistant",
          "content": <choice.message.content, which is usually None here>,
          "tool_calls": [
            {"id": <call.id>,
             "type": "function",
             "function": {"name": <call.function.name>,
                          "arguments": <call.function.arguments>}},
            ...
          ],
        }

    Keep `arguments` as the raw JSON string the model produced. Parsing it and
    re-serializing it is how the arguments the model sees itself having sent
    stop matching the ones it actually sent.
    """
    raise NotImplementedError


def tool_result_turn(call_id: str, content: str) -> dict:
    """
    Build the message carrying one tool's result back to the model.

    Returns:
        {"role": "tool", "tool_call_id": call_id, "content": content}

    `tool_call_id` is the only thing pairing this result with the request it
    answers. Position is not the pairing and neither is the tool name, because
    a model can call the same tool twice in one turn.
    """
    raise NotImplementedError


def run_agent(
    client,
    registry: dict[str, Callable],
    tools: list[dict],
    question: str,
    max_steps: int = 6,
) -> str:
    """
    Run the loop until the model produces a final answer.

    Flow:
      1. messages starts as [{"role": "user", "content": question}]
      2. up to max_steps times:
         a. response = client.chat.completions.create(model="mock",
                                                      messages=messages,
                                                      tools=tools)
         b. read choice = response.choices[0] and branch on finish_reason:
              "tool_calls" -> carry on below
              "length"     -> raise TruncatedAnswer
              anything else -> return choice.message.content, or "" if it is None
         c. append assistant_turn(choice)
         d. for every call in choice.message.tool_calls, in order: dispatch it
            and append tool_result_turn(call.id, to_tool_content(result))
      3. the budget is spent: raise MaxStepsExceeded(max_steps, messages)

    Branch on finish_reason, never on the text. Deciding you are done because
    the content looks like an answer, or because it does not contain the word
    "Action", is how ReAct was done before providers had a tool calling API,
    and it breaks the first time a model narrates its plan before calling a
    tool.

    Args:
        max_steps: the maximum number of MODEL CALLS, not tool calls and not
            round trips. max_steps=1 means one call: if that call asks for a
            tool, the budget is gone and the loop raises. Below 1 is a bug in
            the caller, so it raises rather than quietly doing nothing.

    Raises:
        ValueError: max_steps < 1.
        TruncatedAnswer: the model ran out of output budget.
        MaxStepsExceeded: the step budget ran out with no answer.
        ToolError: propagated from dispatch. Surviving it is the last lesson in
            this module; for now, a malformed call ends the run.

    Every iteration sends the entire `messages` list again, because the API is
    stateless. A ten step run does not cost ten calls' worth of input tokens,
    it costs the sum of a conversation that grew on every step, and the tool
    results are usually the largest part of it.
    """
    raise NotImplementedError
