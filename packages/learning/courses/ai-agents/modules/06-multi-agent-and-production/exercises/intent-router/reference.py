"""
An intent router: worked solution.

Rules first because they are free, a model call for what the rules cannot
separate, and a named fallback for everything else.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Handoff:
    """What a specialist is handed: the request, the earlier turns, and why."""

    request: str
    history: tuple[dict, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class Route:
    """A name the classifier can emit, a description it reads, and a handler."""

    name: str
    description: str
    handler: Callable[[Handoff], str]
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    """Where the request is going and why it went there."""

    route: str
    confidence: float
    reason: str
    matched: tuple[str, ...] = ()


@dataclass(frozen=True)
class Dispatch:
    """The decision, what the specialist was given, and what it said."""

    decision: Decision
    handoff: Handoff
    output: str


class MalformedReply(ValueError):
    """The classifier's reply was not a label and a confidence."""


_WORD = re.compile(r"[a-z0-9']+")

_SYSTEM = (
    "Classify the user's request into exactly one route.\n"
    "Routes:\n{catalogue}\n"
    'Answer with JSON only: {{"route": "<name>", "confidence": <0.0-1.0>}}'
)


def normalise(text: str) -> set[str]:
    """The lowercase word tokens of a request."""
    return set(_WORD.findall((text or "").lower()))


def parse_label(content: str) -> tuple[str, float]:
    """Read a route label and a confidence out of the classifier's reply."""
    if not isinstance(content, str):
        raise MalformedReply(f"expected text, got {type(content).__name__}")

    # Fenced code blocks are the single most common shape of a "JSON only"
    # reply that is not JSON. Stripping the fence costs three lines and saves a
    # fallback on a classification that was actually correct.
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else ""
        stripped = stripped.rsplit("```", 1)[0].strip()

    try:
        payload = json.loads(stripped)
    except (ValueError, TypeError) as exc:
        raise MalformedReply(f"reply is not JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise MalformedReply(f"expected a JSON object, got {type(payload).__name__}")

    route = payload.get("route")
    confidence = payload.get("confidence")
    if not isinstance(route, str) or not route:
        raise MalformedReply(f"'route' must be a non-empty string, got {route!r}")
    # bool is a subclass of int, and True would otherwise sail through as 1.0.
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise MalformedReply(f"'confidence' must be a number, got {confidence!r}")
    if not 0.0 <= confidence <= 1.0:
        raise MalformedReply(f"'confidence' must be within 0.0 to 1.0, got {confidence}")

    return route, float(confidence)


def _score(route: Route, tokens: set[str]) -> tuple[int, tuple[str, ...]]:
    """How many of a route's keywords are present, and which ones."""
    matched = []
    for keyword in route.keywords:
        words = keyword.lower().split()
        if words and all(word in tokens for word in words):
            matched.append(keyword)
    return len(matched), tuple(matched)


def rule_route(routes: list[Route], request: str) -> Decision | None:
    """Classify with keywords, or decline when the keywords disagree."""
    tokens = normalise(request)
    scored = [(route, *_score(route, tokens)) for route in routes]
    best = max((count for _, count, _ in scored), default=0)
    if best == 0:
        return None

    winners = [(route, matched) for route, count, matched in scored if count == best]
    if len(winners) > 1:
        # Two routes are equally plausible. Breaking the tie on list order would
        # make the answer depend on how somebody happened to declare the routes,
        # which is the least defensible tie break there is.
        return None

    route, matched = winners[0]
    return Decision(
        route=route.name,
        confidence=best / len(route.keywords),
        reason="rule",
        matched=matched,
    )


def build_router_messages(routes: list[Route], request: str) -> list[dict]:
    """A system message carrying the catalogue, then the request, alone."""
    catalogue = "\n".join(f"{route.name}: {route.description}" for route in routes)
    return [
        {"role": "system", "content": _SYSTEM.format(catalogue=catalogue)},
        {"role": "user", "content": request},
    ]


def model_route(
    client: Any,
    routes: list[Route],
    request: str,
    *,
    fallback: str,
    threshold: float = 0.6,
) -> Decision:
    """One classification call, with three ways of not believing it."""
    response = client.chat.completions.create(
        model="mock",
        messages=build_router_messages(routes, request),
    )
    content = response.choices[0].message.content

    try:
        label, confidence = parse_label(content)
    except MalformedReply:
        # There is no confidence to report: the number never parsed. Reporting
        # 0.0 here is not a measurement, it is the absence of one, and the
        # reason string is what carries that.
        return Decision(route=fallback, confidence=0.0, reason="fallback:malformed")

    if label not in {route.name for route in routes}:
        return Decision(
            route=fallback, confidence=confidence, reason="fallback:unknown-route"
        )
    if confidence < threshold:
        return Decision(
            route=fallback, confidence=confidence, reason="fallback:low-confidence"
        )
    return Decision(route=label, confidence=confidence, reason="model")


class Router:
    """Rules first, model second, fallback always."""

    def __init__(
        self,
        client: Any,
        routes: list[Route],
        *,
        fallback: str,
        threshold: float = 0.6,
    ) -> None:
        if not routes:
            raise ValueError("a router with no routes cannot route anything")
        names = [route.name for route in routes]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate route name(s): {', '.join(duplicates)}")
        if fallback not in names:
            raise ValueError(
                f"fallback {fallback!r} is not a route. Known routes: {', '.join(names)}"
            )

        self.client = client
        self.routes = list(routes)
        self.fallback = fallback
        self.threshold = threshold
        self._by_name = {route.name: route for route in routes}

    def decide(self, request: str) -> Decision:
        """Rules, then the model. The rule pass is what keeps the bill down."""
        decision = rule_route(self.routes, request)
        if decision is not None:
            return decision
        return model_route(
            self.client,
            self.routes,
            request,
            fallback=self.fallback,
            threshold=self.threshold,
        )

    def dispatch(self, request: str, history: list[dict] | None = None) -> Dispatch:
        """Decide, then run the chosen route's handler on the whole context."""
        decision = self.decide(request)
        handoff = Handoff(
            request=request,
            history=tuple(history or ()),
            reason=decision.reason,
        )
        output = self._by_name[decision.route].handler(handoff)
        return Dispatch(decision=decision, handoff=handoff, output=output)
