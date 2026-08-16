"""
Check your setup.

Five small functions over the one data structure this whole course is built on:
a list of chat messages. Nothing here is hard. It is here so that when something
in your toolchain is broken you find out in the first ten minutes rather than in
module four.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


def count_words(content: str | None) -> int:
    """
    Count the whitespace separated words in one message's content.

    Args:
        content: the text of a message, or None. None is not an error here. An
            assistant turn that only calls a tool carries no text at all, and
            you meet that in the next lesson, so every function that touches
            content has to survive it.

    Returns:
        The number of words. Runs of spaces, tabs and newlines count as a single
        separator, which is what str.split() with no argument already does for
        you. Both None and "" count zero.
    """
    raise NotImplementedError


def role_counts(messages: list[dict]) -> dict[str, int]:
    """
    How many messages each role sent.

    Args:
        messages: dicts shaped like {"role": "user", "content": "hello there"}.

    Returns:
        A dict mapping role to count, holding only the roles that actually
        appear. An empty list gives an empty dict.

        Do not pre-seed the roles you expect. A conversation can carry "system",
        "user", "assistant" and "tool" turns, and reporting {"tool": 0} for a
        conversation that never called a tool is a claim your caller will read
        as fact.
    """
    raise NotImplementedError


def last_user_message(messages: list[dict]) -> str | None:
    """
    The content of the most recent message whose role is "user".

    Search from the end of the list, not the start. By the time you are running
    an agent the list holds several user turns, the model's replies, and the
    results of every tool it called, and the question you are answering is the
    last one, never the first.

    Returns:
        The content of that message, or None when no message has role "user".
        Those two cases are deliberately not distinguished here, which is fine
        for a helper this size and would not be fine in an agent: a caller that
        needs to tell "nobody has asked anything yet" from "the last question
        arrived empty" has to be given the message, not its content.
    """
    raise NotImplementedError


def summarise_messages(messages: list[dict]) -> str:
    """
    One line describing a whole conversation.

    Returns:
        "N messages, M words", where N is the number of messages and M is the
        total word count across every message's content.

        Nothing is pluralised: a single message gives "1 messages, 4 words".
        Read that format twice. Matching a string exactly is most of what a test
        suite ever asks of you, and a wrong comma is a red test.

    Examples:
        >>> summarise_messages([{"role": "user", "content": "hello there"}])
        '1 messages, 2 words'
        >>> summarise_messages([])
        '0 messages, 0 words'
    """
    raise NotImplementedError


def first_reply(client) -> str:
    """
    Send one message to the model and return the text that comes back.

    Send a single user message with the content "Hello." and model="mock", then
    dig the assistant's text out of the response:

        response = client.chat.completions.create(
            model="mock",
            messages=[{"role": "user", "content": "Hello."}],
        )
        response.choices[0].message.content

    Both arguments have to be named. create() takes keyword arguments only, so
    passing the message list positionally raises TypeError before anything else
    happens. Real provider clients are the same, for the same reason: a call with
    a dozen optional parameters is unreadable when they are positional.

    The nesting on the way out is deep for a one line answer. That is not the
    mock being awkward. It is the shape every OpenAI compatible provider returns,
    and the next lesson is about why each layer exists.

    Args:
        client: a mockllm.MockClient. Call it exactly once.

    Returns:
        The assistant's reply text.
    """
    raise NotImplementedError
