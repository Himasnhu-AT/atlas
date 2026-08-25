import unittest
from solution import price_binomial_tree


class TestBinomialTree(unittest.TestCase):
    def test_european_convergence_to_black_scholes(self):
        # S=100, K=100, tau=1.0, r=0.05, sigma=0.20
        # Black-Scholes call is 10.4506
        tree_price = price_binomial_tree(
            spot=100.0,
            strike=100.0,
            tau=1.0,
            r=0.05,
            sigma=0.20,
            steps=200,
            is_call=True,
            is_american=False,
        )
        self.assertAlmostEqual(tree_price, 10.4506, delta=0.05)

    def test_american_put_early_exercise_premium(self):
        # Deep ITM Put: S=50, K=100, tau=1.0, r=0.10, sigma=0.20
        # American put price must be >= intrinsic (50.0)
        # European put is less due to time value of money discounting the strike
        euro_put = price_binomial_tree(
            50.0, 100.0, 1.0, 0.10, 0.20, steps=100, is_call=False, is_american=False
        )
        amer_put = price_binomial_tree(
            50.0, 100.0, 1.0, 0.10, 0.20, steps=100, is_call=False, is_american=True
        )

        self.assertGreater(amer_put, euro_put)
        self.assertGreaterEqual(amer_put, 50.0)


if __name__ == "__main__":
    unittest.main()
