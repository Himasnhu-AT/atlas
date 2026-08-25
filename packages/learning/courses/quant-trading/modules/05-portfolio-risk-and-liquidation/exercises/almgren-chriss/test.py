import unittest
from solution import almgren_chriss_trajectory


class TestAlmgrenChriss(unittest.TestCase):
    def test_risk_neutral_twap_limit(self):
        # lambda_risk = 0.0 -> straight line from 1000 to 0
        traj = almgren_chriss_trajectory(
            total_shares=1000.0,
            num_intervals=4,
            tau=1.0,
            sigma=0.20,
            eta=0.01,
            lambda_risk=0.0,
        )
        self.assertEqual(len(traj), 5)
        self.assertEqual(traj, [1000.0, 750.0, 500.0, 250.0, 0.0])

    def test_risk_averse_front_loading(self):
        # High risk aversion -> rapid early selling (lower remaining inventory than TWAP)
        traj = almgren_chriss_trajectory(
            total_shares=1000.0,
            num_intervals=4,
            tau=1.0,
            sigma=0.20,
            eta=0.01,
            lambda_risk=1.0,
        )
        self.assertEqual(len(traj), 5)
        self.assertEqual(traj[0], 1000.0)
        self.assertEqual(traj[-1], 0.0)
        # At interval 1, remaining shares should be strictly less than 750 (TWAP)
        self.assertLess(traj[1], 750.0)


if __name__ == "__main__":
    unittest.main()
