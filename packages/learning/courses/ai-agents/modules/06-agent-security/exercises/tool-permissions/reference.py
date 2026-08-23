"""Least privilege for tools: a worked solution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Order:
    order_id: str
    total: float
    state: str


@dataclass
class Session:
    phase: str = "gathering"
    approved: bool = False
    auto_refund_limit: float = 100.0
    orders: dict[str, Order] = field(default_factory=dict)


READ_TOOLS = ["search_docs", "lookup_order"]
WRITE_TOOLS = ["refund_order"]


def tools_for(session: Session) -> list[str]:
    if session.phase == "acting" and session.approved:
        return sorted(READ_TOOLS + WRITE_TOOLS)
    return sorted(READ_TOOLS)


@dataclass
class Decision:
    allowed: bool
    reason: str = ""


def check_call(name: str, arguments: dict, session: Session) -> Decision:
    # Availability first: a tool that was never offered reports that, rather
    # than leaking whether some order exists.
    if name not in tools_for(session):
        return Decision(False, "not available")

    if name != "refund_order":
        return Decision(True)

    order_id = arguments.get("order_id")
    if not order_id:
        return Decision(False, "no order_id")

    # `session.orders` came from authentication, not from the conversation.
    order = session.orders.get(order_id)
    if order is None:
        return Decision(False, "not in this session")
    if order.state != "delivered":
        return Decision(False, "not delivered")
    if order.total > session.auto_refund_limit:
        return Decision(False, "over the automatic limit")

    return Decision(True)


def denial_observation(name: str, decision: Decision, call_id: str = "call_1") -> dict:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": f"{name} was not permitted: {decision.reason}",
    }


def run_guarded(calls: list[dict], session: Session) -> dict:
    executed: list[str] = []
    denied: list[dict] = []
    observations: list[dict] = []

    for index, call in enumerate(calls, start=1):
        name = call["name"]
        decision = check_call(name, call.get("arguments", {}), session)

        if decision.allowed:
            executed.append(name)
            continue

        denied.append({"name": name, "reason": decision.reason})
        observations.append(denial_observation(name, decision, f"call_{index}"))

    return {"executed": executed, "denied": denied, "observations": observations}
