"""Contracts for horizon-native Technical Analysis snapshots."""

from datetime import date
import unittest

import pandas as pd

from backtest_engine.config import rulebook_for
from commons.technical_horizon import (
    TECHNICAL_NATIVE_BAR_LIMIT,
    build_horizon_technical_snapshot,
    build_horizon_native_frame,
    normalize_technical_horizon,
)


def make_daily_ohlcv(start: str, end: str) -> pd.DataFrame:
    dates = pd.bdate_range(start, end)
    close = pd.Series(range(100_000, 100_000 + len(dates) * 100, 100))
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 50,
            "high": close + 100,
            "low": close - 100,
            "close": close,
            "volume": 1_000_000,
        }
    )


class TechnicalHorizonTests(unittest.TestCase):
    def test_horizon_labels_resolve_to_schema5_rulebooks(self) -> None:
        self.assertEqual(normalize_technical_horizon("Swing"), "swing")
        self.assertEqual(normalize_technical_horizon("Mid-term"), "midterm")
        self.assertEqual(rulebook_for(normalize_technical_horizon("Swing")).ma_pair, (5, 13))
        self.assertEqual(rulebook_for(normalize_technical_horizon("Mid-term")).ma_pair, (8, 21))
        with self.assertRaisesRegex(ValueError, "Swing or Mid-term"):
            normalize_technical_horizon("Week")

    def test_midterm_uses_completed_fridays_and_caps_output(self) -> None:
        source = make_daily_ohlcv("2023-01-02", "2025-09-03")

        frame, rulebook = build_horizon_native_frame(source, "Mid-term")

        self.assertEqual(rulebook.horizon, "midterm")
        self.assertLessEqual(len(frame), TECHNICAL_NATIVE_BAR_LIMIT)
        self.assertTrue((pd.to_datetime(frame["date"]).dt.weekday == 4).all())
        self.assertEqual(pd.Timestamp(frame["date"].max()).date(), date(2025, 8, 29))

    def test_swing_remains_daily_and_caps_output(self) -> None:
        source = make_daily_ohlcv("2024-01-02", "2025-09-03")

        frame, rulebook = build_horizon_native_frame(source, "Swing")

        self.assertEqual(rulebook.horizon, "swing")
        self.assertEqual(len(frame), TECHNICAL_NATIVE_BAR_LIMIT)
        self.assertEqual(pd.Timestamp(frame["date"].max()).date(), date(2025, 9, 3))

    def test_swing_snapshot_matches_schema5_indicators_and_scales_once(self) -> None:
        source = make_daily_ohlcv("2024-01-02", "2025-09-03")
        native, _ = build_horizon_native_frame(source, "Swing")

        snapshot = build_horizon_technical_snapshot(source, "Swing")
        actual = snapshot["data"]

        self.assertEqual(snapshot["profile"]["ma_kind"], "EMA")
        self.assertEqual(snapshot["profile"]["short_ma"], 5)
        self.assertEqual(snapshot["profile"]["rsi_period"], 9)
        pd.testing.assert_series_equal(
            actual["RSI_9"].reset_index(drop=True),
            native["rulebook_rsi"].reset_index(drop=True),
            check_names=False,
        )
        pd.testing.assert_series_equal(
            actual["ADX_14"].reset_index(drop=True),
            native["rulebook_adx_14"].reset_index(drop=True),
            check_names=False,
        )
        for display_column, native_column in (
            ("EMA_5", "rulebook_ma_fast"),
            ("EMA_13", "rulebook_ma_slow"),
            ("ALLIGATOR_JAW", "rulebook_alligator_jaw"),
            ("ALLIGATOR_TEETH", "rulebook_alligator_teeth"),
            ("ALLIGATOR_LIPS", "rulebook_alligator_lips"),
            ("ATR_14", "ATR_14"),
        ):
            with self.subTest(column=display_column):
                pd.testing.assert_series_equal(
                    actual[display_column].multiply(1000).reset_index(drop=True),
                    native[native_column].reset_index(drop=True),
                    check_names=False,
                    check_exact=False,
                    atol=1e-9,
                )
        self.assertFalse(any(column.startswith("rulebook_") for column in actual.columns))

    def test_midterm_snapshot_uses_schema5_sma_and_reports_nine_indicators(self) -> None:
        source = make_daily_ohlcv("2023-01-02", "2025-09-03")
        native, _ = build_horizon_native_frame(source, "Mid-term")

        snapshot = build_horizon_technical_snapshot(source, "Mid-term")

        self.assertEqual(snapshot["profile"]["ma_kind"], "SMA")
        self.assertEqual(snapshot["profile"]["short_ma"], 8)
        self.assertEqual(snapshot["profile"]["long_ma"], 21)
        self.assertEqual(snapshot["profile"]["rsi_period"], 14)
        pd.testing.assert_series_equal(
            snapshot["data"]["SMA_8"].multiply(1000).reset_index(drop=True),
            native["rulebook_ma_fast"].reset_index(drop=True),
            check_names=False,
            check_exact=False,
            atol=1e-9,
        )
        self.assertEqual(
            [row["indicator"] for row in snapshot["report"]],
            [
                "MA", "MA cross", "Alligator", "RSI", "Stochastic",
                "ADX", "OBV", "ATR", "Bollinger",
            ],
        )
        alligator = snapshot["report"][2]
        self.assertEqual(alligator["dimension"], "trend_direction")
        self.assertEqual(alligator["role"], "gate")

    def test_short_history_snapshot_remains_usable_with_unknown_values(self) -> None:
        source = make_daily_ohlcv("2025-08-20", "2025-09-03")

        snapshot = build_horizon_technical_snapshot(source, "Swing")

        self.assertEqual(len(snapshot["data"]), len(source))
        self.assertEqual(snapshot["report"][2]["trend"], "Unknown")
