"""
Self-consistency.

Sample the same question several times, take the answer that comes back most
often, and keep the disagreement. The mode is the easy part; refusing to sound
confident about a three-two split is the part with value.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


def normalise(answer: str) -> str:
    """
    Reduce an answer to a form two answers can be equal in.

    "42", "42.", "The answer is 42" and " 42 " are one answer four ways, and
    counted raw they give four groups of one and no majority.

    Args:
        answer: one sampled reply.

    Returns:
        The answer, lowercased, stripped, with surrounding punctuation removed
        (.,!?;: and quotes), and internal runs of whitespace collapsed to one
        space.

        If the result contains exactly one run of digits and nothing
        substantial around it, return just the digits. That is what makes "the
        answer is 42" and "42" agree.

        "Substantial" means a word longer than three characters that is not a
        carrier word. Carrier words hold a number without adding meaning to it:
        answer, approximately, about, roughly, around, that, this, there, value,
        result, total. So "the answer is 42" reduces to "42", and "42 units were
        recalled" does not, because "units" and "recalled" are saying something.

        This normaliser is doing real work and it is also where the method
        quietly breaks: too loose and genuinely different answers collapse into
        agreement you did not earn. Report what you chose rather than pretending
        there was no choice.
    """
    raise NotImplementedError


def sample(client, question: str, n: int = 5, temperature: float = 0.7) -> list[str]:
    """
    Ask the same question n times.

    Args:
        client: a mockllm.MockClient. Call it exactly n times.
        question: what to ask.
        n: how many samples.
        temperature: passed on every call.

    Returns:
        The raw replies, in order, stripped.

    Send each call as:

        user: "<question>"

    with `temperature=temperature` as a keyword argument, so the request records
    it. This is the one place where turning temperature UP is the correct move:
    you are deliberately buying variance in order to measure it. At 0 every
    sample is identical and you have paid n times for one answer.
    """
    raise NotImplementedError


def tally(answers: list[str]) -> list[tuple[str, int]]:
    """
    Count normalised answers, most common first.

    Args:
        answers: raw replies.

    Returns:
        (normalised answer, count) pairs, sorted by count descending and then by
        the answer alphabetically, so a tie is broken the same way every run. A
        tally that reorders itself between runs makes the mode nondeterministic,
        which is a strange property for a method whose point is stability.

        Empty input gives [].
    """
    raise NotImplementedError


def agree(answers: list[str], split_threshold: float = 0.8) -> dict:
    """
    The answer, and how much to trust it.

    Args:
        answers: raw replies.
        split_threshold: the share the winner needs to count as agreement.

    Returns:
        A dict shaped:

            {
                "answer": "42",
                "agreement": 0.6,
                "distribution": [("42", 3), ("43", 2)],
                "confidence": "split",
                "escalate": True,
            }

        `agreement` is the winner's share of the samples, 0.0 for no samples.

        `confidence` is:
          - "high"    the winner's share is at or above split_threshold
          - "scatter" every answer is different AND there are at least three
                      samples, which usually means the question is
                      underspecified or the information is not in the context
          - "split"   anything else

        `escalate` is True for anything that is not "high". Reporting a
        three-two split as a confident answer throws away the one thing the
        method produced, and it is the most common way this gets misused.

        No samples gives answer "", agreement 0.0, confidence "scatter" and
        escalate True: nothing is not an answer.
    """
    raise NotImplementedError


def suits_self_consistency(answers: list[str], max_words: int = 12) -> bool:
    """
    Is this the kind of answer the method can work on?

    Self-consistency wants an answer that can be compared: a number, a category,
    a yes or no, a short span. It does not work on long generated prose, because
    two summaries are never equal and a normaliser that makes them equal is
    measuring nothing.

    Args:
        answers: raw replies.
        max_words: the longest an answer may be and still be comparable.

    Returns:
        True when every answer is at most max_words words. False for empty
        input, because there is nothing to compare.
    """
    raise NotImplementedError
