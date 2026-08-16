"""
Grading the behaviour, not the answer.

The session from the last two exercises is here in full, and so are two variants
of it that are wrong on purpose. Your work is the harness: replay a persona,
score the transcript against rules a support lead would recognise, and report which
rule broke on which persona.

The personas live in test.py and are passed in. Nothing here reads from disk.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Callable

from mockllm import cosine_similarity, embed_text


# Everything down to the broken sessions is the last two exercises, finished.


@dataclass
class Article:
    """One knowledge base document. The id is what an answer cites."""

    id: str
    title: str
    body: str


@dataclass
class Reply:
    """What the agent produced for one question."""

    text: str
    cited: list[str]
    dropped: list[str]
    route: str


STOPWORDS = frozenset(
    """a am an and any are as at be been before but by can cannot did do does for from
    get got had has have how i if in is it its me my no not of on or please so still
    that the their them then there these they this to was we were what when where which
    who will with would you your just only all it's i'm""".split()
)

_WORD = re.compile(r"[a-z0-9']+")

CITATION = re.compile(r"\[(A\d+)\]")

HUMAN_QUEUE = "the human support queue"

OUT_OF_SCOPE_TEXT = (
    "Nothing in the knowledge base covers that, so I am not going to guess. "
    f"Passing this to {HUMAN_QUEUE}."
)

SYSTEM = (
    "You answer questions about this product using only the context below. "
    "Every factual sentence must carry the bracket id of the article it came "
    "from, like [A1]. If the context does not answer the question, say so "
    "plainly and do not guess."
)


def normalise(content: str) -> str:
    """Lowercase, keep words and digits, drop stopwords."""
    return " ".join(w for w in _WORD.findall(content.lower()) if w not in STOPWORDS)


def retrieve(
    articles: list[Article],
    question: str,
    k: int = 2,
    floor: float = 0.12,
) -> list[tuple[Article, float]]:
    """Best k articles for the question, score descending, id ascending on a tie."""
    query = embed_text(normalise(question))

    scored: list[tuple[Article, float]] = []
    for article in articles:
        vector = embed_text(normalise(f"{article.title} {article.body}"))
        score = cosine_similarity(query, vector)
        if score >= floor:
            scored.append((article, score))

    scored.sort(key=lambda pair: (-pair[1], pair[0].id))
    return scored[:k]


def build_messages(question: str, hits: list[tuple[Article, float]], system: str) -> list[dict]:
    """System prompt, then the retrieved context, then the question alone."""
    blocks = [f"[{article.id}] {article.title}\n{article.body}" for article, _ in hits]
    context = "Context:\n\n" + ("\n\n".join(blocks) if blocks else "(nothing retrieved)")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": context},
        {"role": "user", "content": question},
    ]


def parse_citations(text: str, allowed: list[str]) -> tuple[list[str], list[str]]:
    """Bracket ids in first appearance order, split into retrieved and invented."""
    permitted = set(allowed)
    cited: list[str] = []
    dropped: list[str] = []

    for marker in CITATION.findall(text or ""):
        bucket = cited if marker in permitted else dropped
        if marker not in bucket:
            bucket.append(marker)

    return cited, dropped


def answer(
    client,
    articles: list[Article],
    question: str,
    k: int = 2,
    floor: float = 0.12,
) -> Reply:
    """Answer one question against the knowledge base, or decline to."""
    hits = retrieve(articles, question, k=k, floor=floor)
    if not hits:
        return Reply(text=OUT_OF_SCOPE_TEXT, cited=[], dropped=[], route="out_of_scope")

    response = client.chat.completions.create(
        model="mock",
        messages=build_messages(question, hits, SYSTEM),
    )
    text = response.choices[0].message.content or ""
    cited, dropped = parse_citations(text, [article.id for article, _ in hits])
    route = "answered" if cited else "unsupported"
    return Reply(text=text, cited=cited, dropped=dropped, route=route)


# The session itself, also finished.


#: Phrases that mean "put me through to a person".
WANTS_HUMAN = ("human", "real person", "agent", "representative", "someone else")

#: Phrases that contain a trigger word and are not a request for a person.
#: "agent" is a support word and a computing word, and a customer pasting a log
#: line is not asking for anything. Word boundaries alone will not save you
#: here, because "user agent" is two whole words. Mask these first.
NOT_A_REQUEST = ("user agent", "agent string", "support agent", "this agent")

#: What the pushback says when there is a plausible article to offer.
PUSHBACK_WITH_ARTICLE = (
    "Before I pass you on, this might be the answer: [{id}] {title}. "
    "Tell me if it is not and I will hand you over."
)

#: What it says when retrieval came back with nothing.
PUSHBACK_PLAIN = (
    "I can hand you to {queue}. Before I do, tell me in one line what you are "
    "trying to do and I will try once more."
)

ESCALATION_REASON = "customer asked for a person"

ESCALATED_TEXT = (
    f"Handing this to {HUMAN_QUEUE} now, along with everything we have already tried."
)

ALREADY_ESCALATED_TEXT = (
    f"This is already with {HUMAN_QUEUE}. They have the whole thread and will pick it "
    "up from there."
)

#: Longest opening message a summary will quote before it truncates.
SUMMARY_LIMIT = 160


@dataclass
class Handoff:
    """
    What the human receives when the agent gives up.

    Everything here exists so the person taking over does not have to read the
    whole transcript before they can start. Escalating with an empty payload is
    the failure mode that costs the most satisfaction: the customer explains
    themselves twice and concludes, correctly, that the bot wasted their time.

    Attributes:
        reason: why this escalated, in a few words.
        summary: one line. What they asked and how long this has been going on.
        attempted: every reply the agent already sent, in order. The human needs
            this to avoid repeating an answer that has already failed.
        article_ids: knowledge base ids the agent cited, deduplicated.
        transcript_turns: how many messages the customer sent.
    """

    reason: str
    summary: str
    attempted: list[str]
    article_ids: list[str]
    transcript_turns: int


@dataclass
class SessionReply:
    """
    One turn of the conversation, from the agent's side.

    action is exactly one of "answered", "pushed_back", "escalated",
    "out_of_scope". handoff is set only on an "escalated" turn.
    """

    text: str
    action: str
    handoff: Handoff | None = None


def wants_human(message: str) -> bool:
    """Decide whether the customer is asking for a person."""
    # Mask the phrases that merely contain a trigger word before matching. A
    # bare word boundary is not enough: "user agent" is two whole words, and a
    # customer pasting a log line is not asking for anything.
    text = message.lower()
    for phrase in NOT_A_REQUEST:
        text = text.replace(phrase, " ")

    return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in WANTS_HUMAN)


def summarise(transcript: list[tuple[str, str]]) -> str:
    """Compress the conversation into the one line a human reads first."""
    asked = [said for role, said in transcript if role == "user"]
    if not asked:
        return "No customer messages yet, 0 exchanges."

    # split() then join collapses newlines and runs of spaces, which is what
    # keeps a pasted stack trace from becoming a forty line summary.
    opening = " ".join(asked[0].split())
    if len(opening) > SUMMARY_LIMIT:
        opening = opening[:SUMMARY_LIMIT] + "..."

    count = len(asked)
    return f"Customer opened with: {opening} ({count} exchange(s) so far)."


class TriageSession:
    """One conversation with one customer."""

    def __init__(self, client, articles: list[Article], max_pushbacks: int = 1) -> None:
        self.client = client
        self.articles = articles
        self.max_pushbacks = max_pushbacks
        self.human_requests = 0
        self.attempted: list[str] = []
        self.cited: list[str] = []
        self.escalated = False
        self.transcript: list[tuple[str, str]] = []
        self.handoff: Handoff | None = None

    def handle(self, message: str) -> SessionReply:
        # Record the customer's turn first, so a handoff built on this turn
        # counts this turn.
        self.transcript.append(("user", message))

        if self.escalated:
            # A person owns this conversation now. Talking over them is worse
            # than saying nothing, and the model call would be pure cost.
            return self._say(ALREADY_ESCALATED_TEXT, "escalated", self.handoff)

        if wants_human(message):
            self.human_requests += 1
            if self.human_requests <= self.max_pushbacks:
                return self._push_back(message)
            return self._escalate()

        return self._answer(message)

    def _answer(self, message: str) -> SessionReply:
        reply = answer(self.client, self.articles, message)

        # The draft is recorded whether or not it is sent. The human taking over
        # needs to see what the agent tried, including the answer it was not
        # allowed to send.
        self.attempted.append(reply.text)
        for article_id in reply.cited:
            if article_id not in self.cited:
                self.cited.append(article_id)

        if reply.route == "answered":
            return self._say(reply.text, "answered")
        # "unsupported" and "out_of_scope" both mean nothing grounded the reply,
        # so the customer gets the safe line rather than the ungrounded draft.
        return self._say(OUT_OF_SCOPE_TEXT, "out_of_scope")

    def _push_back(self, message: str) -> SessionReply:
        hits = retrieve(self.articles, self._topic(message), k=1)
        if hits:
            article = hits[0][0]
            text = PUSHBACK_WITH_ARTICLE.format(id=article.id, title=article.title)
        else:
            text = PUSHBACK_PLAIN.format(queue=HUMAN_QUEUE)

        self.attempted.append(text)
        return self._say(text, "pushed_back")

    def _escalate(self) -> SessionReply:
        # Copy the lists. Aliasing them would let the payload keep changing
        # after it was handed over, which is a bug nobody finds by reading.
        self.handoff = Handoff(
            reason=ESCALATION_REASON,
            summary=summarise(self.transcript),
            attempted=list(self.attempted),
            article_ids=list(self.cited),
            transcript_turns=sum(1 for role, _ in self.transcript if role == "user"),
        )
        self.escalated = True
        return self._say(ESCALATED_TEXT, "escalated", self.handoff)

    def _topic(self, message: str) -> str:
        """
        The question the pushback should answer.

        "Can I speak to a human" retrieves nothing useful on its own, so look
        back for the last message that was not a request for a person. The
        customer's actual question is still the question.
        """
        for role, said in reversed(self.transcript[:-1]):
            if role == "user" and not wants_human(said):
                return said
        return message

    def _say(self, text: str, action: str, handoff: Handoff | None = None) -> SessionReply:
        """Record the agent's turn and return it. Every path goes through here."""
        self.transcript.append(("agent", text))
        return SessionReply(text=text, action=action, handoff=handoff)


