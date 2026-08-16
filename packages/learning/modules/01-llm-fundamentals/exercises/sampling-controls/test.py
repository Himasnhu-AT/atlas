"""
Tests for: sampling controls.

These assert on distributions rather than on drawn tokens wherever they can, so
a sampler that happens to return a plausible index does not pass.

Run with `python3 test.py`.
"""

from __future__ import annotations

import random
import unittest

from solution import (
    IMPOSSIBLE,
    apply_temperature,
    decode_step,
    sample,
    softmax,
    top_k_filter,
    top_p_filter,
)

#: Six tokens, ranked and well separated, standing in for a real vocabulary.
LOGITS = [4.0, 3.0, 2.0, 1.0, 0.0, -1.0]


class CountingRandom(random.Random):
    """A seeded Random that records how many numbers were taken from it."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.draws = 0

    def random(self) -> float:
        self.draws += 1
        return super().random()


class TestSoftmaxAndTemperature(unittest.TestCase):
    def test_softmax_is_a_distribution_in_rank_order(self):
        probs = softmax(LOGITS)
        self.assertAlmostEqual(sum(probs), 1.0, places=9)
        self.assertEqual(
            probs,
            sorted(probs, reverse=True),
            "softmax is monotone: a higher logit must not become a lower probability",
        )

    def test_softmax_is_shift_invariant(self):
        shifted = softmax([value + 17.0 for value in LOGITS])
        for got, want in zip(shifted, softmax(LOGITS)):
            self.assertAlmostEqual(got, want, places=9)

    def test_softmax_survives_huge_logits(self):
        probs = softmax([1000.0, 1001.0])
        self.assertAlmostEqual(sum(probs), 1.0, places=9)
        self.assertAlmostEqual(
            probs[1],
            0.7310585786300049,
            places=9,
            msg="subtract max(logits) before exponentiating, or exp() overflows",
        )

    def test_softmax_turns_impossible_into_exactly_zero(self):
        probs = softmax([0.0, IMPOSSIBLE])
        self.assertEqual(probs, [1.0, 0.0])

    def test_temperature_one_leaves_the_logits_alone(self):
        self.assertEqual(apply_temperature(LOGITS, 1.0), LOGITS)

    def test_temperature_moves_mass_between_the_head_and_the_tail(self):
        base = softmax(apply_temperature(LOGITS, 1.0))
        cold = softmax(apply_temperature(LOGITS, 0.5))
        hot = softmax(apply_temperature(LOGITS, 2.0))
        self.assertGreater(
            cold[0], base[0], "dividing by 0.5 doubles every gap, so the leader pulls ahead"
        )
        self.assertLess(cold[-1], base[-1])
        self.assertLess(hot[0], base[0])
        self.assertGreater(
            hot[-1], base[-1], "a high temperature is the tail getting a real share"
        )

    def test_temperature_zero_is_a_one_hot_on_the_argmax(self):
        self.assertEqual(
            softmax(apply_temperature(LOGITS, 0.0)),
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "temperature 0 is greedy decoding: all the mass on the argmax",
        )
        self.assertEqual(softmax(apply_temperature([1.0, 9.0, 2.0], 0.0)), [0.0, 1.0, 0.0])

    def test_temperature_zero_breaks_ties_toward_the_lower_index(self):
        probs = softmax(apply_temperature([5.0, 5.0, 1.0], 0.0))
        self.assertEqual(
            probs, [1.0, 0.0, 0.0], "a tie at temperature 0 goes to the lower index"
        )

    def test_unusable_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            softmax([])
        with self.assertRaises(ValueError):
            apply_temperature([], 1.0)
        with self.assertRaises(ValueError):
            apply_temperature(LOGITS, -0.5)


class TestTruncation(unittest.TestCase):
    def setUp(self):
        self.probs = [0.5, 0.25, 0.15, 0.06, 0.03, 0.01]

    def test_top_k_keeps_exactly_k_tokens_in_place(self):
        self.assertEqual(sum(1 for value in top_k_filter(self.probs, 3) if value > 0.0), 3)
        self.assertEqual(
            top_k_filter(self.probs, 2)[2:],
            [0.0, 0.0, 0.0, 0.0],
            "positions are preserved: index i must still mean token i",
        )

    def test_top_k_renormalises(self):
        self.assertAlmostEqual(
            sum(top_k_filter(self.probs, 3)),
            1.0,
            places=9,
            msg="the survivors are a distribution, so divide them by their own total",
        )

    def test_top_k_of_one_is_greedy(self):
        self.assertEqual(top_k_filter(self.probs, 1), [1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    def test_top_k_breaks_ties_toward_the_lower_index(self):
        filtered = top_k_filter([0.4, 0.3, 0.3], 2)
        self.assertGreater(filtered[1], 0.0, "the tie on the boundary goes to index 1")
        self.assertEqual(filtered[2], 0.0)

    def test_top_k_at_the_boundaries(self):
        wide = top_k_filter(self.probs, 99)
        self.assertEqual(
            sum(1 for value in wide if value > 0.0),
            len(self.probs),
            "a k larger than the vocabulary keeps all of it rather than raising",
        )
        with self.assertRaises(ValueError):
            top_k_filter(self.probs, 0)

    def test_top_p_keeps_the_token_that_crosses_the_threshold(self):
        # 0.5 then 0.25 reaches 0.75, so p of 0.7 stops on the second token and
        # keeps it. Dropping it would leave 0.5 of mass against a 0.7 request.
        filtered = top_p_filter(self.probs, 0.7)
        self.assertGreater(filtered[1], 0.0, "the crossing token is kept, not dropped")
        self.assertEqual(filtered[2], 0.0)

    def test_top_p_kept_mass_is_at_least_p(self):
        for p in (0.1, 0.4, 0.75, 0.9):
            with self.subTest(p=p):
                kept = sum(
                    original
                    for original, value in zip(self.probs, top_p_filter(self.probs, p))
                    if value > 0.0
                )
                self.assertGreaterEqual(round(kept, 9), p)

    def test_top_p_below_the_leader_still_keeps_the_leader(self):
        filtered = top_p_filter(self.probs, 0.4)
        self.assertEqual(
            filtered,
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "p smaller than the top token keeps that one token, never zero of them",
        )

    def test_top_p_renormalises_and_p_of_one_keeps_everything(self):
        self.assertAlmostEqual(sum(top_p_filter(self.probs, 0.6)), 1.0, places=9)
        whole = top_p_filter(self.probs, 1.0)
        self.assertEqual(sum(1 for value in whole if value > 0.0), len(self.probs))

    def test_top_p_rejects_an_out_of_range_p(self):
        for bad in (0.0, -0.2, 1.5):
            with self.subTest(p=bad):
                with self.assertRaises(ValueError):
                    top_p_filter(self.probs, bad)

    def test_the_filters_compose(self):
        # top-k leaves three tokens at 0.5556, 0.2778, 0.1667; top-p of 0.8
        # then stops on the second of those.
        filtered = top_p_filter(top_k_filter(self.probs, 3), 0.8)
        self.assertEqual(sum(1 for value in filtered if value > 0.0), 2)
        self.assertAlmostEqual(sum(filtered), 1.0, places=9)


class TestSamplingAndComposition(unittest.TestCase):
    def test_a_one_hot_distribution_always_returns_its_token(self):
        rng = random.Random(1)
        self.assertEqual({sample([0.0, 1.0, 0.0], rng) for _ in range(50)}, {1})

    def test_a_zero_probability_token_is_never_drawn(self):
        rng = random.Random(2)
        drawn = {sample([0.5, 0.0, 0.5], rng) for _ in range(500)}
        self.assertNotIn(1, drawn, "a token with no mass must never come back")
        self.assertEqual(drawn, {0, 2})

    def test_the_same_seed_gives_the_same_draws(self):
        probs = [0.4, 0.35, 0.25]

        def run() -> list[int]:
            rng = random.Random(9)
            return [sample(probs, rng) for _ in range(20)]

        self.assertEqual(run(), run(), "a seeded generator must replay exactly")

    def test_sample_takes_exactly_one_number_from_the_generator(self):
        rng = CountingRandom(3)
        sample([0.2, 0.3, 0.5], rng)
        self.assertEqual(
            rng.draws,
            1,
            "one call to rng.random(): a redraw loop is neither reproducible nor bounded",
        )

    def test_draw_frequencies_track_the_distribution(self):
        probs = [0.7, 0.2, 0.1]
        rng = random.Random(11)
        counts = [0, 0, 0]
        for _ in range(4000):
            counts[sample(probs, rng)] += 1
        for index, want in enumerate(probs):
            with self.subTest(token=index):
                self.assertAlmostEqual(
                    counts[index] / 4000,
                    want,
                    delta=0.03,
                    msg="the draw should follow the cumulative distribution",
                )

    def test_decode_step_at_temperature_zero_ignores_the_generator(self):
        drawn = {decode_step(LOGITS, random.Random(seed), temperature=0.0) for seed in range(20)}
        self.assertEqual(drawn, {0}, "greedy decoding does not consult the sampler's luck")

    def test_decode_step_with_top_k_one_is_greedy(self):
        rng = random.Random(4)
        drawn = {decode_step(LOGITS, rng, temperature=1.5, top_k=1) for _ in range(50)}
        self.assertEqual(drawn, {0})

    def test_decode_step_honours_the_nucleus(self):
        rng = random.Random(5)
        drawn = {decode_step(LOGITS, rng, top_p=0.8) for _ in range(600)}
        self.assertTrue(
            drawn.issubset({0, 1}),
            f"top-p of 0.8 covers the first two tokens, but {sorted(drawn)} came back",
        )

    def test_decode_step_defaults_to_the_full_distribution(self):
        rng = random.Random(6)
        drawn = {decode_step(LOGITS, rng) for _ in range(3000)}
        self.assertEqual(
            drawn,
            set(range(len(LOGITS))),
            "with no filters and temperature 1.0 every token is reachable",
        )

    def test_temperature_reaches_further_down_the_list(self):
        cold = [decode_step(LOGITS, random.Random(s), temperature=0.5) for s in range(400)]
        hot = [decode_step(LOGITS, random.Random(s), temperature=2.0) for s in range(400)]
        self.assertGreater(
            sum(1 for token in hot if token >= 3),
            sum(1 for token in cold if token >= 3),
            "a higher temperature should draw from the tail more often",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
