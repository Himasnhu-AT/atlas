"""
Chain of verification.

Take the answer apart, ask about each piece as though you had never seen the
rest, and reassemble. The independence is in what you leave OUT of the
verification prompt, which is one line to get wrong.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

# Words that mark a sentence as a judgement rather than a checkable claim.
JUDGEMENT_WORDS = [
    "significant",
    "impressive",
    "important",
    "best",
    "excellent",
    "poor",
    "clearly",
    "obviously",
]


def decompose(draft: str) -> list[dict]:
    """
    Split a draft into individual claims, and say which are checkable.

    Args:
        draft: the answer, as sentences separated by ". ".

    Returns:
        One dict per claim, in order:

            {"text": "The 2019 model was released in March", "checkable": True}

    Three rules, and the third is where most implementations go wrong:

      - ONE ASSERTION EACH. A sentence joined by " and " is two claims, and
        verifying it as one gives a single verdict on something that could be
        half right. Split on " and " as well as on sentence boundaries.
      - CLAIMS STAND ALONE. A fragment shorter than 12 characters after
        stripping is not a claim; drop it.
      - NOT EVERYTHING IS A CLAIM. A sentence containing any JUDGEMENT_WORD is
        an opinion, and running it through a fact check produces a
        confident-sounding verdict on a matter of taste. Mark it
        `checkable: False` rather than dropping it: it still belongs in the
        final answer.

    Trailing full stops are stripped from `text`. Empty input gives [].
    """
    raise NotImplementedError


def question_for(claim: str) -> str:
    """
    Turn a claim into a question answerable without knowing the claim.

    Args:
        claim: one checkable claim.

    Returns:
        The question. Keep it simple: "What is true about: <claim>?" is enough,
        because the work is not done by clever phrasing. It is done by what the
        verification call does not receive.
    """
    raise NotImplementedError


def verify(client, question: str) -> str:
    """
    Answer a verification question in a fresh context.

    THIS IS THE STEP THAT DOES THE WORK, and the way to get nothing out of the
    whole pattern is to include the draft here. Send the question and nothing
    else: no draft, no other claims, no reasoning. If the answer comes back
    different from the claim, that difference is information, because the two
    were produced from different inputs.

    Args:
        client: a mockllm.MockClient. Call it exactly once.
        question: from question_for.

    Returns:
        The reply, stripped.

    Send one call:

        system: "Answer the question directly and briefly."
        user:   "<question>"
    """
    raise NotImplementedError


def reconcile(claim: str, answer: str) -> str:
    """
    Compare an independent answer to the original claim.

    Args:
        claim: what the draft asserted.
        answer: what the independent verification came back with.

    Returns:
        One of "supported", "contradicted", "unsupported".

        "unsupported" when the answer contains "unknown", "not sure", "no
        information" or "cannot" (case-insensitively). Check this FIRST: an
        answer saying it does not know is not evidence either way, and treating
        it as a contradiction deletes true claims.

        "supported" when every alphanumeric word of the claim longer than three
        characters appears in the answer, case-insensitively.

        "contradicted" otherwise.

        The three are deliberately kept apart. Unsupported is not contradicted:
        the claim may be perfectly true and simply outside what the verification
        could reach, and collapsing the two silently loses good content.
    """
    raise NotImplementedError


def run_verification(client, draft: str) -> dict:
    """
    The whole pattern, end to end.

    Args:
        client: a mockllm.MockClient. One call per checkable claim, in order.
        draft: the answer to verify.

    Returns:
        A dict shaped:

            {
                "claims": [{"text": ..., "checkable": ..., "verdict": ...,
                            "answer": ...}],
                "final": "...",
                "counts": {"supported": 2, "contradicted": 1,
                           "unsupported": 0, "skipped": 1},
            }

        A claim that is not checkable has verdict "skipped", answer "", and
        costs no model call.

        `final` is the claims that survived, joined by ". " with a trailing full
        stop: everything supported, everything not checkable, and everything
        unsupported marked with a trailing " [unverified]". Contradicted claims
        are dropped.

        Keeping the unsupported ones with a marker rather than deleting them is
        the same decision as quarantining a bad row instead of dropping it: the
        caller can see what was not checked and decide.
    """
    raise NotImplementedError