# Two sessions that are wrong on purpose. Each is one configuration mistake, of
# the kind that reaches production because it reads fine in a diff. The harness
# you write has to catch both, and has to leave the correct session alone.


class EagerSession(TriageSession):
    """Hands over the moment anybody asks, without trying once more."""

    def __init__(self, client, articles: list[Article]) -> None:
        super().__init__(client, articles, max_pushbacks=0)


class StubbornSession(TriageSession):
    """Pushes back forever. The customer asks four times and never gets a person."""

    def __init__(self, client, articles: list[Article]) -> None:
        super().__init__(client, articles, max_pushbacks=1_000_000)


# The new work starts here.


@dataclass
class Transcript:
    """
    Everything one persona did, kept so the rubric can be asked questions later.

    Not to be confused with `TriageSession.transcript`, which is the raw
    (role, said) log the session keeps in order to summarise itself. This is the
    graded record of a whole replay, and it carries the actions and the handoff
    that the rules actually ask about.

    Attributes:
        persona: the persona's name.
        turns: (customer message, SessionReply) pairs, in order.
        actions: the action of each reply, in the same order as turns.
        handoff: the last handoff produced, or None if the session never
            escalated.
    """

    persona: str
    turns: list[tuple[str, SessionReply]]
    actions: list[str]
    handoff: Handoff | None


