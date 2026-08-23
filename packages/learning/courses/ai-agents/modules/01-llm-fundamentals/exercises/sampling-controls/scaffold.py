"""
Sampling controls.

The model stops at a vector of logits. Everything after that, the softmax, the
temperature, the truncations and the draw, is ordinary code with no model in it,
and this is that code. A fixed vocabulary of six tokens stands in for the hundred
thousand a real one has; nothing else is simplified.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import math
import random

#: A logit of negative infinity is a token that cannot be sampled. exp() of it
#: is exactly 0.0, so it survives a softmax as a probability of zero rather than
#: as a special case you have to remember to check for.
IMPOSSIBLE = -math.inf


def softmax(logits: list[float]) -> list[float]:
    """
    Turn logits into a probability distribution.

    Exponentiate each logit and divide by the total, so the result is
    non-negative and sums to 1.0.

    Subtract max(logits) from every logit before exponentiating. This is not an
    optimisation and it is not optional: math.exp(1000) raises OverflowError,
    and real logits get that large. Shifting every logit by the same constant
    leaves the answer unchanged, because the constant cancels between the
    numerator and the denominator.

    An entry of IMPOSSIBLE comes out as exactly 0.0.

    Args:
        logits: at least one score, at least one of them finite.

    Returns:
        A new list of the same length, summing to 1.0.

    Raises:
        ValueError: logits is empty, or every entry is IMPOSSIBLE.
    """
    raise NotImplementedError


def apply_temperature(logits: list[float], temperature: float) -> list[float]:
    """
    Rescale logits before the softmax.

    Divide every logit by the temperature. Below 1.0 this widens the gaps
    between logits and concentrates the distribution; above 1.0 it narrows them
    and spreads the distribution out.

    Temperature 0 is a branch, not a division. It means greedy decoding, so
    return a list where the winning logit is 0.0 and every other entry is
    IMPOSSIBLE. Passing that through softmax() gives an exact one-hot.

    Ties at temperature 0 go to the LOWEST index. Something has to break them
    and max() already works that way, so anything else is a surprise.

    Args:
        logits: at least one score.
        temperature: 0.0 or greater.

    Returns:
        A new list of the same length.

    Raises:
        ValueError: logits is empty, or temperature is negative.
    """
    raise NotImplementedError


def top_k_filter(probs: list[float], k: int) -> list[float]:
    """
    Keep the k most likely tokens and renormalise.

    Every other position becomes 0.0, and the survivors are divided by their own
    total so the result still sums to 1.0. Renormalising is what makes this a
    distribution rather than a list of numbers that happen to be small.

    Positions are preserved: the return value is the same length as `probs` and
    index i still means token i. Returning only the survivors would lose the
    mapping from position to token, which is the one thing the caller needs.

    Ties on the k-th boundary go to the lowest index.

    Args:
        probs: a distribution. k of them will survive.
        k: how many to keep. k greater than len(probs) keeps everything.

    Returns:
        A new list of the same length, summing to 1.0.

    Raises:
        ValueError: probs is empty, k is less than 1, or the kept mass is 0.0.
    """
    raise NotImplementedError


def top_p_filter(probs: list[float], p: float) -> list[float]:
    """
    Keep the smallest set of tokens whose probability sums to at least p.

    Walk the tokens from most to least likely, accumulating. Keep each one you
    walk over, and stop once the running total reaches p. Everything you did not
    walk over becomes 0.0, and the survivors are renormalised.

    The token that crosses p is KEPT, not dropped. So the mass you keep is
    always at least p, and the most likely token always survives however large
    its own probability is. Dropping the crossing token instead means p of 0.5
    discards a token holding 0.6 of the mass and leaves you renormalising an
    empty set.

    Ties are ordered by index, lowest first, so the result does not depend on
    how the sort happened to be implemented.

    Args:
        probs: a distribution.
        p: greater than 0.0 and no more than 1.0.

    Returns:
        A new list of the same length, summing to 1.0.

    Raises:
        ValueError: probs is empty, p is out of range, or the total mass is 0.0.
    """
    raise NotImplementedError


def sample(probs: list[float], rng: random.Random) -> int:
    """
    Draw one token index from a distribution.

    Take a single number from rng.random(), scale it by the total mass, and walk
    the probabilities accumulating until the running total passes it. Return the
    index you stopped at.

    Call rng.random() exactly once. A loop that redraws until it likes the
    answer works, and it makes the function's cost depend on the distribution
    and its output impossible to reproduce from a seed.

    A token with probability 0.0 must never be returned. Walking with a strict
    comparison on the running total gives you that for free.

    Args:
        probs: a distribution. Need not be exactly normalised.
        rng: a seeded random.Random, so tests can reproduce a draw.

    Returns:
        An index into `probs`.

    Raises:
        ValueError: probs is empty or its total is 0.0.
    """
    raise NotImplementedError


def decode_step(
    logits: list[float],
    rng: random.Random,
    *,
    temperature: float = 1.0,
    top_k: int | None = None,
    top_p: float | None = None,
) -> int:
    """
    One full decoding step: logits in, one token index out.

    The pipeline, in this order:

        1. apply_temperature on the logits
        2. softmax
        3. top_k_filter, when top_k is not None
        4. top_p_filter, when top_p is not None
        5. sample

    Temperature first is the part that matters. It is what decides how much mass
    the tail carries, and the truncations can only work with the distribution
    they are handed. Whether top-k or top-p runs first is a convention and
    providers document their own; this pipeline runs k then p.

    The defaults are the identity: temperature 1.0 with neither filter samples
    straight from the model's own distribution.

    Args:
        logits: the model's raw scores.
        rng: a seeded random.Random.
        temperature: 0.0 for greedy decoding.
        top_k: keep this many tokens, or None to skip the filter.
        top_p: keep this much mass, or None to skip the filter.

    Returns:
        An index into `logits`.
    """
    raise NotImplementedError
