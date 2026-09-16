"""Contracts for calendar-aligned v2 Flexible Rulebook history."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
import unittest

import pandas as pd

from backtest_engine.listing_status import ListingStatus
from flexible_rulebook.v2.contracts import TRAINING_RATIOS
from flexible_rulebook.v2.history import (
    HistoryRange,
    build_native_bars,
    load_history,
    make_native_split,
    trade_dates_belong_to_partition,
)


class FlexibleRulebookV2HistoryTests(unittest.TestCase):
    def _raw(self, dates: list[str]) -> pd.DataFrame:
        return pd.DataFrame({
            "date": dates,
            "open": [100_000 + index * 1_000 for index in range(len(dates))],
            "high": [102_000 + index * 1_000 for index in range(len(dates))],
            "low": [98_000 + index * 1_000 for index in range(len(dates))],
            "close": [101_000 + index * 1_000 for index in range(len(dates))],
            "volume": [1_000_000 + index for index in range(len(dates))],
        })

    def _listed(self, ticker: str = "VCB") -> dict[str, ListingStatus]:
        return {
            ticker: ListingStatus(
                ticker,
                "listed",
                date(2026, 1, 9),
                date(2026, 1, 9),
            )
        }

    def test_lifetime_normalizes_ticker_preserves_raw_integers_and_fingerprints_source_calendar(self) -> None:
        ticker = self._raw(["2026-01-05", "2026-01-06", "2026-01-09"])
        vnindex = ticker.copy(deep=True)
        engine = object()

        with patch(
            "flexible_rulebook.v2.history.load_listing_statuses",
            return_value=self._listed(),
        ), patch(
            "flexible_rulebook.v2.history.load_lifetime_date_bounds",
            return_value=(date(2026, 1, 5), date(2026, 1, 9)),
        ), patch(
            "flexible_rulebook.v2.history.load_ticker_history",
            side_effect=(ticker, vnindex),
        ):
            snapshot = load_history(" vcb ", HistoryRange.lifetime(), engine=engine)

        self.assertEqual("VCB", snapshot.ticker)
        self.assertEqual(date(2026, 1, 5), snapshot.start_date)
        self.assertEqual(date(2026, 1, 9), snapshot.end_date)
        self.assertEqual([100_000, 101_000, 102_000], snapshot.frame["open"].tolist())
        self.assertTrue(pd.api.types.is_integer_dtype(snapshot.frame["close"]))
        self.assertEqual(64, len(snapshot.source_fingerprint))
        self.assertEqual(64, len(snapshot.calendar_fingerprint))
        self.assertEqual(64, len(snapshot.fingerprint))

    def test_bounded_range_does_not_expand_to_lifetime_and_aligns_to_vnindex_sessions(self) -> None:
        ticker = self._raw(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-09"])
        vnindex = ticker.drop(index=[2]).reset_index(drop=True)
        history_range = HistoryRange.bounded(date(2026, 1, 5), date(2026, 1, 9))

        with patch(
            "flexible_rulebook.v2.history.load_listing_statuses",
            return_value=self._listed(),
        ), patch(
            "flexible_rulebook.v2.history.load_lifetime_date_bounds",
        ) as bounds, patch(
            "flexible_rulebook.v2.history.load_ticker_history",
            side_effect=(ticker, vnindex),
        ) as loader:
            snapshot = load_history("VCB", history_range, engine=object())

        bounds.assert_not_called()
        self.assertEqual((date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 9)), snapshot.sessions)
        self.assertEqual((date(2026, 1, 7),), snapshot.excluded_sessions)
        self.assertEqual(
            [
                ("VCB", date(2026, 1, 5), date(2026, 1, 9), loader.call_args_list[0].args[3]),
                ("VNINDEX", date(2026, 1, 5), date(2026, 1, 9), loader.call_args_list[1].args[3]),
            ],
            [call.args for call in loader.call_args_list],
        )

    def test_delisted_ticker_is_a_skip_before_loading_and_recovers_when_live_status_recovers(self) -> None:
        delisted = ListingStatus("LTG", "delisted", date(2026, 6, 19), date(2026, 9, 9))
        with patch(
            "flexible_rulebook.v2.history.load_listing_statuses",
            return_value={"LTG": delisted},
        ), patch("flexible_rulebook.v2.history.load_lifetime_date_bounds") as bounds:
            skipped = load_history("LTG", HistoryRange.lifetime(), engine=object())

        self.assertEqual("skipped", skipped.state)
        self.assertIn("Delisted", skipped.reason)
        bounds.assert_not_called()

    def test_vnindex_calendar_change_invalidates_identity_even_if_aligned_ticker_rows_do_not_change(self) -> None:
        ticker = self._raw(["2026-01-05", "2026-01-07", "2026-01-09"])
        before = ticker.copy(deep=True)
        after = pd.concat(
            [ticker.iloc[:1], self._raw(["2026-01-06"]), ticker.iloc[1:]],
            ignore_index=True,
        ).sort_values("date").reset_index(drop=True)
        history_range = HistoryRange.bounded(date(2026, 1, 5), date(2026, 1, 9))

        with patch(
            "flexible_rulebook.v2.history.load_listing_statuses",
            return_value=self._listed(),
        ), patch(
            "flexible_rulebook.v2.history.load_ticker_history",
            side_effect=(ticker, before, ticker, after),
        ):
            first = load_history("VCB", history_range, engine=object())
            second = load_history("VCB", history_range, engine=object())

        pd.testing.assert_frame_equal(first.frame, second.frame)
        self.assertNotEqual(first.calendar_fingerprint, second.calendar_fingerprint)
        self.assertNotEqual(first.fingerprint, second.fingerprint)

    def test_history_uses_retrying_engine_factory_only_when_caller_did_not_supply_engine(self) -> None:
        ticker = self._raw(["2026-01-05", "2026-01-09"])
        factory_engine = object()
        history_range = HistoryRange.bounded(date(2026, 1, 5), date(2026, 1, 9))

        with patch(
            "flexible_rulebook.v2.history.load_listing_statuses",
            return_value=self._listed(),
        ), patch(
            "flexible_rulebook.v2.history.load_ticker_history",
            side_effect=(ticker, ticker),
        ), patch(
            "flexible_rulebook.v2.history.get_engine_with_retry",
            return_value=factory_engine,
        ) as factory:
            snapshot = load_history("VCB", history_range, database_url="postgresql://example")

        self.assertEqual("available", snapshot.state)
        factory.assert_called_once_with("postgresql://example")

    def test_native_bars_preserve_actual_sessions_and_exclude_unfinished_week(self) -> None:
        frame = pd.DataFrame({
            "date": ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-12"],
            "open": [10, 11, 12, 13, 20],
            "high": [12, 14, 13, 15, 22],
            "low": [9, 10, 11, 12, 19],
            "close": [11, 12, 12, 14, 21],
            "volume": [100, 110, 120, 130, 200],
        })

        daily = build_native_bars(frame, "swing", completed_as_of=date(2026, 1, 12))
        weekly = build_native_bars(frame, "midterm", completed_as_of=date(2026, 1, 12))

        self.assertEqual(date(2026, 1, 5), daily[0].bucket_label)
        self.assertEqual(date(2026, 1, 5), daily[0].first_session)
        self.assertEqual(date(2026, 1, 5), daily[0].last_session)
        self.assertEqual(1, len(weekly))
        self.assertEqual(date(2026, 1, 9), weekly[0].bucket_label)
        self.assertEqual(date(2026, 1, 5), weekly[0].first_session)
        self.assertEqual(date(2026, 1, 8), weekly[0].last_session)
        self.assertEqual((10, 15, 9, 14, 460), weekly[0].ohlcv)

    def test_native_split_uses_floor_ratio_after_warmup_and_records_actual_session_bounds(self) -> None:
        frame = self._raw([
            "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
            "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16",
        ])
        bars = build_native_bars(frame, "swing", completed_as_of=date(2026, 1, 16))

        for ratio in TRAINING_RATIOS:
            split = make_native_split(bars, ratio, warmup_bars=1)
            self.assertEqual(1, split.training.start_ordinal)
            self.assertEqual(int(9 * float(ratio)), split.training.row_count)
            self.assertGreaterEqual(split.test.row_count, 1)
            self.assertEqual(split.training.end_session, bars[split.training.end_ordinal].last_session)
            self.assertEqual(split.test.start_session, bars[split.test.start_ordinal].first_session)

    def test_cross_boundary_or_incomplete_trade_is_excluded_from_partition(self) -> None:
        frame = self._raw([
            "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
            "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16",
        ])
        bars = build_native_bars(frame, "swing", completed_as_of=date(2026, 1, 16))
        partition = make_native_split(bars, Decimal("0.50")).test

        self.assertFalse(trade_dates_belong_to_partition(
            date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 13), partition,
        ))
        self.assertFalse(trade_dates_belong_to_partition(
            date(2026, 1, 12), date(2026, 1, 13), None, partition,
        ))
        self.assertTrue(trade_dates_belong_to_partition(
            date(2026, 1, 12), date(2026, 1, 13), date(2026, 1, 16), partition,
        ))


if __name__ == "__main__":
    unittest.main()
