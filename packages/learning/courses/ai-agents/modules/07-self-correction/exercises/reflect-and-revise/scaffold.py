"""
Reflection and its failure mode.

The three-call loop, bounded, plus the harness that tells you whether a pass
improved anything. The last function is the one that matters: it measures what
reflection did not do.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


def critique(client, draft: str, criteria: list[str]) -> list[str]:
    """
    Ask for findings against specific criteria.

    Args:
        client: a mockllm.MockClient. Call it exactly once.
        draft: the answer so far.
        criteria: what to judge it against, for example
            ["states its sources", "no unsupported numbers"].

    Returns:
        One finding per line of the reply, stripped, with blanks dropped. An
        empty list means nothing was found, and you have to be able to get an
        empty list back: a prompt asking "what is wrong with this?" makes a model
        find something wrong with a perfect answer, because you asked.

        A reply of exactly "NONE" (any case, any surrounding whitespace) is an
        empty list.

    Send one call:

        system: "List findings against the criteria, one per line. Reply NONE if
                 there are none."
        user:   "Criteria:\\n- <each criterion>\\n\\nDraft:\\n<draft>"
    """
    raise NotImplementedError


def revise(client, draft: str, findings: list[str]) -> str:
    """
    Rewrite the draft against the findings.

    Args:
        client: a mockllm.MockClient. Call it exactly once.
        draft: the answer so far.
        findings: what to fix.

    Returns:
        The revised text, stripped.

    Send one call:

        system: "Revise the draft to address every finding. Change nothing else."
        user:   "Findings:\\n- <each finding>\\n\\nDraft:\\n<draft>"

    "Change nothing else" is load-bearing. Without it each pass makes small
    changes to please the critic, and after four passes the answer has drifted
    away from the question.
    """
    raise NotImplementedError


def reflect(client, draft: str, criteria: list[str], max_passes: int = 3) -> dict:
    """
    Critique, revise, repeat, with a bound.

    Args:
        client: a mockllm.MockClient.
        draft: the starting answer.
        criteria: what the critique judges against.
        max_passes: the hard limit. Never let the model decide when to stop:
            "revise until you are satisfied" runs until agreeableness kicks in,
            which is unpredictable.

    Returns:
        A dict shaped:

            {
                "final": "...",
                "passes": 2,
                "history": [{"draft": ..., "findings": [...], "revised": ...}],
                "stopped": "clean" | "limit",
            }

        Stop early when a critique returns no findings; "stopped" is "clean"
        then and "limit" when max_passes ran out.

        `passes` counts completed critique-and-revise cycles. A first critique
        that finds nothing is zero passes, `final` is the original draft, and
        `history` holds the one entry that found nothing with `revised` equal to
        the draft it did not change.
    """
    raise NotImplementedError


def score(text: str, rubric: dict) -> int:
    """
    Score text against a fixed rubric, without a model.

    Deterministic on purpose. A comparison harness that asks a model whether the
    revision improved things has the problem this whole module is about.

    Args:
        text: the answer to score.
        rubric: maps a required substring to its point value, for example
            {"source:": 2, "approximately": 1}.

    Returns:
        The total for every substring present, case-insensitively. Each key
        scores at most once however often it appears.
    """
    raise NotImplementedError


def improvement(history: list[dict], rubric: dict) -> list[dict]:
    """
    Did each pass make it better, worse, or merely different?

    Args:
        history: the `history` from reflect().
        rubric: as above.

    Returns:
        One dict per pass, in order:

            {"pass": 1, "before": 2, "after": 4, "verdict": "better"}

        `verdict` is "better" when the score rose, "worse" when it fell, and
        "unchanged" when it did not move — including when the text changed and
        the score did not, which is the drift this exists to expose.
    """
    raise NotImplementedError
