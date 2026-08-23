"""Focused contracts for sharing the current technical snapshot."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from commons.common_functions import synthesize_all_advice
from pages.analyze_visualization import analyze_portfolio_ticker


class TestAnalyzeSnapshotReuse(unittest.TestCase):
    def test_synthesis_reuses_precomputed_signals_without_fetching_again(self):
        stats_data = {
            "ticker": "FPT",
            "current_delta": 3.5,
            "total_signals": 10,
            "possibility_up": 70.0,
            "possibility_down": 20.0,
            "technical_signals": [
                [0, "MA", "", "Up"],
                [1, "MA cross", "", "Strong Up"],
                [2, "RSI", "", "Up"],
                [3, "Stochastic", "", "Sideways"],
                [4, "ADX", "", "Up"],
                [5, "OBV", "", "Up"],
                [6, "ATR", "", "Down"],
                [7, "Bollinger", "", "Up"],
            ],
            "technical_adx_value": 30.0,
        }

        with patch("commons.common_functions.fetch_data") as mock_fetch:
            result = synthesize_all_advice(
                stats_data,
                validation_days=5,
                result_days=5,
                engine=MagicMock(),
            )

        mock_fetch.assert_not_called()
        self.assertIn("Based on 7 indicators", result["technical"])
        self.assertIn("final", result)

    @patch("commons.common_functions.build_technical_snapshot")
    @patch("pandas.read_sql")
    def test_analyze_ticker_exposes_snapshot_signals_and_report(
        self,
        mock_read_sql,
        mock_build_snapshot,
    ):
        mock_read_sql.side_effect = [
            # Latest prices used by the statistical signal.
            pd.DataFrame({
                "date": ["2024-05-20", "2024-05-15"],
                "close": [110000, 100000],
                "exchange": ["HSX", "HSX"],
            }),
            # Historical result summary.
            pd.DataFrame({
                "up_count": [5],
                "down_count": [2],
                "no_change_count": [3],
                "total_signals": [10],
                "min_up_delta": [1.0],
                "median_up_delta": [2.0],
                "max_up_delta": [5.0],
                "min_down_delta": [-1.0],
                "median_down_delta": [-2.0],
                "max_down_delta": [-5.0],
            }),
        ]
        mock_build_snapshot.return_value = {
            "signals": [[0, "MA", "", "Up"]],
            "report": [{"indicator": "MA", "trend": "Up"}],
            "adx_value": 25.0,
        }

        from commons.common_functions import analyze_ticker

        with patch("commons.common_functions.fetch_data") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame({"close": [100.0]})
            result = analyze_ticker("TCB", 2, 5, MagicMock())

        mock_build_snapshot.assert_called_once()
        self.assertEqual(result["technical_signals"], [[0, "MA", "", "Up"]])
        self.assertEqual(result["technical_report"][0]["indicator"], "MA")
        self.assertEqual(result["technical_adx_value"], 25.0)

    @patch("pages.analyze_visualization.fetch_data")
    @patch("pages.analyze_visualization.analyze_ticker")
    def test_portfolio_reuses_analyze_ticker_snapshot(
        self,
        mock_analyze_ticker,
        mock_fetch,
    ):
        mock_analyze_ticker.return_value = {
            "possibility_up": 70.0,
            "possibility_down": 20.0,
            "min_up_delta": 1.0,
            "median_up_delta": 2.0,
            "max_up_delta": 3.0,
            "min_down_delta": -3.0,
            "median_down_delta": -2.0,
            "max_down_delta": -1.0,
            "technical_signals": [[0, "OBV", "", "Up"]],
            "technical_adx_value": 25.0,
        }

        result = analyze_portfolio_ticker("FPT", 5, 5, MagicMock())

        mock_fetch.assert_not_called()
        self.assertEqual(result["tech_trend_key"], "Strong Up")


if __name__ == "__main__":
    unittest.main()
