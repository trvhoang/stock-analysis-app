"""Statistical primitives retained for exploratory V4 selection only."""

import unittest

from backtest_engine.validation import (
    calculate_deflated_sharpe,
    calculate_unannualized_sharpe,
    moving_block_permutation_test,
)


class BacktestValidationTests(unittest.TestCase):
    def test_unannualized_sharpe_uses_sample_standard_deviation(self):
        self.assertAlmostEqual(
            calculate_unannualized_sharpe((1.0, 2.0, 3.0)),
            2.0,
        )

    def test_dsr_compares_one_treatment_against_exact_two_sharpe_family(self):
        returns = (1.0, -0.5, 1.5, 0.5, -0.25)
        trials = (
            calculate_unannualized_sharpe(returns),
            calculate_unannualized_sharpe((0.5, -0.5, 0.5, 0.25, -0.25)),
        )

        score = calculate_deflated_sharpe(returns, trials)

        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_centered_moving_block_result_is_deterministic_information(self):
        first = moving_block_permutation_test(
            (1.0, -0.5, 1.5, 0.5, -0.25, 0.75, -0.4, 0.9, -0.1, 0.3,
             0.2, -0.3, 1.1, -0.2, 0.4, 0.6, -0.6, 0.8, -0.7, 0.5, 0.1),
            count=100,
            seed=42,
            block_size=20,
        )
        second = moving_block_permutation_test(
            (1.0, -0.5, 1.5, 0.5, -0.25, 0.75, -0.4, 0.9, -0.1, 0.3,
             0.2, -0.3, 1.1, -0.2, 0.4, 0.6, -0.6, 0.8, -0.7, 0.5, 0.1),
            count=100,
            seed=42,
            block_size=20,
        )

        self.assertEqual(first.p_value, second.p_value)
        self.assertEqual(first.null_sharpes, second.null_sharpes)


if __name__ == "__main__":
    unittest.main()

