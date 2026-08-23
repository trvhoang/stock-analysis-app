import unittest

import pandas as pd

from commons.technical_analysis import (
    ADX_LOW_TREND_MULTIPLIER,
    ADX_TREND_THRESHOLD,
    apply_adx_gate,
    calculate_dimension_technical_score,
    get_latest_adx_value,
)


class TestAdxGating(unittest.TestCase):
    def test_gate_constants_match_resolved_starting_rule(self):
        self.assertEqual(ADX_TREND_THRESHOLD, 20.0)
        self.assertEqual(ADX_LOW_TREND_MULTIPLIER, 0.5)

    def test_adx_below_20_halves_only_trend_direction(self):
        scores = {"trend_direction": 3.0, "momentum": 4.0}

        gated = apply_adx_gate(scores, 19.9)

        self.assertEqual(gated, {"trend_direction": 1.5, "momentum": 4.0})
        self.assertEqual(scores, {"trend_direction": 3.0, "momentum": 4.0})

    def test_adx_at_or_above_20_keeps_full_trend_direction_score(self):
        scores = {"trend_direction": 3.0, "momentum": 4.0}

        self.assertEqual(apply_adx_gate(scores, 20.0), scores)
        self.assertEqual(apply_adx_gate(scores, 20.1), scores)

    def test_missing_or_unknown_adx_skips_gate(self):
        scores = {"trend_direction": 3.0, "momentum": 4.0}

        for adx_value in (None, "Unknown", "not-a-number", float("nan"), pd.NA):
            with self.subTest(adx_value=adx_value):
                self.assertEqual(apply_adx_gate(scores, adx_value), scores)

    def test_missing_trend_group_does_not_get_created_by_gate(self):
        scores = {"momentum": 4.0}

        self.assertEqual(apply_adx_gate(scores, 10.0), scores)

    def test_scorer_applies_gate_before_weighted_combination(self):
        signals = [
            [0, "MA", "", "Up"],
            [1, "RSI", "", "Strong Up"],
        ]

        full_score = calculate_dimension_technical_score(signals, adx_value=20.0)
        weak_trend_score = calculate_dimension_technical_score(signals, adx_value=19.9)
        unavailable_score = calculate_dimension_technical_score(signals, adx_value=None)

        self.assertEqual(full_score[0], 87.5)
        self.assertEqual(weak_trend_score[0], 68.75)
        self.assertEqual(unavailable_score[0], full_score[0])

    def test_adx_signal_remains_non_voting_when_gate_value_is_missing(self):
        signals = [[0, "ADX", "", "Strong Up"]]

        self.assertEqual(
            calculate_dimension_technical_score(signals, adx_value=None),
            (0.0, {}, 0),
        )

    def test_latest_adx_utility_returns_numeric_value_or_none(self):
        frame = pd.DataFrame(
            {
                "high": range(100, 140),
                "low": range(99, 139),
                "close": range(99, 139),
            }
        )

        latest = get_latest_adx_value(frame)

        self.assertIsInstance(latest, float)
        self.assertIsNone(get_latest_adx_value(pd.DataFrame({"close": [1.0]})))


if __name__ == "__main__":
    unittest.main()
