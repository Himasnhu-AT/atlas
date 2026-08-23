"""
Sampling controls: worked solution.

Everything between the model's logits and a single token index. No model, no
network, no library: a softmax, two truncations and one draw from a seeded
random number generator.
"""

from __future__ import annotations

import math
import random

#: A logit of negative infinity is a token that cannot be sampled. exp() of it
#: is exactly 0.0, so it falls out of the softmax as a probability of zero with
#: no special case anywhere.
IMPOSSIBLE = -math.inf


def softmax(logits: list[float]) -> list[float]:
    """Logits to a distribution, computed the way it has to be computed."""
    if not logits:
        raise ValueError("softmax needs at least one logit")

    ceiling = max(logits)
    if ceiling == -math.inf:
        raise ValueError("every logit is IMPOSSIBLE, so there is nothing to sample")

    # The shift is what makes this safe. exp(1000) overflows; exp(1000 - 1001)
    # does not, and the constant cancels between numerator and denominator so
    # the answer is identical to the naive version that crashes.
    weights = [math.exp(value - ceiling) for value in logits]
    total = sum(weights)
    return [weight / total for weight in weights]


def apply_temperature(logits: list[float], temperature: float) -> list[float]:
    """Divide the logits, except at zero, where the limit is greedy decoding."""
    if not logits:
        raise ValueError("apply_temperature needs at least one logit")
    if temperature < 0.0:
        raise ValueError(f"temperature must be 0 or greater, got {temperature}")

    if temperature == 0.0:
        # index() returns the first match, so ties go to the lowest index. That
        # matches max() and matches argmax everywhere else, which is the whole
        # argument for choosing it.
        winner = logits.index(max(logits))
        return [0.0 if index == winner else IMPOSSIBLE for index in range(len(logits))]

    return [value / temperature for value in logits]


def _renormalise(probs: list[float], keep: set[int]) -> list[float]:
    """Zero everything outside `keep` and rescale what is left to sum to 1."""
    total = sum(probs[index] for index in keep)
    if total <= 0.0:
        raise ValueError("the kept tokens carry no probability mass")
    return [probs[index] / total if index in keep else 0.0 for index in range(len(probs))]


def top_k_filter(probs: list[float], k: int) -> list[float]:
    """Keep the k most likely tokens, positions intact, and renormalise."""
    if not probs:
        raise ValueError("top_k_filter needs at least one probability")
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")

    # Sort by probability descending, then by index ascending. Two keys rather
    # than reverse=True, because reverse=True would flip the tie break too and
    # make the winner depend on the order the list happened to arrive in.
    ranked = sorted(range(len(probs)), key=lambda index: (-probs[index], index))
    return _renormalise(probs, set(ranked[:k]))


def top_p_filter(probs: list[float], p: float) -> list[float]:
    """Keep the smallest prefix of the ranked tokens that covers p."""
    if not probs:
        raise ValueError("top_p_filter needs at least one probability")
    if not 0.0 < p <= 1.0:
        raise ValueError(f"p must be greater than 0 and at most 1, got {p}")

    ranked = sorted(range(len(probs)), key=lambda index: (-probs[index], index))

    keep: set[int] = set()
    running = 0.0
    for index in ranked:
        keep.add(index)
        running += probs[index]
        # Checked after adding, which is what keeps the crossing token. Check
        # before adding and p of 0.5 throws away a token holding 0.6.
        if running >= p:
            break

    return _renormalise(probs, keep)


def sample(probs: list[float], rng: random.Random) -> int:
    """One draw, one call to rng.random(), by walking the cumulative sum."""
    if not probs:
        raise ValueError("sample needs at least one probability")

    total = sum(probs)
    if total <= 0.0:
        raise ValueError("cannot sample from a distribution with no mass")

    # Scaling the draw by the total means a distribution that is only
    # approximately normalised, which is what floating point renormalisation
    # gives you, still samples correctly.
    threshold = rng.random() * total

    running = 0.0
    for index, probability in enumerate(probs):
        running += probability
        # Strictly greater. With >=, a token of probability 0.0 would match a
        # threshold that landed exactly on the boundary before it.
        if running > threshold:
            return index

    # Only reachable when rounding leaves `running` a hair under `threshold`.
    # Fall back to the last token that could legitimately have been drawn.
    return max(index for index, probability in enumerate(probs) if probability > 0.0)


def decode_step(
    logits: list[float],
    rng: random.Random,
    *,
    temperature: float = 1.0,
    top_k: int | None = None,
    top_p: float | None = None,
) -> int:
    """The five stages in order, with the two filters optional."""
    probs = softmax(apply_temperature(logits, temperature))

    if top_k is not None:
        probs = top_k_filter(probs, top_k)
    if top_p is not None:
        probs = top_p_filter(probs, top_p)

    return sample(probs, rng)
