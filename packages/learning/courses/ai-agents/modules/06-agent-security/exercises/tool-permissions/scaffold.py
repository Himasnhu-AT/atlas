"""
Least privilege for tools.

The model choosing a tool is not an authorisation decision, because the model is
the part the attacker can reach. Authority belongs to the state the run is in and
to values the attacker never wrote.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Order:
    """One order, as your authentication layer knows it. Never from the model."""

    order_id: str
    total: float
    state: str  # "pending" | "delivered" | "cancelled"


@dataclass
class Session:
    """
    Everything the permission checks are allowed to read.

    None of this comes from the conversation. That is the entire property that
    makes a check worth anything: the values the decision reads are values the
    attacker cannot write.
    """

    phase: str = "gathering"  # "gathering" | "acting"
    approved: bool = False
    auto_refund_limit: float = 100.0
    orders: dict[str, Order] = field(default_factory=dict)


READ_TOOLS = ["search_docs", "lookup_order"]
WRITE_TOOLS = ["refund_order"]


def tools_for(session: Session) -> list[str]:
    """
    Which tools go in the `tools` array for this request.

    You are already making this choice on every call; right now the answer is
    "everything", which is a choice.

    Args:
        session: where the run is.

    Returns:
        Tool names, sorted, for this state:

          - gathering                       read tools only
          - acting, not approved            read tools only
          - acting, approved                read tools and write tools

        When a write tool is not in this list, no sentence in any document can
        produce a call to it. The persuasion succeeds and produces nothing,
        which is what a control looks like.
    """
    raise NotImplementedError


@dataclass
class Decision:
    """The result of a permission check."""

    allowed: bool
    reason: str = ""


def check_call(name: str, arguments: dict, session: Session) -> Decision:
    """
    Decide whether one proposed tool call may run.

    Allowing a tool by name and stopping there leaves the model a free choice of
    arguments, and an injection that can get a call emitted can usually choose
    what it acts on.

    Args:
        name: the tool the model asked for.
        arguments: the arguments it chose. Untrusted.
        session: trusted state.

    Returns:
        A Decision. Refuse, with a reason, when:

          - the tool is not in `tools_for(session)`      "not available"
          - refund_order has no order_id                 "no order_id"
          - the order is not in this session             "not in this session"
          - the order's state is not "delivered"         "not delivered"
          - the total is over session.auto_refund_limit  "over the automatic limit"

        Check availability first. A tool that was never offered should report
        that, not leak whether some order exists.

        The reason goes into the model's context, so it is a channel the
        attacker can read. Keep it to what you would happily show the user: no
        limits, no ids they did not supply, no internal policy.
    """
    raise NotImplementedError


def denial_observation(name: str, decision: Decision, call_id: str = "call_1") -> dict:
    """
    Turn a refusal into a tool message the loop can carry on from.

    A denial is not a crash. It is an observation, exactly like a failed tool,
    so the agent can do something sensible such as explaining that this needs a
    person.

    Returns:
        {"role": "tool", "tool_call_id": call_id,
         "content": "<name> was not permitted: <reason>"}
    """
    raise NotImplementedError


def run_guarded(calls: list[dict], session: Session) -> dict:
    """
    Run a sequence of proposed calls through the checks.

    Args:
        calls: each {"name": ..., "arguments": {...}}, in the order the model
            asked for them.
        session: trusted state.

    Returns:
        A dict shaped:

            {
                "executed": ["lookup_order"],
                "denied": [{"name": "refund_order", "reason": "not available"}],
                "observations": [ ...one tool message per denial... ],
            }

        Nothing is actually executed here; "executed" is the list that WOULD
        have run. The exercise is about the decision, not the side effect.

        Every call is considered. A denial does not stop the run, because
        stopping would make a refused call indistinguishable from a crash.
    """
    raise NotImplementedError
