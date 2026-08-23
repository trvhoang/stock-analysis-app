import unittest

import numpy as np
import pandas as pd

from commons.technical_analysis import (
    calculate_atr,
    calculate_atr_trend,
    calculate_bollinger,
    calculate_bollinger_trend,
    calculate_obv,
    calculate_obv_trend,
    calculate_adx,
    calculate_adx_trend,
)


def make_ohlcv(high, low, close, volume, index=None):
    df = pd.DataFrame({"high": high, "low": low, "close": close, "volume": volume})
    if index is not None:
        df.index = index
    return df


class TestCalculateATR(unittest.TestCase):
    def setUp(self):
        self.high = [10, 12, 11, 13, 14, 13, 15, 16, 15, 17, 18, 17, 19, 20, 19]
        self.low = [8, 9, 9, 10, 11, 11, 12, 13, 13, 14, 15, 14, 16, 17, 16]
        self.close = [9, 11, 10, 12, 13, 12, 14, 15, 14, 16, 17, 16, 18, 19, 18]
        self.volume = [100] * 15
        self.df = make_ohlcv(self.high, self.low, self.close, self.volume)

    def expected_tr(self):
        tr = [self.high[0] - self.low[0]]
        for i in range(1, len(self.high)):
            tr.append(
                max(
                    self.high[i] - self.low[i],
                    abs(self.high[i] - self.close[i - 1]),
                    abs(self.low[i] - self.close[i - 1]),
                )
            )
        return tr

    def test_returns_series_with_period_named_column(self):
        result = calculate_atr(self.df, period=14)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(result.name, "ATR_14")

    def test_matches_hand_computed_true_range_and_wilder_smoothing(self):
        expected = (
            pd.Series(self.expected_tr())
            .ewm(alpha=1 / 14, adjust=False, min_periods=14)
            .mean()
        )
        result = calculate_atr(self.df, period=14)
        pd.testing.assert_series_equal(
            result.reset_index(drop=True), expected, check_names=False
        )

    def test_nan_before_min_periods(self):
        result = calculate_atr(self.df, period=14)
        self.assertTrue(result.iloc[:13].isna().all())
        self.assertFalse(pd.isna(result.iloc[13]))
        self.assertFalse(pd.isna(result.iloc[14]))

    def test_preserves_custom_index(self):
        idx = pd.date_range("2026-01-01", periods=15)
        df = make_ohlcv(self.high, self.low, self.close, self.volume, index=idx)
        result = calculate_atr(df, period=14)
        pd.testing.assert_index_equal(result.index, idx)

    def test_missing_required_column_returns_all_nan_aligned(self):
        df = self.df.drop(columns=["high"])
        result = calculate_atr(df, period=14)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.isna().all())

    def test_empty_dataframe_returns_empty_series_no_exception(self):
        df = pd.DataFrame(columns=["high", "low", "close", "volume"])
        result = calculate_atr(df, period=14)
        self.assertEqual(len(result), 0)

    def test_does_not_mutate_input(self):
        original_cols = list(self.df.columns)
        calculate_atr(self.df, period=14)
        self.assertEqual(list(self.df.columns), original_cols)


