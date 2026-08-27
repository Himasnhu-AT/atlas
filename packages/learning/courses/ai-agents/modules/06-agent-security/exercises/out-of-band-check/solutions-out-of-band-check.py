"""A guardrail that cannot be talked out of: a worked solution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Account:
    account_id: str
    tier: str
    auto_refund_limit: float
    delivered_orders: dict[str, float] = field(default_factory=dict)


def model_guardrail(client, proposed_action: str, transcript: str) -> dict:
    response = client.chat.completions.create(
        model="mock",
        messages=[
            {
                "role": "system",
                "content": "Is the following action safe? Answer SAFE or UNSAFE.",
            },
            {
                "role": "user",
                "content": f"The agent wants to: {proposed_action}\n\nContext:\n{transcript}",
            },
        ],
    )

    raw = (response.choices[0].message.content or "").strip().upper()
    # A check whose answer you could not parse has not passed.
    verdict = raw if raw in {"SAFE", "UNSAFE"} else "UNSAFE"

    # The transcript went into the request, so this check shares whatever
    # compromise the transcript has.
    return {"verdict": verdict, "reads_transcript": True}


def deterministic_guardrail(action: dict, account: Account) -> dict:
    def unsafe(reason: str) -> dict:
        return {"verdict": "UNSAFE", "reason": reason, "reads_transcript": False}

    if action.get("tool") != "refund_order":
        return unsafe("unknown action")

    order_id = action.get("order_id")
    if order_id not in account.delivered_orders:
        return unsafe("not a delivered order")

    amount = action.get("amount")
    if amount != account.delivered_orders[order_id]:
        return unsafe("amount does not match")

    if amount > account.auto_refund_limit:
        return unsafe("over the automatic limit")

    return {"verdict": "SAFE", "reason": "", "reads_transcript": False}


def is_independent(check: dict) -> bool:
    return not check.get("reads_transcript", False)


def layered_decision(model_check: dict, deterministic_check: dict) -> dict:
    # The deterministic layer decides. Named first when both refuse, because it
    # is the one that would still have held if the model had been talked round.
    if deterministic_check["verdict"] == "UNSAFE":
        return {
            "allowed": False,
            "blocked_by": "deterministic",
            "reason": deterministic_check.get("reason", ""),
        }

    # A model check may only make the answer more restrictive, never less.
    if model_check["verdict"] == "UNSAFE":
        return {"allowed": False, "blocked_by": "model", "reason": "model refused"}

    return {"allowed": True, "blocked_by": "", "reason": ""}


def audit_entry(action: dict, decision: dict, attempt_id: str) -> dict:
    return {
        "attempt_id": attempt_id,
        "tool": action.get("tool"),
        # A copy, so a later mutation cannot rewrite what the log says.
        "arguments": {k: v for k, v in action.items() if k != "tool"},
        "allowed": decision["allowed"],
        "blocked_by": decision["blocked_by"],
        "reason": decision["reason"],
    }
