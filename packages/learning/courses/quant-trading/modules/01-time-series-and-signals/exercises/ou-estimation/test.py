import unittest
from quantlib import generate_synthetic_ou
from solution import estimate_ou_parameters


class TestOUEstimation(unittest.TestCase):
    def test_ou_calibration_on_synthetic_path(self):
        dt = 1.0 / 252.0
        known_theta = 5.0
        known_mu = 100.0
        known_sigma = 2.0

        # Generate long path with known parameters
        path = generate_synthetic_ou(
            x0=100.0,
            theta=known_theta,
            mu=known_mu,
            sigma=known_sigma,
            n_steps=2000,
            dt=dt,
            seed=123,
        )

        params = estimate_ou_parameters(path, dt=dt)
        self.assertAlmostEqual(params["mu"], known_mu, delta=2.0)
        self.assertAlmostEqual(params["theta"], known_theta, delta=1.5)
        self.assertAlmostEqual(params["sigma"], known_sigma, delta=0.5)
        self.assertAlmostEqual(params["half_life"], 0.693147 / params["theta"], places=4)

    def test_non_reverting_series_raises(self):
        # A straight upward trending line has b >= 1
        trend = [float(i) for i in range(100)]
        with self.assertRaises(ValueError):
            estimate_ou_parameters(trend, dt=1.0)


if __name__ == "__main__":
    unittest.main()
