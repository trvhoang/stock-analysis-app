"""Causal, Backtest-owned V3 rulebook indicator contracts."""

from datetime import date
import unittest

import numpy as np
import pandas as pd

from backtest_engine import indicators as backtest_indicators
from backtest_engine.config import rulebook_for
from backtest_engine.indicators import build_rulebook_frame, rsi_upcross


def make_ohlcv(start="2024-01-01", rows=100) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=rows)
    close = pd.Series(range(50_000, 50_000 + rows), dtype="int64")
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 100,
            "low": close - 100,
            "close": close,
            "volume": [1_000] * rows,
        }
    )


RULEBOOK_COLUMNS = [
    "rulebook_ma_fast",
    "rulebook_ma_slow",
    "rulebook_rsi",
    "rulebook_alligator_jaw",
    "rulebook_alligator_teeth",
    "rulebook_alligator_lips",
    "rulebook_volume_baseline",
    "rulebook_plus_di_14",
    "rulebook_minus_di_14",
    "rulebook_adx_14",
    "ATR_14",
    "rulebook_missing_required_input",
]


class RulebookIndicatorTests(unittest.TestCase):
    def test_rsi_uses_first_simple_average_then_wilder_recursion(self):
        close = pd.Series([10.0, 11.0, 14.0, 13.0, 15.0, 14.0, 18.0])

        actual = backtest_indicators._rsi(close, 3)

        expected = np.array(
            [80.0, 87.5, 68.29268292682927, 86.3157894736842],
            dtype=float,
        )
        self.assertTrue(actual.iloc[:3].isna().all())
        np.testing.assert_allclose(actual.iloc[3:].to_numpy(), expected, rtol=1e-12)

    def test_rsi_preserves_zero_gain_and_zero_loss_edge_behavior(self):
        rising = backtest_indicators._rsi(pd.Series([10.0, 11.0, 12.0, 13.0]), 3)
        falling = backtest_indicators._rsi(pd.Series([13.0, 12.0, 11.0, 10.0]), 3)
        flat = backtest_indicators._rsi(pd.Series([10.0, 10.0, 10.0, 10.0]), 3)

        self.assertEqual(100.0, rising.iloc[3])
        self.assertEqual(0.0, falling.iloc[3])
        self.assertEqual(100.0, flat.iloc[3])

    def test_atr_uses_first_simple_average_then_wilder_recursion(self):
        frame = pd.DataFrame(
            {
                "high": [10.0, 13.0, 13.0, 15.0, 14.0],
                "low": [8.0, 9.0, 10.0, 11.0, 10.0],
                "close": [9.0, 12.0, 11.0, 14.0, 12.0],
            }
        )

        actual = backtest_indicators._atr(frame, 3)

        self.assertTrue(actual.iloc[:2].isna().all())
        np.testing.assert_allclose(
            actual.iloc[2:].to_numpy(),
            np.array([3.0, 10.0 / 3.0, 32.0 / 9.0]),
            rtol=1e-12,
        )

    def test_adx_uses_sma_seeded_directional_index_values(self):
        frame = pd.DataFrame(
            {
                "high": [10.0, 11.0, 12.0, 11.0, 10.0, 11.0],
                "low": [8.0, 9.0, 10.0, 8.0, 7.0, 8.0],
                "close": [9.0, 10.0, 11.0, 9.0, 8.0, 10.0],
            }
        )

        adx = backtest_indicators._adx(frame, 3)

        self.assertTrue(adx.iloc[:4].isna().all())
        np.testing.assert_allclose(
            adx.iloc[4:].to_numpy(),
            np.array([54.94252873563219, 37.02050935316655]),
            rtol=1e-12,
        )

    def test_rulebook_frame_exposes_directional_dmi_facts(self):
        source = make_ohlcv(rows=50)
        frame = build_rulebook_frame(
            source,
            rulebook_for("swing"),
            common_as_of=source["date"].iloc[-1].date(),
        )

        self.assertIn("rulebook_plus_di_14", frame.columns)
        self.assertIn("rulebook_minus_di_14", frame.columns)
        self.assertGreater(frame.loc[49, "rulebook_plus_di_14"], 0.0)
        self.assertEqual(0.0, frame.loc[49, "rulebook_minus_di_14"])

    def test_alligator_point_requires_full_lips_teeth_jaw_order(self):
        point = backtest_indicators._alligator_point(
            pd.Series([3.0, 1.0, 3.0]),
            pd.Series([2.0, 2.0, 2.0]),
            pd.Series([1.0, 3.0, 3.0]),
        )

        self.assertEqual(point.tolist(), [3.0, 1.0, 2.0])

    def test_volume_gate_excludes_the_current_bar_from_its_baseline(self):
        daily = make_ohlcv(rows=40)
        daily.loc[10, "volume"] = 1_300

        frame = build_rulebook_frame(
            daily,
            rulebook_for("swing"),
            common_as_of=daily["date"].iloc[-1].date(),
        )

        self.assertEqual(frame.loc[10, "rulebook_volume_baseline"], 1_000.0)
        self.assertTrue(bool(frame.loc[10, "rulebook_volume_gate"]))

    def test_rsi_upcross_is_an_event_not_a_persistent_bullish_label(self):
        values = pd.Series([51.9, 52.0, 55.0])

        self.assertEqual(rsi_upcross(values, 52).tolist(), [False, True, False])

    def test_future_rows_cannot_change_prior_swing_or_weekly_rulebook_values(self):
        original = make_ohlcv(rows=100)
        changed = original.copy(deep=True)
        cutoff = 69  # Friday; all preceding W-FRI bars are complete.
        changed.loc[cutoff + 1 :, "close"] += 10_000
        changed.loc[cutoff + 1 :, "open"] = changed.loc[cutoff + 1 :, "close"]
        changed.loc[cutoff + 1 :, "high"] = changed.loc[cutoff + 1 :, "close"] + 100
        changed.loc[cutoff + 1 :, "low"] = changed.loc[cutoff + 1 :, "close"] - 100

        for horizon in ("swing", "midterm"):
            with self.subTest(horizon=horizon):
                rulebook = rulebook_for(horizon)
                before = build_rulebook_frame(
                    original,
                    rulebook,
                    common_as_of=date(2025, 1, 1),
                )
                after = build_rulebook_frame(
                    changed,
                    rulebook,
                    common_as_of=date(2025, 1, 1),
                )
                cutoff_date = original.loc[cutoff, "date"]
                pd.testing.assert_frame_equal(
                    before.loc[before["date"] <= cutoff_date, RULEBOOK_COLUMNS].reset_index(
                        drop=True
                    ),
                    after.loc[after["date"] <= cutoff_date, RULEBOOK_COLUMNS].reset_index(
                        drop=True
                    ),
                )

    def test_midterm_holiday_short_week_boundary_uses_w_fri_label(self):
        daily = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2024-05-06",
                        "2024-05-07",
                        "2024-05-08",
                        "2024-05-09",
                        "2024-05-10",
                        "2024-05-13",
                        "2024-05-14",
                        "2024-05-15",
                    ]
                ),
                "open": [50_000] * 8,
                "high": [50_100] * 8,
                "low": [49_900] * 8,
                "close": [50_000] * 8,
                "volume": [1_000] * 8,
            }
        )

        for today, expected_last_date in (
            (date(2024, 5, 16), date(2024, 5, 10)),
            (date(2024, 5, 17), date(2024, 5, 17)),
            (date(2024, 5, 18), date(2024, 5, 17)),
            (date(2024, 5, 20), date(2024, 5, 17)),
        ):
            with self.subTest(today=today):
                weekly = build_rulebook_frame(
                    daily,
                    rulebook_for("midterm"),
                    common_as_of=today,
                )

                self.assertEqual(weekly["date"].max().date(), expected_last_date)

    def test_required_input_and_derived_ohlc_envelope_are_explicit_and_non_mutating(self):
        source = make_ohlcv(rows=50)
        source.loc[20, "high"] = source.loc[20, "close"] - 1

        frame = build_rulebook_frame(
            source,
            rulebook_for("swing"),
            common_as_of=source["date"].iloc[-1].date(),
        )

        self.assertEqual(frame.loc[20, "high"], source.loc[20, "open"])
        self.assertEqual(source.loc[20, "high"], source.loc[20, "close"] - 1)
        self.assertTrue(bool(frame.loc[0, "rulebook_missing_required_input"]))
        self.assertFalse(bool(frame.loc[40, "rulebook_missing_required_input"]))


if __name__ == "__main__":
    unittest.main()
