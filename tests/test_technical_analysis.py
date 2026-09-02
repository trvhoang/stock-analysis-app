"""Focused tests for deterministic technical-analysis helpers."""

import unittest

import numpy as np
import pandas as pd

from commons.technical_analysis import (
    _canonical_indicator_name,
    _format_indicator_value,
    _format_price_value,
    _latest_numeric_value,
    apply_adx_gate,
    calculate_adx_trend,
    calculate_atr,
    calculate_atr_trend,
    calculate_bollinger,
    calculate_bollinger_trend,
    calculate_dimension_technical_score,
    calculate_ma_cross_trend,
    calculate_ma_trend,
    calculate_obv,
    calculate_obv_trend,
    calculate_rsi_trend,
    calculate_stochastic_trend,
    calculate_adx,
    get_latest_adx_value,
    calculate_trend_correlation,
    group_technical_indicators,
)


class TechnicalAnalysisTests(unittest.TestCase):
    def test_group_technical_indicators_preserves_unknown_records(self) -> None:
        data = [[0, "RSI", "", "Up"], [1, "Mystery", "", "Down"], [2]]
        grouped = group_technical_indicators(data)
        self.assertEqual(grouped["momentum"], [data[0]])
        self.assertEqual(grouped["unassigned"], [data[1], data[2]])
        self.assertEqual(data, [[0, "RSI", "", "Up"], [1, "Mystery", "", "Down"], [2]])

    def test_apply_adx_gate_halves_only_trend_direction_below_threshold(self) -> None:
        scores = {"trend_direction": 4.0, "momentum": 3.0}
        gated = apply_adx_gate(scores, 19.99)
        self.assertEqual(gated, {"trend_direction": 2.0, "momentum": 3.0})
        self.assertEqual(scores, {"trend_direction": 4.0, "momentum": 3.0})
        self.assertEqual(apply_adx_gate(scores, 20), scores)
        self.assertEqual(apply_adx_gate(scores, "bad"), scores)

    def test_dimension_score_renormalizes_available_dimensions(self) -> None:
        tech_data = [[0, "RSI", "", "Strong Up"], [1, "ADX", "", "Up"]]
        percentage, group_scores, count = calculate_dimension_technical_score(tech_data, adx_value=25)
        self.assertEqual(count, 1)
        self.assertEqual(group_scores["momentum"], 4.0)
        self.assertEqual(percentage, 100.0)

    def test_trend_correlation_maps_trend_keys_to_numeric_scores(self) -> None:
        frame = pd.DataFrame({"a": ["Up", "Down", "Up"], "b": ["Strong Up", "Strong Down", "Up"]})
        correlation = calculate_trend_correlation(frame)
        self.assertGreater(float(correlation.loc["a", "b"]), 0.9)
        self.assertTrue(calculate_trend_correlation(pd.DataFrame()).empty)

    def test_calculate_atr_uses_true_range_and_wilder_warmup(self) -> None:
        frame = pd.DataFrame(
            {"high": [12.0, 15.0, 14.0], "low": [10.0, 11.0, 12.0], "close": [11.0, 12.0, 13.0]}
        )
        atr = calculate_atr(frame, period=2)
        self.assertTrue(np.isnan(atr.iloc[0]))
        self.assertAlmostEqual(float(atr.iloc[1]), 3.0)
        self.assertAlmostEqual(float(atr.iloc[2]), 2.5)
        self.assertNotIn("ATR_2", frame.columns)

    def test_calculate_atr_returns_aligned_nan_for_missing_columns(self) -> None:
        frame = pd.DataFrame({"close": [10.0, 11.0]})
        atr = calculate_atr(frame, period=2)
        self.assertEqual(atr.name, "ATR_2")
        self.assertEqual(len(atr), 2)
        self.assertTrue(atr.isna().all())

    def test_calculate_obv_starts_flat_and_signs_volume(self) -> None:
        frame = pd.DataFrame({"close": [10.0, 11.0, 10.0, 10.0], "volume": [100, 200, 300, 400]})
        obv = calculate_obv(frame)
        pd.testing.assert_series_equal(obv, pd.Series([0.0, 200.0, -100.0, -100.0], name="OBV"))
        self.assertNotIn("OBV", frame.columns)

    def test_obv_and_adx_trend_return_unknown_for_insufficient_or_missing_data(self) -> None:
        self.assertEqual(calculate_obv_trend(pd.DataFrame({"close": [1], "OBV": [0]}), lookback=1), "Unknown")
        self.assertEqual(calculate_adx_trend(pd.DataFrame({"ADX_14": [np.nan]})), "Unknown")
        self.assertEqual(calculate_adx_trend(pd.DataFrame({"ADX_14": [19.9]})), "Sideways")

    def test_atr_trend_uses_prior_baseline_and_explicit_bands(self) -> None:
        frame = pd.DataFrame({"close": [100.0] * 4, "ATR": [1.0, 1.0, 1.0, 1.5]})
        self.assertEqual(calculate_atr_trend(frame, atr_col="ATR", baseline_window=3), "Strong Up")
        self.assertEqual(calculate_atr_trend(pd.DataFrame({"close": [100.0], "ATR": [1.0]}), atr_col="ATR"), "Unknown")

    def test_calculate_bollinger_returns_sample_bands_without_mutating_input(self) -> None:
        frame = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
        bands = calculate_bollinger(frame, period=3, std_mult=2)
        self.assertEqual(
            list(bands.columns),
            ["BBM_3_2", "BBU_3_2", "BBL_3_2", "BBB_3_2", "BBP_3_2"],
        )
        self.assertTrue(bands.iloc[:2].isna().all().all())
        self.assertAlmostEqual(float(bands.loc[2, "BBM_3_2"]), 2.0)
        self.assertAlmostEqual(float(bands.loc[2, "BBU_3_2"]), 4.0)
        self.assertAlmostEqual(float(bands.loc[2, "BBL_3_2"]), 0.0)
        self.assertAlmostEqual(float(bands.loc[2, "BBB_3_2"]), 200.0)
        self.assertAlmostEqual(float(bands.loc[2, "BBP_3_2"]), 0.75)
        self.assertNotIn("BBM_3_2", frame.columns)

    def test_bollinger_and_adx_helpers_reject_missing_input_safely(self) -> None:
        frame = pd.DataFrame({"open": [1.0, 2.0]})
        bands = calculate_bollinger(frame, period=3)
        self.assertEqual(bands.shape, (2, 5))
        self.assertTrue(bands.isna().all().all())
        adx = calculate_adx(frame, period=2)
        self.assertEqual(adx.shape, (2, 3))
        self.assertTrue(adx.isna().all().all())
        self.assertIsNone(get_latest_adx_value(frame, period=2))

    def test_adx_directional_series_and_latest_value_are_aligned(self) -> None:
        frame = pd.DataFrame(
            {
                "high": [10.0, 11.0, 12.0, 13.0, 14.0],
                "low": [9.0, 10.0, 11.0, 12.0, 13.0],
                "close": [9.5, 10.5, 11.5, 12.5, 13.5],
            }
        )
        adx = calculate_adx(frame, period=2)
        self.assertEqual(list(adx.columns), ["ADX_2", "DMP_2", "DMN_2"])
        self.assertEqual(len(adx), len(frame))
        self.assertAlmostEqual(float(adx["DMP_2"].iloc[-1]), 63.829787234042556)
        self.assertAlmostEqual(float(adx["DMN_2"].iloc[-1]), 0.0)
        self.assertAlmostEqual(get_latest_adx_value(frame, period=2), float(adx["ADX_2"].iloc[-1]))

    def test_ma_trend_handles_spread_reversal_and_missing_values(self) -> None:
        up = pd.DataFrame({"close": [100.0], "fast": [105.0], "slow": [100.0]})
        self.assertEqual(calculate_ma_trend(up, "fast", "slow"), "Up")
        sideways = pd.DataFrame({"close": [100.0], "fast": [101.0], "slow": [100.0]})
        self.assertEqual(calculate_ma_trend(sideways, "fast", "slow"), "Sideways")
        self.assertEqual(calculate_ma_trend(pd.DataFrame({"close": [1.0]}), "fast", "slow"), "Unknown")

    def test_ma_cross_trend_uses_latest_nonzero_events_only(self) -> None:
        frame = pd.DataFrame({"cross": [0, 1, 0, -1, 1, 0, 1]})
        self.assertEqual(calculate_ma_cross_trend(frame, "cross"), "Up")
        self.assertEqual(calculate_ma_cross_trend(pd.DataFrame({"cross": [0, 1]}), "cross"), "Unknown")
        self.assertEqual(calculate_ma_cross_trend(pd.DataFrame({"cross": [0, 1, -1]}), "missing"), "Unknown")

    def test_rsi_and_stochastic_trend_classifiers_cover_directional_boundaries(self) -> None:
        self.assertEqual(
            calculate_rsi_trend(pd.DataFrame({"rsi": [50.0, 57.0, 60.0]}), rsi_col="rsi"),
            "Up",
        )
        self.assertEqual(
            calculate_rsi_trend(pd.DataFrame({"rsi": [50.0, 42.0, 35.0]}), rsi_col="rsi"),
            "Down",
        )
        self.assertEqual(calculate_rsi_trend(pd.DataFrame({"rsi": [np.nan]}), rsi_col="rsi"), "Unknown")
        self.assertEqual(calculate_stochastic_trend(pd.DataFrame({"k": [80.0], "d": [75.0]}), "k", "d"), "Up")
        self.assertEqual(calculate_stochastic_trend(pd.DataFrame({"k": [20.0], "d": [25.0]}), "k", "d"), "Down")
        self.assertEqual(calculate_stochastic_trend(pd.DataFrame({"k": [50.0], "d": [50.0]}), "k", "d"), "Sideways")

    def test_bollinger_trend_prioritizes_breakouts_then_narrow_center(self) -> None:
        columns = {"close": [106.0], "mid": [100.0], "upper": [105.0], "lower": [95.0], "width": [10.0], "pct": [1.1]}
        self.assertEqual(calculate_bollinger_trend(pd.DataFrame(columns), "close", "mid", "upper", "lower", "width", "pct"), "Strong Up")
        columns["close"] = [100.0]
        columns["width"] = [3.0]
        columns["pct"] = [0.5]
        self.assertEqual(calculate_bollinger_trend(pd.DataFrame(columns), "close", "mid", "upper", "lower", "width", "pct"), "Sideways")
        self.assertEqual(calculate_bollinger_trend(pd.DataFrame({"close": [1.0]}), "close", "mid", "upper", "lower", "width", "pct"), "Unknown")

    def test_scalar_technical_helpers_normalize_aliases_and_missing_values(self) -> None:
        frame = pd.DataFrame({"value": ["bad", 12.5]})
        self.assertEqual(_canonical_indicator_name(" rsi14 "), "RSI")
        self.assertIsNone(_canonical_indicator_name("future-indicator"))
        self.assertEqual(_latest_numeric_value(frame, "value"), 12.5)
        self.assertIsNone(_latest_numeric_value(pd.DataFrame({"value": ["bad"]}), "value"))
        self.assertIsNone(_latest_numeric_value(frame, "missing"))
        self.assertEqual(_format_indicator_value(1.234), "1.23")
        self.assertEqual(_format_indicator_value(None), "N/A")
        self.assertEqual(_format_price_value(12.3), "12.30k")
        self.assertEqual(_format_price_value(None), "N/A")


if __name__ == "__main__":
    unittest.main()
