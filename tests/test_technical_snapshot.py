import unittest

import pandas as pd

import commons.technical_analysis as technical_analysis
from commons.technical_analysis import build_technical_snapshot


def make_ohlcv(rows=60):
    close = pd.Series([100.0 + index for index in range(rows)])
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=rows),
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [1000.0] * rows,
        }
    )


class TestTechnicalSnapshot(unittest.TestCase):
    def test_snapshot_contains_all_eight_indicators_and_roles(self):
        snapshot = build_technical_snapshot(make_ohlcv(), 5, 10)

        report_by_name = {
            record["indicator"]: record for record in snapshot["report"]
        }
        self.assertEqual(
            set(report_by_name),
            {"MA", "MA cross", "RSI", "Stochastic", "ADX", "OBV", "ATR", "Bollinger"},
        )
        self.assertEqual(
            report_by_name["ADX"],
            {
                "indicator": "ADX",
                "dimension": "trend_strength",
                "role": "gate",
                "value": report_by_name["ADX"]["value"],
                "trend": report_by_name["ADX"]["trend"],
            },
        )
        self.assertTrue(all("dimension" in record for record in snapshot["report"]))
        self.assertTrue(all("role" in record for record in snapshot["report"]))
        self.assertIsNotNone(snapshot["adx_value"])

    def test_snapshot_contains_enriched_columns_and_scorer_signals(self):
        snapshot = build_technical_snapshot(make_ohlcv(), 5, 10)

        for column in (
            "SMA_5",
            "SMA_10",
            "cross_5_10",
            "RSI_14",
            "%K",
            "%D",
            "ATR_14",
            "OBV",
            "ADX_14",
            "BBM_20_2",
            "BBU_20_2",
            "BBL_20_2",
            "BBB_20_2",
            "BBP_20_2",
        ):
            self.assertIn(column, snapshot["data"].columns)

        self.assertEqual(len(snapshot["signals"]), 8)
        signal_names = {signal[1] for signal in snapshot["signals"]}
        self.assertEqual(
            signal_names,
            {"MA", "MA cross", "RSI", "Stochastic", "ADX", "OBV", "ATR", "Bollinger"},
        )

    def test_snapshot_handles_short_data_without_raising(self):
        snapshot = build_technical_snapshot(make_ohlcv(rows=5), 5, 10)

        self.assertEqual(len(snapshot["report"]), 8)
        self.assertIsNone(snapshot["adx_value"])
        report_by_name = {
            record["indicator"]: record for record in snapshot["report"]
        }
        for indicator in ("MA", "MA cross", "RSI", "ADX", "OBV", "ATR", "Bollinger"):
            self.assertEqual(report_by_name[indicator]["trend"], "Unknown")

    def test_ichimoku_placeholder_is_removed(self):
        self.assertFalse(hasattr(technical_analysis, "calculate_ichimoku"))


if __name__ == "__main__":
    unittest.main()
