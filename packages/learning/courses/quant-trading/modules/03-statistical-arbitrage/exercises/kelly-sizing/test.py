import unittest
from solution import calculate_kelly_fraction


class TestKellySizing(unittest.TestCase):
    def test_even_odds_sixty_percent_win(self):
        # p = 0.60, b = 1.0 (win $1 or lose $1)
        # Full Kelly = (0.6 * 2 - 1) / 1.0 = 0.20
        # Half Kelly (multiplier=0.5) = 0.10
        f = calculate_kelly_fraction(win_rate=0.60, win_loss_ratio=1.0, fraction_multiplier=0.5)
        self.assertAlmostEqual(f, 0.10, places=4)

    def test_negative_expectation(self):
        # p = 0.40, b = 1.0 -> Full Kelly < 0 -> returns 0.0
        f = calculate_kelly_fraction(win_rate=0.40, win_loss_ratio=1.0)
        self.assertEqual(f, 0.0)

    def test_asymmetric_payoff_with_cap(self):
        # p = 0.50, b = 3.0 (win $3 or lose $1)
        # Full Kelly = (0.5 * 4 - 1) / 3.0 = 1.0 / 3.0 = 0.3333
        # Full multiplier (1.0) with max_cap=0.25 -> clamped to 0.25
        f = calculate_kelly_fraction(
            win_rate=0.50, win_loss_ratio=3.0, fraction_multiplier=1.0, max_cap=0.25
        )
        self.assertEqual(f, 0.25)


if __name__ == "__main__":
    unittest.main()