@dataclass
class Scorecard:
    """One persona's result: which rules held, which did not, and the fraction."""

    persona: str
    passed: list[str]
    failed: list[str]
    score: float


@dataclass
class SuiteResult:
    """
    The whole suite, in the shape a CI job needs.

    Attributes:
        per_persona: scorecard by persona name.
        pass_rate: the mean of the persona scores, to two places.
        failures: (persona, rule) for every rule that failed anywhere.
        ok: whether pass_rate cleared the floor.
    """

    per_persona: dict[str, Scorecard]
    pass_rate: float
    failures: list[tuple[str, str]]
    ok: bool


def replay(session, persona_name: str, persona: dict) -> Transcript:
    """
    Run one persona against one session and record what happened.

    The persona is a dict with a "turns" key holding the customer's messages in
    order. Feed each one to session.handle() in order, keep the (message, reply)
    pairs, and pull the actions out of the replies.

    The transcript's handoff is the last non-None handoff any reply carried, or None
    when the session never escalated. Take the last rather than the first, so a
    session that rebuilds its payload is reported on what it finally produced.

    Args:
        session: anything with a handle(message) -> SessionReply method.
        persona_name: the name this persona is filed under.
        persona: {"turns": [...], "script": [...]}. The script has already been
            used to build the session's client, so it is nothing to do with you.

    Returns:
        A Transcript. Never None, even for a persona with no turns.
    """
    raise NotImplementedError


