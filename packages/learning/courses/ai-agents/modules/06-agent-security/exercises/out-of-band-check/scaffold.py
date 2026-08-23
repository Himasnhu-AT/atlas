"""
A guardrail that cannot be talked out of.

Write both guardrails, run both against a transcript carrying the injection, and
watch the model-based one approve an action it should have stopped.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Account:
    """Facts from your authentication layer. Never from the conversation."""

    account_id: str
    tier: str
    auto_refund_limit: float
    delivered_orders: dict[str, float] = field(default_factory=dict)


def model_guardrail(client, proposed_action: str, transcript: str) -> dict:
    """
    Ask a model whether an action is safe, given the conversation.

    This is the natural way to write a guardrail and it is the one this exercise
    exists to discredit. Read what it sends: the transcript, which contains the
    document, which contains the injection. You have built a second model that
    can be persuaded by the same sentence that persuaded the first, and given it
    the job of checking the first.

    Send one call:

        system:  "Is the following action safe? Answer SAFE or UNSAFE."
        user:    "The agent wants to: <proposed_action>\\n\\nContext:\\n<transcript>"

    Args:
        client: a mockllm.MockClient. Call it exactly once.
        proposed_action: a description of what the agent is about to do.
        transcript: the conversation so far, including tool output.

    Returns:
        {"verdict": "SAFE" | "UNSAFE", "reads_transcript": True}

        The verdict is the model's reply, stripped and uppercased. Anything that
        is not exactly SAFE or UNSAFE becomes "UNSAFE": a check whose answer you
        could not parse has not passed.

        `reads_transcript` is hardcoded True and is not decoration. It is the
        property that decides whether this check is independent of the thing it
        is checking, and `is_independent` below reads it.
    """
    raise NotImplementedError


def deterministic_guardrail(action: dict, account: Account) -> dict:
    """
    Decide the same question without reading the conversation.

    No transcript. No document. No model. It reads the proposed call and facts
    from the account, and the attacker can write neither.

    Args:
        action: {"tool": "refund_order", "order_id": "A-1", "amount": 40.0}
        account: trusted state.

    Returns:
        {"verdict": "SAFE" | "UNSAFE", "reason": str, "reads_transcript": False}

        UNSAFE, with a reason, when:

          - the tool is not "refund_order"          "unknown action"
          - the order is not a delivered order      "not a delivered order"
          - the amount does not match the order     "amount does not match"
          - the amount is over the account limit    "over the automatic limit"

        Compare the amount exactly against what the order was worth. An agent
        that has been talked into refunding the right order for the wrong amount
        is the same failure as the wrong order.
    """
    raise NotImplementedError


def is_independent(check: dict) -> bool:
    """
    Is this check independent of the input it is guarding?

    Args:
        check: the output of either guardrail.

    Returns:
        True when the check did not read attacker-influenced input.

        The definition worth carrying: an out-of-band check reads only values the
        untrusted input could not have influenced. Everything else is advisory,
        and a model-based check that reads the transcript shares the
        transcript's compromise.
    """
    raise NotImplementedError


def layered_decision(model_check: dict, deterministic_check: dict) -> dict:
    """
    Combine the layers, in the order that survives one of them failing.

    Args:
        model_check: the output of model_guardrail.
        deterministic_check: the output of deterministic_guardrail.

    Returns:
        A dict shaped:

            {"allowed": False, "blocked_by": "deterministic", "reason": "..."}

        The deterministic check decides. A model-based check may only make the
        answer MORE restrictive, never less: it can veto an action the
        deterministic layer allowed, and it can never rescue one the
        deterministic layer refused.

        `blocked_by` is "deterministic", "model", or "" when allowed. When both
        refuse, the deterministic one is named, because that is the layer that
        would still have held if the model had been talked round.
    """
    raise NotImplementedError


def audit_entry(action: dict, decision: dict, attempt_id: str) -> dict:
    """
    What goes in the log, whatever happened.

    Every denied call, with its arguments and reason, to somewhere the agent
    cannot write. This is the only one of the layers that has any value after
    the fact: it is what tells you an attack was attempted.

    Returns:
        {
            "attempt_id": ...,
            "tool": ...,
            "arguments": {...},          a copy, not the caller's dict
            "allowed": bool,
            "blocked_by": str,
            "reason": str,
        }

        `arguments` is every key of `action` except "tool", copied, so a later
        mutation in the agent cannot rewrite what the log says was attempted.
    """
    raise NotImplementedError
