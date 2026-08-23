import unittest

from commons.common_functions import generate_technical_advice
from commons.technical_analysis import (
    TECHNICAL_GROUP_WEIGHTS,
    calculate_dimension_technical_score,
)


class TestTechnicalDimensionScoring(unittest.TestCase):
    def test_weights_cover_only_the_four_voting_dimensions(self):
        self.assertEqual(
            TECHNICAL_GROUP_WEIGHTS,
            {
                "trend_direction": 0.25,
                "momentum": 0.25,
                "volume": 0.25,
                "volatility": 0.25,
            },
        )

    def test_averages_indicators_inside_groups_before_combining_groups(self):
        signals = [
            [0, "MA", "", "Up"],
            [1, "MA cross", "", "Sideways"],
            [2, "RSI", "", "Strong Up"],
            [3, "Stochastic", "", "Up"],
        ]

        percentage, group_scores, count = calculate_dimension_technical_score(signals)

        self.assertEqual(group_scores, {"trend_direction": 2.5, "momentum": 3.5})
        self.assertEqual(count, 4)
        self.assertEqual(percentage, 75.0)

    def test_renormalizes_weights_when_voting_groups_are_missing(self):
        signals = [[0, "MA", "", "Strong Up"]]

        percentage, group_scores, count = calculate_dimension_technical_score(signals)

        self.assertEqual(group_scores, {"trend_direction": 4.0})
        self.assertEqual(count, 1)
        self.assertEqual(percentage, 100.0)

    def test_adx_is_metadata_only_and_never_contributes_to_score(self):
        signals = [[0, "ADX", "", "Strong Up"]]

        percentage, group_scores, count = calculate_dimension_technical_score(signals)

        self.assertEqual(group_scores, {})
        self.assertEqual(count, 0)
        self.assertEqual(percentage, 0.0)

        mixed_percentage, _, mixed_count = calculate_dimension_technical_score(
            [[0, "MA", "", "Up"], [1, "ADX", "", "Strong Up"]]
        )
        self.assertEqual(mixed_percentage, 75.0)
        self.assertEqual(mixed_count, 1)

    def test_empty_or_unknown_indicators_return_unknown_zero_score(self):
        for signals in ([], [[0, "Future Indicator", "", "Up"]]):
            with self.subTest(signals=signals):
                percentage, group_scores, count = calculate_dimension_technical_score(signals)
                self.assertEqual((percentage, group_scores, count), (0.0, {}, 0))

    def test_unknown_trend_is_neutral_inside_a_known_voting_group(self):
        display, trend, percentage = generate_technical_advice(
            [[0, "MA", "", "Unknown"]]
        )

        self.assertEqual(percentage, 50.0)
        self.assertEqual(trend, "Sideways")
        self.assertIn("50%", display)

    def test_existing_advice_return_shape_and_75_percent_example_remain(self):
        result = generate_technical_advice(
            [
                [0, "Stoch", "", "Strong Up"],
                [1, "RSI", "", "Up"],
                [2, "MA", "", "Up"],
                [3, "Cross", "", "Sideways"],
            ]
        )

        self.assertEqual(len(result), 3)
        self.assertEqual(result[1], "Strong Up")
        self.assertEqual(result[2], 75.0)


if __name__ == "__main__":
    unittest.main()
