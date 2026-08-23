"""
When to hand over.

The second slice. Everything from the last exercise is already here and already
written: Article, retrieve, parse_citations, answer, and the constants they use.
Read it, do not rewrite it.

Your work is the session on top of it: recognising a request for a person,
pushing back exactly once, and building a handoff that is worth receiving.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import re

from dataclasses import dataclass

from mockllm import cosine_similarity, embed_text


# Everything from here to the next banner is the previous exercise, finished.


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


# The new work starts here.


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
    """
    Decide whether the customer is asking for a person.

    Match any phrase in WANTS_HUMAN, case insensitively and on word boundaries,
    so "humanities" and "agents" do not count. Before you match, remove every
    phrase in NOT_A_REQUEST from the message, so a pasted log line reading
    "my user agent string is broken" is not read as a request for a person.

    A false positive here escalates a customer who never asked, which wrecks the
    deflection rate. A false negative traps somebody who did ask, which is worse.

    Args:
        message: one customer message.

    Returns:
        True when the message asks for a person.
    """
    raise NotImplementedError


def summarise(transcript: list[tuple[str, str]]) -> str:
    """
    Compress the conversation into the one line a human reads first.

    The transcript is a list of (role, text) pairs where role is "user" or
    "agent". An exchange is one user message, so count those and ignore the
    agent's.

    The line must contain the first user message and the number of exchanges,
    must fit on one line, and must survive an empty transcript. Collapse runs of
    whitespace in the quoted message so a pasted stack trace does not turn a one
    line summary into forty. Quote at most SUMMARY_LIMIT characters of it and
    end with "..." when you cut.

    Returns:
        A single line with no newline characters in it.
    """
    raise NotImplementedError


class TriageSession:
    """
    One conversation with one customer.

    The escalation contract, in full:

      - An ordinary message is answered with answer(). The reply text is
        recorded in `attempted` and any cited ids are added to `cited` without
        duplicates. An "answered" reply goes to the customer as written. A reply
        that grounded nothing goes no further: the customer gets
        OUT_OF_SCOPE_TEXT, action is "out_of_scope", and the model's draft still
        lands in `attempted` where a human can see it.
      - The first max_pushbacks requests for a person get a pushback: one more
        attempt at the answer, recorded in `attempted`, and no escalation.
      - The next one escalates. It builds a Handoff, sets `escalated`, and
        stores the handoff so later turns can return the same object.
      - Once escalated, every later message returns action "escalated" with that
        same Handoff and never calls the model again. The conversation belongs
        to a person now, and an agent still talking over them is worse than an
        agent that says nothing.

    Attributes:
        client: the model client, kept so handle() can pass it to answer().
        articles: the knowledge base.
        max_pushbacks: how many requests get a pushback before the next escalates.
        human_requests: how many times a person has been asked for.
        attempted: every reply sent, in order.
        cited: article ids cited so far, deduplicated, in first citation order.
        escalated: whether this session has handed over.
        transcript: (role, text) pairs, both sides, in order.
        handoff: the Handoff once escalated, otherwise None.
    """

    def __init__(self, client, articles: list[Article], max_pushbacks: int = 1) -> None:
        """
        Set up an empty session.

        Args:
            client: the model client, passed straight through to answer().
            articles: the knowledge base.
            max_pushbacks: how many requests for a person get a pushback before
                the next one hands over. 1 is the default and the right answer
                for most support desks. 0 means hand over on the first request,
                which is what you want for a queue where nobody bluffs.
        """
        raise NotImplementedError

    def handle(self, message: str) -> SessionReply:
        """
        Take one customer message and produce one reply.

        The order of operations matters:

          1. Append ("user", message) to the transcript first, so a handoff
             built on this turn counts this turn.
          2. If already escalated, return SessionReply(ALREADY_ESCALATED_TEXT,
             "escalated", self.handoff). No model call, no new handoff.
          3. If wants_human(message), increment human_requests, then either push
             back or escalate as described on the class.
          4. Otherwise answer the question.

        The pushback offers an article, and the article it offers is the best
        hit for the last message that was NOT a request for a person, falling
        back to this message when there is no earlier one. "Can I speak to a
        human" retrieves nothing useful on its own; the customer's actual
        question is still the question. Retrieve with k=1 and format
        PUSHBACK_WITH_ARTICLE with the hit's id and title, or PUSHBACK_PLAIN
        with queue=HUMAN_QUEUE when nothing comes back.

        The Handoff is built from what the session already knows: reason
        ESCALATION_REASON, summary summarise(self.transcript), attempted and
        article_ids copied out of the session, and transcript_turns counting the
        user messages. Copy the lists rather than aliasing them, or the payload
        keeps changing after you have handed it over.

        Append the agent's reply to the transcript on every path, so the log a
        human reads is the conversation and not half of it.

        Returns:
            A SessionReply. Its handoff is None on every action except
            "escalated".
        """
        raise NotImplementedError
