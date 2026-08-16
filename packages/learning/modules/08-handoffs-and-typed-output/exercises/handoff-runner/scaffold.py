"""
Handoffs are tool calls.

You are building the runner that sits under a multi agent system: a loop with
one variable, `current_agent`, and a synthetic tool per handoff target. When the
model calls one of those synthetic tools, you reassign the variable and keep
going with the conversation intact.

Everything above the line is given. Write the four functions below it.
Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Callable

#: The prefix every synthetic handoff tool carries. A name that starts with this
#: and matches no target is a bug worth shouting about, not an unknown tool.
HANDOFF_PREFIX = "transfer_to_"


class UnknownHandoff(RuntimeError):
    """The model called a transfer tool that names no agent the current agent can reach."""


class MaxTurnsExceeded(RuntimeError):
    """The run used its whole turn budget without producing a final answer."""


@dataclass
class Agent:
    """
    One agent: a name, a system prompt, its tools, and who it can hand off to.

    `handoffs` is what makes this multi agent. Each entry becomes one more
    function schema in the tools list sent to the model, so from the model's
    side there is no difference between calling a tool and changing who is
    answering.
    """

    name: str
    instructions: str
    tools: list[Callable] = field(default_factory=list)
    handoffs: list["Agent"] = field(default_factory=list)


@dataclass
class RunResult:
    """
    What one run produced.

    Attributes:
        final_output: the last assistant message, or "" if it had no content.
        last_agent: the name of whichever agent was driving when the run ended.
        handoffs: (from_name, to_name) for every transfer, in the order they
            happened.
        messages: the conversation history, WITHOUT the system message. The
            system prompt changes every time the agent changes, so it is built
            fresh on each request rather than stored in the history. It also
            stops before the final answer: the turn that ends the run returns
            rather than appending, so the reply lives on `final_output` and
            nowhere else.
        turns: how many model calls the run made.
    """

    final_output: str
    last_agent: str
    handoffs: list[tuple[str, str]]
    messages: list[dict]
    turns: int


# ---------------------------------------------------------------------------
# Your work starts here.
# ---------------------------------------------------------------------------


def handoff_tool_name(agent: Agent) -> str:
    """
    The name of the synthetic tool that transfers control to `agent`.

    HANDOFF_PREFIX, then the agent's name lowercased with spaces and hyphens
    turned into underscores. Surrounding whitespace is stripped first.

        Agent(name="Billing")        -> "transfer_to_billing"
        Agent(name="Refund Desk")    -> "transfer_to_refund_desk"
        Agent(name="on-call")        -> "transfer_to_on_call"

    Tool names have to survive the provider's own validation, which is why the
    punctuation goes. Two agents whose names differ only in punctuation collide
    here, and that is a naming problem rather than something to encode around.
    """
    raise NotImplementedError


def tool_schemas(agent: Agent) -> list[dict]:
    """
    The tools list to send with this agent's turn: real tools, then handoffs.

    For each callable in `agent.tools`, in order:

        {"type": "function",
         "function": {
             "name": <fn.__name__>,
             "description": <inspect.getdoc(fn) or "">,
             "parameters": {
                 "type": "object",
                 "properties": {<each parameter>: {"type": "string"}},
                 "required": [<parameters with no default, in order>],
             }}}

    Every parameter is typed "string". That is a simplification the real SDKs do
    not make, and it is enough here: the point of this exercise is the handoff,
    not the type mapping. You build a real one in the last lesson of this module.

    Then for each entry in `agent.handoffs`, in order:

        {"type": "function",
         "function": {
             "name": <handoff_tool_name(target)>,
             "description": f"Hand off to {target.name}. {target.instructions}",
             "parameters": {"type": "object", "properties": {}, "required": []}}}

    The handoff schema takes no arguments, so its properties object is empty.
    The target's own instructions go in the description because that is the only
    thing telling the model what the other agent is for.

    Note that the schemas describe the CURRENT agent only. When control moves,
    the next request carries a different tools list, and that is the mechanism
    by which an agent cannot hand off to somewhere it was never wired to.
    """
    raise NotImplementedError


def dispatch(agent: Agent, name: str, arguments_json: str) -> str:
    """
    Run one ordinary tool call against `agent` and return its result as a string.

    Look the tool up by `__name__` in `agent.tools`, parse `arguments_json` as
    JSON, call the function with those arguments as keywords, and return
    `str(...)` of whatever comes back. An empty or blank arguments string means
    no arguments.

    Raises:
        KeyError: the agent has no tool with that name.
        ValueError: the arguments were not a JSON object.

    Tool results must be strings. A dict where a string belongs fails deep
    inside a real provider's client, with a message that will not mention your
    code.
    """
    raise NotImplementedError


def run(agent: Agent, user_input: str, client, max_turns: int = 8) -> RunResult:
    """
    Drive the loop until an agent answers without calling a tool.

    Flow:
      1. current_agent = agent, messages = [{"role": "user", "content": user_input}]
      2. up to max_turns times:
         a. call client.chat.completions.create(
                model="mock",
                messages=[{"role": "system", "content": current_agent.instructions}]
                         + messages,
                tools=tool_schemas(current_agent))
         b. if finish_reason is NOT "tool_calls", the run is over: return a
            RunResult carrying the reply content (or "" when it is None).
         c. append the assistant message recording the calls, in the same shape
            as the last module:
              {"role": "assistant",
               "content": <choice.message.content>,
               "tool_calls": [{"id": ..., "type": "function",
                               "function": {"name": ..., "arguments": ...}}, ...]}
         d. for every call in the batch, in order:
              - if its name matches handoff_tool_name of one of
                current_agent.handoffs: append a tool message
                {"role": "tool", "tool_call_id": <call.id>,
                 "content": f"Transferred to {target.name}."},
                record (current_agent.name, target.name) in the handoff trail,
                and reassign current_agent. That reassignment is the entire
                mechanism. Nothing is copied, nothing is restarted, and the
                history carries over untouched.
              - else if its name starts with HANDOFF_PREFIX: raise UnknownHandoff.
              - else: dispatch it and append the result in a tool message keyed
                to the same call id.
      3. raise MaxTurnsExceeded when the budget is gone.

    A handoff takes effect immediately, so a later call in the same batch is
    resolved against the new agent's tools.

    The system message is rebuilt on every request and never stored in
    `messages`. Storing it would leave the previous agent's instructions in the
    history after a transfer, and the model would then be reading two sets of
    orders.

    Args:
        max_turns: the maximum number of MODEL CALLS. Values below 1 raise
            ValueError. A handoff spends a turn like anything else, so a three
            agent chain needs at least four.

    Raises:
        ValueError: max_turns is below 1.
        UnknownHandoff: a transfer tool named an agent that is not reachable.
        MaxTurnsExceeded: the budget ran out with no final answer.
    """
    raise NotImplementedError