class TestCalculateBollinger(unittest.TestCase):
    def setUp(self):
        # 25 rows, deterministic ramp so rolling mean/std are hand-checkable
        self.close = [100 + i for i in range(25)]
        self.df = make_ohlcv(
            high=[c + 1 for c in self.close],
            low=[c - 1 for c in self.close],
            close=self.close,
            volume=[1000] * 25,
        )

    def test_returns_dataframe_with_expected_columns(self):
        result = calculate_bollinger(self.df, period=20, std_mult=2)
        self.assertIsInstance(result, pd.DataFrame)
        for col in ["BBM_20_2", "BBU_20_2", "BBL_20_2", "BBB_20_2", "BBP_20_2"]:
            self.assertIn(col, result.columns)

    def test_matches_hand_computed_rolling_stats(self):
        close = pd.Series(self.close)
        mid = close.rolling(window=20, min_periods=20).mean()
        std = close.rolling(window=20, min_periods=20).std()
        upper = mid + 2 * std
        lower = mid - 2 * std
        bandwidth = (upper - lower) / mid * 100
        percent_b = (close - lower) / (upper - lower)

        result = calculate_bollinger(self.df, period=20, std_mult=2)
        pd.testing.assert_series_equal(
            result["BBM_20_2"].reset_index(drop=True), mid, check_names=False
        )
        pd.testing.assert_series_equal(
            result["BBU_20_2"].reset_index(drop=True), upper, check_names=False
        )
        pd.testing.assert_series_equal(
            result["BBL_20_2"].reset_index(drop=True), lower, check_names=False
        )
        pd.testing.assert_series_equal(
            result["BBB_20_2"].reset_index(drop=True), bandwidth, check_names=False
        )
        pd.testing.assert_series_equal(
            result["BBP_20_2"].reset_index(drop=True), percent_b, check_names=False
        )

    def test_nan_before_min_periods(self):
        result = calculate_bollinger(self.df, period=20, std_mult=2)
        self.assertTrue(result["BBM_20_2"].iloc[:19].isna().all())
        self.assertFalse(pd.isna(result["BBM_20_2"].iloc[19]))

    def test_missing_close_returns_all_nan_aligned(self):
        df = self.df.drop(columns=["close"])
        result = calculate_bollinger(df, period=20, std_mult=2)
        self.assertEqual(len(result), len(df))
        for col in ["BBM_20_2", "BBU_20_2", "BBL_20_2", "BBB_20_2", "BBP_20_2"]:
            self.assertTrue(result[col].isna().all())

    def test_empty_dataframe_no_exception(self):
        df = pd.DataFrame(columns=["high", "low", "close", "volume"])
        result = calculate_bollinger(df, period=20, std_mult=2)
        self.assertEqual(len(result), 0)


class TestCalculateOBV(unittest.TestCase):
    def setUp(self):
        self.close = [10, 11, 10, 10, 12, 11, 11, 13]
        self.volume = [100, 200, 150, 50, 300, 100, 80, 400]
        self.df = make_ohlcv(
            high=[c + 1 for c in self.close],
            low=[c - 1 for c in self.close],
            close=self.close,
            volume=self.volume,
        )

    def test_returns_series_named_obv(self):
        result = calculate_obv(self.df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(result.name, "OBV")

    def test_matches_hand_computed_values(self):
        expected = pd.Series([0, 200, 50, 50, 350, 250, 250, 650], dtype=float)
        result = calculate_obv(self.df)
        pd.testing.assert_series_equal(
            result.reset_index(drop=True).astype(float), expected, check_names=False
        )

    def test_missing_volume_returns_all_nan_aligned(self):
        df = self.df.drop(columns=["volume"])
        result = calculate_obv(df)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.isna().all())

    def test_missing_close_returns_all_nan_aligned(self):
        df = self.df.drop(columns=["close"])
        result = calculate_obv(df)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.isna().all())

    def test_empty_dataframe_no_exception(self):
        df = pd.DataFrame(columns=["high", "low", "close", "volume"])
        result = calculate_obv(df)
        self.assertEqual(len(result), 0)

    def test_does_not_mutate_input(self):
        original_cols = list(self.df.columns)
        calculate_obv(self.df)
        self.assertEqual(list(self.df.columns), original_cols)


class TestCalculateADX(unittest.TestCase):
    def setUp(self):
        # 40 rows of a clean uptrend so +DM dominates and ADX/DMP/DMN are well-defined
        n = 40
        self.high = [100 + i * 1.5 for i in range(n)]
        self.low = [98 + i * 1.5 for i in range(n)]
        self.close = [99 + i * 1.5 for i in range(n)]
        self.volume = [1000] * n
        self.df = make_ohlcv(self.high, self.low, self.close, self.volume)

    def test_returns_dataframe_with_expected_columns(self):
        result = calculate_adx(self.df, period=14)
        self.assertIsInstance(result, pd.DataFrame)
        for col in ["ADX_14", "DMP_14", "DMN_14"]:
            self.assertIn(col, result.columns)

    def test_uptrend_has_dominant_positive_di_and_bounded_values(self):
        result = calculate_adx(self.df, period=14)
        tail = result.dropna()
        self.assertTrue((tail["DMP_14"] > tail["DMN_14"]).all())
        self.assertTrue((tail["ADX_14"] >= 0).all())
        self.assertTrue((tail["ADX_14"] <= 100).all())

    def test_missing_required_column_returns_all_nan_aligned(self):
        df = self.df.drop(columns=["low"])
        result = calculate_adx(df, period=14)
        self.assertEqual(len(result), len(df))
        for col in ["ADX_14", "DMP_14", "DMN_14"]:
            self.assertTrue(result[col].isna().all())

    def test_empty_dataframe_no_exception(self):
        df = pd.DataFrame(columns=["high", "low", "close", "volume"])
        result = calculate_adx(df, period=14)
        self.assertEqual(len(result), 0)

    def test_does_not_mutate_input(self):
        original_cols = list(self.df.columns)
        calculate_adx(self.df, period=14)
        self.assertEqual(list(self.df.columns), original_cols)


