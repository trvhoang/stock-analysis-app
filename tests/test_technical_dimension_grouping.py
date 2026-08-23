import unittest

import pandas as pd

from commons.technical_analysis import (
    TECHNICAL_DIMENSIONS,
    TECHNICAL_INDICATOR_METADATA,
    calculate_trend_correlation,
    group_technical_indicators,
)


class TestTechnicalDimensionGrouping(unittest.TestCase):
    def test_registry_matches_resolved_dimensions_and_adx_no_vote_role(self):
        self.assertEqual(
            TECHNICAL_DIMENSIONS,
            {
                "trend_direction": ("MA", "MA cross"),
                "momentum": ("RSI", "Stochastic"),
                "trend_strength": ("ADX",),
                "volume": ("OBV",),
                "volatility": ("ATR", "Bollinger"),
            },
        )
        self.assertEqual(
            TECHNICAL_INDICATOR_METADATA["ADX"],
            {"dimension": "trend_strength", "votes": False},
        )

    def test_groups_aliases_without_mutating_signal_records(self):
        signals = [
            [2, "MA", "", "Up"],
            [3, "MA cross", "", "Down"],
            [1, "RSI14", "", "Sideways"],
            [0, "Stoch", "", "Up"],
            [4, "ADX", "", "Sideways"],
            [5, "OBV", "", "Up"],
            [6, "ATR", "", "Down"],
            [7, "Bollinger Bands", "", "Sideways"],
            [8, "Future Indicator", "", "Unknown"],
        ]
        original = [row.copy() for row in signals]

        grouped = group_technical_indicators(signals)

        self.assertEqual(grouped["trend_direction"], signals[:2])
        self.assertEqual(grouped["momentum"], [signals[2], signals[3]])
        self.assertEqual(grouped["trend_strength"], [signals[4]])
        self.assertEqual(grouped["volume"], [signals[5]])
        self.assertEqual(grouped["volatility"], signals[6:8])
        self.assertEqual(grouped["unassigned"], [signals[8]])
        self.assertEqual(signals, original)

    def test_empty_and_duplicate_inputs_preserve_shape_and_order(self):
        self.assertEqual(
            group_technical_indicators([]),
            {
                "trend_direction": [],
                "momentum": [],
                "trend_strength": [],
                "volume": [],
                "volatility": [],
                "unassigned": [],
            },
        )

        signals = [
            [0, "MA", "", "Up"],
            [1, "MA", "", "Down"],
        ]
        self.assertEqual(group_technical_indicators(signals)["trend_direction"], signals)

    def test_correlation_maps_trend_keys_to_existing_score_scale(self):
        trends = pd.DataFrame(
            {
                "MA": ["Strong Down", "Down", "Sideways", "Up", "Strong Up"],
                "RSI": ["Strong Down", "Down", "Sideways", "Up", "Strong Up"],
                "ADX": ["Sideways", "Up", "Strong Up", "Up", "Sideways"],
            }
        )

        correlation = calculate_trend_correlation(trends)

        self.assertEqual(list(correlation.index), ["MA", "RSI", "ADX"])
        self.assertEqual(list(correlation.columns), ["MA", "RSI", "ADX"])
        self.assertAlmostEqual(correlation.loc["MA", "RSI"], 1.0)
        self.assertAlmostEqual(correlation.loc["MA", "MA"], 1.0)

    def test_correlation_handles_unknown_values_and_empty_input(self):
        trends = pd.DataFrame(
            {
                "MA": ["Unknown", "Up", "Down"],
                "OBV": ["Sideways", "Up", "Down"],
                "constant": ["Sideways", "Sideways", "Sideways"],
            }
        )

        correlation = calculate_trend_correlation(trends)

        self.assertEqual(correlation.shape, (3, 3))
        self.assertTrue(pd.isna(correlation.loc["constant", "MA"]))
        self.assertTrue(calculate_trend_correlation(pd.DataFrame()).empty)


if __name__ == "__main__":
    unittest.main()
