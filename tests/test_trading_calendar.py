"""VN-Index-defined trading-session calendar contracts."""

from datetime import date
import unittest
from unittest.mock import patch

import pandas as pd

from commons.trading_calendar import (
    VNIndexCalendarUnavailable,
    build_vnindex_calendar,
    restrict_to_vnindex_sessions,
    load_calendar_aligned_history,
)


def _ohlcv(dates: list[str]) -> pd.DataFrame:
    close = pd.Series(range(10_000, 10_000 + len(dates)), dtype="int64")
    return pd.DataFrame({
        "date": pd.to_datetime(dates),
        "open": close,
        "high": close + 10,
        "low": close - 10,
        "close": close,
        "volume": 1_000,
    })


class VNIndexTradingCalendarTests(unittest.TestCase):
    def test_missing_weekday_is_assumed_non_session_and_excluded_before_indicators(self):
        vnindex = _ohlcv(["2026-01-05", "2026-01-07", "2026-01-08"])
        ticker = _ohlcv(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"])

        calendar = build_vnindex_calendar(
            vnindex,
            start=date(2026, 1, 5),
            end=date(2026, 1, 8),
        )
        filtered, excluded = restrict_to_vnindex_sessions(ticker, calendar)

        self.assertEqual((date(2026, 1, 6),), calendar.assumed_non_sessions)
        self.assertEqual((date(2026, 1, 6),), excluded)
        self.assertEqual(
            [date(2026, 1, 5), date(2026, 1, 7), date(2026, 1, 8)],
            [value.date() for value in filtered["date"]],
        )

    def test_no_vnindex_overlap_reports_every_bounded_missing_weekday(self):
        with self.assertRaises(VNIndexCalendarUnavailable) as raised:
            build_vnindex_calendar(
                _ohlcv([]),
                start=date(2026, 1, 5),
                end=date(2026, 1, 9),
            )

        error = raised.exception
        self.assertEqual("missing_vnindex_history", error.reason)
        self.assertEqual(
            (date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8), date(2026, 1, 9)),
            error.missing_sessions,
        )
        self.assertIn("2026-01-05", str(error))
        self.assertIn("2026-01-09", str(error))

    def test_weekend_vnindex_row_fails_closed(self):
        with self.assertRaisesRegex(VNIndexCalendarUnavailable, "weekend"):
            build_vnindex_calendar(
                _ohlcv(["2026-01-05", "2026-01-10"]),
                start=date(2026, 1, 5),
                end=date(2026, 1, 10),
            )

    def test_no_ticker_overlap_reports_all_requested_missing_vnindex_weekdays(self):
        ticker = _ohlcv(["2026-01-08", "2026-01-09"])
        vnindex = _ohlcv(["2026-01-05", "2026-01-06"])

        with patch(
            "commons.trading_calendar._load_raw_history",
            side_effect=[ticker, vnindex],
        ), self.assertRaises(VNIndexCalendarUnavailable) as raised:
            load_calendar_aligned_history(
                object(),
                "VCB",
                start=date(2026, 1, 5),
                end=date(2026, 1, 9),
            )

        self.assertEqual("no_usable_overlap", raised.exception.reason)
        self.assertEqual(
            (date(2026, 1, 7), date(2026, 1, 8), date(2026, 1, 9)),
            raised.exception.missing_sessions,
        )


if __name__ == "__main__":
    unittest.main()