class TestADXTrend(unittest.TestCase):
    def build(self, adx_values):
        return pd.DataFrame({"ADX_14": adx_values})

    def test_unknown_when_missing_column(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        self.assertEqual(calculate_adx_trend(df), "Unknown")

    def test_unknown_when_latest_is_nan(self):
        df = self.build([20, 22, np.nan])
        self.assertEqual(calculate_adx_trend(df), "Unknown")

    def test_unknown_when_empty(self):
        df = self.build([])
        self.assertEqual(calculate_adx_trend(df), "Unknown")

    def test_sideways_when_below_20(self):
        df = self.build([10, 15, 15])
        self.assertEqual(calculate_adx_trend(df), "Sideways")

    def test_up_when_at_least_20_and_rising(self):
        df = self.build([16, 18, 22])
        self.assertEqual(calculate_adx_trend(df), "Up")

    def test_strong_up_when_at_least_25_and_rising(self):
        df = self.build([20, 22, 27])
        self.assertEqual(calculate_adx_trend(df), "Strong Up")

    def test_sideways_when_at_least_20_but_not_rising(self):
        df = self.build([20, 25, 24])
        self.assertEqual(calculate_adx_trend(df), "Sideways")

    def test_sideways_when_only_one_valid_point_cannot_confirm_rising(self):
        df = self.build([np.nan, np.nan, 30])
        self.assertEqual(calculate_adx_trend(df), "Sideways")

    def test_never_returns_bearish_keys(self):
        for values in ([50, 10, 5], [90, 80, 70], [30, 29, 28]):
            with self.subTest(values=values):
                df = self.build(values)
                self.assertNotIn(calculate_adx_trend(df), ["Down", "Strong Down"])


class TestATRTrend(unittest.TestCase):
    def build(self, atr_last, close_const=100.0, baseline_atr=2.0):
        # 21 prior rows with constant ATR -> constant baseline norm = baseline_atr/close_const
        atr_series = [baseline_atr] * 21 + [atr_last]
        close_series = [close_const] * 22
        return pd.DataFrame({"close": close_series, "ATR_14": atr_series})

    def test_unknown_when_missing_columns(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        self.assertEqual(calculate_atr_trend(df), "Unknown")

    def test_unknown_when_insufficient_rows_for_baseline(self):
        df = pd.DataFrame({"close": [100] * 5, "ATR_14": [2] * 5})
        self.assertEqual(calculate_atr_trend(df), "Unknown")

    def test_strong_up_at_ratio_1_5_boundary(self):
        df = self.build(atr_last=3.0)  # ratio = 1.5
        self.assertEqual(calculate_atr_trend(df), "Strong Up")

    def test_up_at_ratio_1_1_boundary(self):
        df = self.build(atr_last=2.2)  # ratio = 1.1
        self.assertEqual(calculate_atr_trend(df), "Up")

    def test_up_just_below_strong_up(self):
        df = self.build(atr_last=2.4)  # ratio = 1.2
        self.assertEqual(calculate_atr_trend(df), "Up")

    def test_sideways_at_ratio_1_0(self):
        df = self.build(atr_last=2.0)  # ratio = 1.0
        self.assertEqual(calculate_atr_trend(df), "Sideways")

    def test_sideways_at_ratio_0_9_boundary(self):
        df = self.build(atr_last=1.8)  # ratio = 0.9
        self.assertEqual(calculate_atr_trend(df), "Sideways")

    def test_down_just_below_0_9(self):
        df = self.build(atr_last=1.79)  # ratio = 0.895
        self.assertEqual(calculate_atr_trend(df), "Down")

    def test_down_at_ratio_0_67_boundary(self):
        df = self.build(atr_last=1.34)  # ratio = 0.67
        self.assertEqual(calculate_atr_trend(df), "Down")

    def test_strong_down_below_0_67(self):
        df = self.build(atr_last=1.0)  # ratio = 0.5
        self.assertEqual(calculate_atr_trend(df), "Strong Down")


class TestOBVTrend(unittest.TestCase):
    def make(self, close, volume):
        return pd.DataFrame({"close": close, "OBV": calculate_obv_series_for_test(close, volume)})

    def test_unknown_when_missing_columns(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        self.assertEqual(calculate_obv_trend(df), "Unknown")

    def test_unknown_when_fewer_than_11_rows(self):
        df = self.make([100] * 5, [1000] * 5)
        self.assertEqual(calculate_obv_trend(df), "Unknown")

    def test_strong_up_confirmed_rising_over_3_percent(self):
        close = [100 + i for i in range(11)]  # 100..110, pct ~8.9%
        volume = [1000] * 11
        df = self.make(close, volume)
        self.assertEqual(calculate_obv_trend(df), "Strong Up")

    def test_up_confirmed_rising_under_3_percent(self):
        close = [100 + i * 0.2 for i in range(11)]  # ~1.8%
        volume = [1000] * 11
        df = self.make(close, volume)
        self.assertEqual(calculate_obv_trend(df), "Up")

    def test_strong_down_confirmed_falling_over_3_percent(self):
        close = [110 - i for i in range(11)]  # 110..100, pct ~-8.3%
        volume = [1000] * 11
        df = self.make(close, volume)
        self.assertEqual(calculate_obv_trend(df), "Strong Down")

    def test_down_confirmed_falling_under_3_percent(self):
        close = [110 - i * 0.2 for i in range(11)]
        volume = [1000] * 11
        df = self.make(close, volume)
        self.assertEqual(calculate_obv_trend(df), "Down")

    def test_sideways_when_flat(self):
        close = [100] * 11
        volume = [1000] * 11
        df = self.make(close, volume)
        self.assertEqual(calculate_obv_trend(df), "Sideways")

    def test_sideways_when_obv_and_price_diverge(self):
        close = [100, 90, 85, 80, 75, 70, 65, 60, 55, 50, 101]
        volume = [100] * 11
        df = self.make(close, volume)
        self.assertEqual(calculate_obv_trend(df), "Sideways")


def calculate_obv_series_for_test(close, volume):
    close_s = pd.Series(close, dtype=float)
    volume_s = pd.Series(volume, dtype=float)
    direction = np.sign(close_s.diff()).fillna(0)
    return (direction * volume_s).cumsum()


class TestBollingerTrend(unittest.TestCase):
    def build(self, close, bbm, bbu, bbl):
        bbb = (bbu - bbl) / bbm * 100
        bbp = (close - bbl) / (bbu - bbl)
        return pd.DataFrame(
            {
                "close": [close],
                "BBM_20_2": [bbm],
                "BBU_20_2": [bbu],
                "BBL_20_2": [bbl],
                "BBB_20_2": [bbb],
                "BBP_20_2": [bbp],
            }
        )

    def test_unknown_when_missing_columns(self):
        df = pd.DataFrame({"close": [100]})
        self.assertEqual(calculate_bollinger_trend(df), "Unknown")

    def test_unknown_when_latest_is_nan(self):
        df = self.build(np.nan, 100, 110, 90)
        self.assertEqual(calculate_bollinger_trend(df), "Unknown")

    def test_strong_up_when_above_upper_band(self):
        df = self.build(115, 100, 110, 90)
        self.assertEqual(calculate_bollinger_trend(df), "Strong Up")

    def test_strong_down_when_below_lower_band(self):
        df = self.build(85, 100, 110, 90)
        self.assertEqual(calculate_bollinger_trend(df), "Strong Down")

    def test_up_when_above_middle_wide_bands(self):
        df = self.build(103, 100, 110, 90)
        self.assertEqual(calculate_bollinger_trend(df), "Up")

    def test_down_when_below_middle_wide_bands(self):
        df = self.build(97, 100, 110, 90)
        self.assertEqual(calculate_bollinger_trend(df), "Down")

    def test_sideways_when_narrow_and_centered(self):
        df = self.build(100.0, 100.0, 101.9, 98.1)  # BBB = 3.8% < 4, BBP = 0.5
        self.assertEqual(calculate_bollinger_trend(df), "Sideways")

    def test_sideways_when_close_equals_middle_even_if_wide(self):
        df = self.build(100, 100, 110, 90)
        self.assertEqual(calculate_bollinger_trend(df), "Sideways")


if __name__ == "__main__":
    unittest.main()


