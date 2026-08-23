"""
An intent router.

A router is a classifier with a handler attached. This one classifies twice: a
free rule pass that answers most requests, and a model call for the ones the
rules cannot separate. Everything it cannot place goes to a named fallback,
because a router that guesses is worse than one that admits it does not know.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Handoff:
    """
    What a specialist is handed when the router picks it.

    Attributes:
        request: the message being routed.
        history: the earlier turns, oldest first, as chat messages. A specialist
            given only the last message cannot resolve "and the other one too",
            which is most of what people actually type.
        reason: the decision reason that sent the work here, carried so the
            specialist can behave differently on a fallback if it wants to.
    """

    request: str
    history: tuple[dict, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class Route:
    """
    One destination.

    Attributes:
        name: the label the classifier produces and the router dispatches on.
        description: what this route is for, in one line. It is not decoration:
            it is what the model reads when the rules do not fire, so a vague
            description is a routing bug waiting to happen.
        handler: called with a Handoff and returns the reply.
        keywords: words that indicate this route. A keyword containing a space
            matches only when every one of its words is present.
    """

    name: str
    description: str
    handler: Callable[[Handoff], str]
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    """
    Where the request is going and why it went there.

    Attributes:
        route: the chosen route name. Never empty.
        confidence: 0.0 to 1.0. For a rule decision this is the fraction of the
            route's keywords that matched; for a model decision it is what the
            model reported. The two are not the same scale and you should not
            compare them across kinds.
        reason: one of "rule", "model", "fallback:malformed",
            "fallback:unknown-route", "fallback:low-confidence".
        matched: the keywords that fired, in the route's own order. Empty for
            every decision that did not come from the rules.
    """

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
    """
    The classifier's reply was not a label and a confidence.

    A classifier is a model, so its output is untrusted input. This is a normal
    Tuesday, not an exceptional condition, which is why the router catches it
    and falls back rather than letting it reach the caller.
    """


_WORD = re.compile(r"[a-z0-9']+")


def normalise(text: str) -> set[str]:
    """
    The lowercase word tokens of a request.

    Runs of letters, digits and apostrophes are tokens. Everything else
    separates. "Refund, please!" gives {"refund", "please"}.
    """
    raise NotImplementedError


def parse_label(content: str) -> tuple[str, float]:
    """
    Read a route label and a confidence out of the classifier's reply.

    The expected reply is a JSON object with a "route" string and a "confidence"
    number between 0.0 and 1.0 inclusive. Models routinely wrap JSON in a fenced
    code block even when told not to, so strip a leading ```json or ``` fence and
    a trailing ``` before parsing. That is not a workaround, it is the single
    cheapest thing you can do to a real classifier's output.

    Args:
        content: the reply text, or None if the model returned no content.

    Returns:
        (route, confidence).

    Raises:
        MalformedReply: the content is missing, is not JSON, is not an object,
            lacks either key, has the wrong type for either key, or reports a
            confidence outside 0.0 to 1.0. Do not repair it and do not guess a
            default: an unreadable classification is a fallback, and the router
            is the thing that decides that.
    """
    raise NotImplementedError


def rule_route(routes: list[Route], request: str) -> Decision | None:
    """
    Classify with keywords, for free.

    Score each route by how many of its keywords appear in the request. A
    single-word keyword matches when it is one of the request's tokens; a
    keyword containing a space matches when every one of its words is a token.

    Returns:
        A Decision with reason "rule" for the single highest scoring route, with
        confidence set to matched / len(keywords) and matched in the route's own
        keyword order.

        None when no route matched anything, and None when two or more routes
        tie for the top score. A tie is the interesting case: the rules have
        genuinely failed to separate the request, and picking the first route in
        the list would turn an ambiguity into a confident mistake. Returning None
        hands the decision to the model pass, which is what it is for.
    """
    raise NotImplementedError


def build_router_messages(routes: list[Route], request: str) -> list[dict]:
    """
    The two messages the classifier is sent.

    A system message carrying the route catalogue, one line per route as
    "<name>: <description>", plus the instruction to answer with JSON holding a
    route and a confidence. Then a user message containing the request and
    nothing else.

    The request goes last and alone. Burying it above the catalogue is the most
    reliable way to have the model classify the instructions instead.

    Returns:
        A list of exactly two message dicts, system first.
    """
    raise NotImplementedError


def model_route(
    client: Any,
    routes: list[Route],
    request: str,
    *,
    fallback: str,
    threshold: float = 0.6,
) -> Decision:
    """
    Classify with one model call, and refuse to trust it blindly.

    Send build_router_messages(routes, request), read
    choices[0].message.content, and turn it into a Decision.

    Four outcomes, and three of them are the fallback route:

        the reply did not parse      -> reason "fallback:malformed",
                                        confidence 0.0
        the label is not a route     -> reason "fallback:unknown-route",
                                        confidence as reported
        confidence < threshold       -> reason "fallback:low-confidence",
                                        confidence as reported
        otherwise                    -> reason "model", the reported route

    Keep the reported confidence on the two fallbacks that have one. A trace
    saying the model wanted "billing" at 0.41 against a floor of 0.6 tells you
    to move the floor. A trace saying "fell back" tells you nothing.

    `matched` is always empty here. Keywords did not decide this.
    """
    raise NotImplementedError


class Router:
    """
    Rules first, model second, fallback always.

    The order is the whole design. The rule pass costs nothing and settles the
    requests that are genuinely unambiguous, so the model call is spent only on
    the ones where it might change the answer. Reversing it works and costs a
    call per request forever.
    """

    def __init__(
        self,
        client: Any,
        routes: list[Route],
        *,
        fallback: str,
        threshold: float = 0.6,
    ) -> None:
        """
        Build a router.

        Raises:
            ValueError: `routes` is empty, two routes share a name, or
                `fallback` does not name one of them. All three are typos you
                want to find at construction rather than on the request that
                happens to be ambiguous at three in the morning.
        """
        raise NotImplementedError

    def decide(self, request: str) -> Decision:
        """
        Choose a route.

        Try rule_route first and return its decision unchanged when it produced
        one, without calling the model. Otherwise fall through to model_route
        with this router's fallback and threshold.
        """
        raise NotImplementedError

    def dispatch(self, request: str, history: list[dict] | None = None) -> Dispatch:
        """
        Decide, then run the chosen route's handler.

        The handler is called with a Handoff carrying the request, the history
        as a tuple in the order given, and the decision's reason. `history` of
        None means an empty history.

        Returns:
            A Dispatch with the decision, the handoff exactly as the handler
            received it, and the handler's return value.
        """
        raise NotImplementedError
