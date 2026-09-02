import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from pages.analyze_visualization import (
    _classify_statistical_trend,
    analyze_portfolio_ticker,
    analyze_price_movement,
    provide_advice,
)


class TestAnalyzeTrendClassification(unittest.TestCase):
    def test_private_classifier_uses_direct_up_and_down_thresholds(self):
        self.assertEqual(_classify_statistical_trend(71, 0), "Strong Up")
        self.assertEqual(_classify_statistical_trend(53, 0), "Up")
        self.assertEqual(_classify_statistical_trend(0, 71), "Strong Down")
        self.assertEqual(_classify_statistical_trend(0, 53), "Down")
        self.assertEqual(_classify_statistical_trend(40, 40), "Sideways")

    def test_analyze_price_movement_returns_empty_contract_for_short_validation(self):
        result = analyze_price_movement("FPT", 1, 5, 2.0, MagicMock())
        self.assertTrue(result.empty)
        self.assertEqual(
            list(result.columns),
            ["no. events", "exact_delta", "result", "result_delta", "signal_date_range"],
        )

    @patch("pages.analyze_visualization.pd.read_sql")
    def test_analyze_price_movement_bounds_query_closes_connection_and_rounds_output(self, mock_read_sql):
        mock_read_sql.return_value = pd.DataFrame(
            {
                "event_date": [date(2026, 8, 1)],
                "exact_delta": [1.234],
                "result": ["Up"],
                "result_delta": [2.345],
                "signal_date_range": ["2026-07-31 to 2026-08-01"],
            }
        )
        engine = MagicMock()

        result = analyze_price_movement(" FPT ", 5, 10, 3.0, engine)

        self.assertEqual(result.loc[0, "no. events"], 1)
        self.assertEqual(result.loc[0, "exact_delta"], 1.23)
        self.assertEqual(result.loc[0, "result_delta"], 2.35)
        query, connection = mock_read_sql.call_args.args
        self.assertIn("%(ticker)s", query)
        self.assertIn("%(validation_days)s", query)
        self.assertEqual(mock_read_sql.call_args.kwargs["params"]["validation_days"], 4)
        self.assertEqual(mock_read_sql.call_args.kwargs["params"]["result_days"], 10)
        self.assertIs(connection, engine.raw_connection.return_value)
        engine.raw_connection.return_value.close.assert_called_once_with()

    def make_stats(self, up, down, total_signals=10):
        return {
            "current_delta": 3.5,
            "total_signals": total_signals,
            "possibility_up": up,
            "possibility_down": down,
        }

    def classify(self, up, down):
        _, trend = provide_advice(5, 10, self.make_stats(up, down))
        return trend

    def test_preserves_existing_strong_and_moderate_directional_results(self):
        cases = [
            (55, 20, "Up"),
            (72, 5, "Strong Up"),
            (15, 80, "Strong Down"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                self.assertEqual(self.classify(up, down), expected)

    def test_uses_sideways_when_low_up_probability_is_no_change_mass(self):
        self.assertEqual(self.classify(40, 10), "Sideways")

    def test_uses_direct_down_probability_for_bearish_classification(self):
        self.assertEqual(self.classify(25, 60), "Down")

    @patch("pages.analyze_visualization.analyze_ticker")
    def test_portfolio_uses_direct_down_probability_for_its_statistical_key(self, mock_analyze_ticker):
        mock_analyze_ticker.return_value = {
            "possibility_up": 25.0,
            "possibility_down": 60.0,
            "min_up_delta": None,
            "median_up_delta": None,
            "max_up_delta": None,
            "min_down_delta": -5.0,
            "median_down_delta": -3.0,
            "max_down_delta": -1.0,
            "technical_signals": [],
            "technical_adx_value": None,
        }

        result = analyze_portfolio_ticker("FPT", 5, 10, MagicMock())

        self.assertEqual("Down", result["stat_trend_key"])
        self.assertEqual("-1.00 -3.00 -5.00 (down)", result["delta"])

    def test_applies_up_threshold_boundaries(self):
        cases = [
            (53, 0, "Up"),
            (70, 0, "Up"),
            (71, 0, "Strong Up"),
            (52, 0, "Sideways"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                self.assertEqual(self.classify(up, down), expected)

    def test_applies_down_threshold_boundaries(self):
        cases = [
            (0, 53, "Down"),
            (0, 70, "Down"),
            (0, 71, "Strong Down"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                self.assertEqual(self.classify(up, down), expected)

    def test_returns_sideways_when_directional_evidence_is_absent_or_equal(self):
        self.assertEqual(self.classify(0, 0), "Sideways")
        self.assertEqual(self.classify(10, 10), "Sideways")

    def test_preserves_message_and_tuple_contract(self):
        cases = [
            (40, 10, "Sideways"),
            (25, 60, "Down"),
            (10, 80, "Strong Down"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                result = provide_advice(5, 10, self.make_stats(up, down))

                self.assertIsInstance(result, tuple)
                self.assertEqual(len(result), 2)
                self.assertIn("3.50%", result[0])
                self.assertIn(expected, result[0])
                self.assertEqual(result[1], expected)

    def test_returns_unknown_without_historical_signals(self):
        message, trend = provide_advice(
            5,
            10,
            self.make_stats(0, 0, total_signals=0),
        )

        self.assertEqual(trend, "Unknown")
        self.assertIn("no historical data matches", message.lower())


if __name__ == "__main__":
    unittest.main()
