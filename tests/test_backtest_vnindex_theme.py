import unittest

import pandas as pd

from backtest_engine.vnindex_theme import (
    align_vnindex_asof,
    build_vnindex_confirmation,
    combine_theme_signal,
)


class VNIndexThemeTests(unittest.TestCase):
    def test_asof_alignment_never_uses_future_vnindex_date(self):
        ticker = pd.DataFrame(
            {"date": pd.to_datetime(["2025-01-03", "2025-01-05", "2025-01-10"])}
        )
        vnindex = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-01", "2025-01-06"]),
                "close": [100, 110],
            }
        )

        aligned = align_vnindex_asof(ticker, vnindex)

        self.assertEqual(
            aligned["vnindex_date"].dt.strftime("%Y-%m-%d").tolist(),
            ["2025-01-01", "2025-01-01", "2025-01-06"],
        )
        self.assertTrue((aligned["vnindex_date"] <= aligned["date"]).all())

    def test_swing_confirmation_uses_daily_sma_50(self):
        dates = pd.date_range("2024-01-01", periods=55, freq="B")
        close = list(range(100, 155))
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": [value + 1 for value in close],
                "low": [value - 1 for value in close],
                "close": close,
                "volume": [1000] * len(close),
            }
        )

        confirmation = build_vnindex_confirmation(frame, horizon="swing")

        self.assertFalse(bool(confirmation.iloc[48]))
        self.assertTrue(bool(confirmation.iloc[-1]))

    def test_midterm_confirmation_uses_weekly_sma_20(self):
        from backtest_engine.timeframes import to_weekly_ohlcv

        dates = pd.date_range("2024-01-01", periods=20, freq="W-MON")
        close = list(range(100, 120))
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": [value + 1 for value in close],
                "low": [value - 1 for value in close],
                "close": close,
                "volume": [1000] * len(close),
            }
        )

        confirmation = build_vnindex_confirmation(frame, horizon="midterm")

        self.assertEqual(len(confirmation), 20)
        self.assertFalse(bool(confirmation.iloc[18]))
        self.assertTrue(bool(confirmation.iloc[-1]))

    def test_midterm_confirmation_reuses_ticker_weekly_dates(self):
        from backtest_engine.timeframes import to_weekly_ohlcv

        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": list(range(100, 110)),
                "high": list(range(101, 111)),
                "low": list(range(99, 109)),
                "close": list(range(100, 110)),
                "volume": [1000] * len(dates),
            }
        )

        confirmation = build_vnindex_confirmation(frame, horizon="midterm")

        self.assertEqual(confirmation.index.tolist(), to_weekly_ohlcv(frame)["date"].tolist())

    def test_no_theme_is_identity_and_and_only(self):
        ticker_signal = pd.Series([True, False, True])
        theme_signal = pd.Series([True, True, False])

        self.assertEqual(
            combine_theme_signal(ticker_signal, theme_signal, mode=None).tolist(),
            ticker_signal.tolist(),
        )
        self.assertEqual(
            combine_theme_signal(ticker_signal, theme_signal, mode="AND").tolist(),
            [True, False, False],
        )
        with self.assertRaisesRegex(ValueError, "AND"):
            combine_theme_signal(ticker_signal, theme_signal, mode="OR")

    def test_invalid_theme_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            combine_theme_signal(pd.Series([True]), pd.Series([True]), mode="XOR")


if __name__ == "__main__":
    unittest.main()