def grounded_when_answering(transcript: Transcript) -> bool:
    """
    Every reply the agent sent as an answer cites at least one article.

    Use the CITATION pattern on the reply text. A transcript with no "answered" turn
    in it passes: the rule does not apply, and a rule that does not apply has
    not been broken. That is true of every predicate here, and it is the part
    people get wrong.
    """
    raise NotImplementedError


def pushed_back_once_before_escalating(transcript: Transcript) -> bool:
    """
    The agent tried exactly one more time before handing over.

    Look at the actions before the first "escalated". Exactly one of them must
    be "pushed_back". A transcript with no escalation in it passes.

    Zero pushbacks is the eager agent, handing over a customer who could have
    been helped. Two or more is the stubborn one, wasting a person's time
    before letting them speak to a person.
    """
    raise NotImplementedError


def escalated_by_second_request(transcript: Transcript) -> bool:
    """
    Nobody has to ask for a person three times.

    Find the customer turns where wants_human(message) is true. If there are
    fewer than two, the rule does not apply and the transcript passes. Otherwise the
    transcript must contain an "escalated" action at or before the index of the
    second request.
    """
    raise NotImplementedError


def handoff_carries_summary_and_steps(transcript: Transcript) -> bool:
    """
    The payload is worth receiving.

    A transcript with no handoff passes. A handoff must have a non-empty summary, at
    least one entry in attempted, and a transcript_turns above zero. An
    escalation carrying none of that makes the customer explain themselves
    twice.
    """
    raise NotImplementedError


def never_escalated_unrequested(transcript: Transcript) -> bool:
    """
    The agent did not hand over a customer who never asked.

    A transcript with no escalation passes. Otherwise at least one customer message
    at or before the escalating turn must satisfy wants_human().

    This is the rule that keeps the rubric honest. Without it, every other rule
    rewards escalating, and the highest scoring agent is the one that gives up
    immediately.
    """
    raise NotImplementedError


#: (name, predicate) for every rule above, in the order they are listed. The
#: name is what a failure report prints, so it has to be the rule's own name.
RUBRIC: list[tuple[str, Callable[[Transcript], bool]]] = []


def grade(transcript: Transcript, rubric=RUBRIC) -> Scorecard:
    """
    Run every rule against one transcript.

    score is len(passed) / len(rubric), rounded to two places. An empty rubric
    scores 1.0 rather than dividing by zero, though a suite with no rules in it
    is a bug you want to notice some other way.

    Returns:
        A Scorecard naming the persona, the rules that held, and the rules that
        did not, keeping the rubric's order in both lists.
    """
    raise NotImplementedError


def run_suite(session_factory, personas: dict, rubric=RUBRIC, floor: float = 0.8) -> SuiteResult:
    """
    Grade one agent against every persona.

    For each persona, build a fresh session with session_factory(persona), replay
    the persona against it, and grade the transcript. A fresh session per persona
    matters: a session carries state, and reusing one makes the second persona's
    result depend on the first, which is how a suite starts lying to you.

    pass_rate is the mean of the persona scores, rounded to two places. failures
    holds a (persona, rule) pair for every rule that failed anywhere, so the
    output says what to go and fix instead of printing a number. ok is
    pass_rate >= floor.

    With no personas at all, pass_rate is 0.0. An empty suite is not a pass.

    Args:
        session_factory: called with one persona dict, returns a session.
        personas: {name: {"turns": [...], "script": [...]}}.
        rubric: (name, predicate) pairs.
        floor: the pass rate this agent has to clear.
    """
    raise NotImplementedError
