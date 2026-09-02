"""History-contract tests for the isolated Flexible Rulebook core."""

from dataclasses import replace
from datetime import date
from unittest.mock import patch
import unittest

import pandas as pd

from flexible_rulebook.history import (
    EvidenceSourceAnchor,
    HistorySnapshot,
    load_flexible_history,
    make_evaluation_split,
    make_evidence_source_anchor,
    trade_dates_belong_to_partition,
    verify_evidence_source_anchor,
)


class FlexibleRulebookHistoryTests(unittest.TestCase):
    def _frame(self, dates: list[str]) -> pd.DataFrame:
        return pd.DataFrame({
            "date": dates,
            "open": [100_000 + index * 1_000 for index in range(len(dates))],
            "high": [102_000 + index * 1_000 for index in range(len(dates))],
            "low": [98_000 + index * 1_000 for index in range(len(dates))],
            "close": [101_000 + index * 1_000 for index in range(len(dates))],
            "volume": [1_000_000 + index for index in range(len(dates))],
        })

    def _snapshot(
        self,
        *,
        dates: list[str] | None = None,
        requested_start: date = date(2011, 1, 2),
        requested_as_of: date = date(2026, 1, 2),
    ) -> HistorySnapshot:
        frame = self._frame(dates or [
            "2011-01-03", "2020-12-31", "2021-01-04", "2026-01-02",
        ])
        native_dates = pd.to_datetime(frame["date"])
        return HistorySnapshot(
            ticker="VCB",
            frame=frame,
            fingerprint="a" * 64,
            quality_state="eligible",
            requested_start=requested_start,
            requested_as_of=requested_as_of,
            first_date=native_dates.iloc[0].date(),
            as_of_date=native_dates.iloc[-1].date(),
            evidence_prefix_fingerprint="a" * 64,
        )

    def test_loader_uses_calendar_fifteen_year_window_and_preserves_raw_input(self) -> None:
        raw = self._frame(["2011-01-03", "2026-01-02"])
        before = raw.copy(deep=True)
        engine = object()

        with patch("flexible_rulebook.history._load_ticker_history", return_value=raw) as loader:
            snapshot = load_flexible_history(engine, " vcb ", as_of=date(2026, 1, 2))

        loader.assert_called_once_with("VCB", date(2011, 1, 2), date(2026, 1, 2), engine)
        pd.testing.assert_frame_equal(raw, before)
        self.assertEqual(snapshot.ticker, "VCB")
        self.assertEqual(snapshot.first_date, date(2011, 1, 3))
        self.assertEqual(snapshot.as_of_date, date(2026, 1, 2))
        self.assertEqual(snapshot.quality_state, "eligible")

    def test_loader_maps_leap_day_to_previous_february_twenty_eighth(self) -> None:
        raw = self._frame(["2009-02-28", "2024-02-29"])

        with patch("flexible_rulebook.history._load_ticker_history", return_value=raw) as loader:
            load_flexible_history(object(), "VCB", as_of=date(2024, 2, 29))

        self.assertEqual(loader.call_args.args[1], date(2009, 2, 28))

    def test_split_uses_first_native_bar_on_or_after_calendar_cutoff(self) -> None:
        split = make_evaluation_split(self._snapshot())

        self.assertEqual(split.method, "calendar_10y_5y")
        self.assertEqual(split.requested_test_cutoff, date(2021, 1, 2))
        self.assertEqual(split.training.end, date(2020, 12, 31))
        self.assertEqual(split.test.start, date(2021, 1, 4))

    def test_short_history_uses_single_chronological_65_35_boundary(self) -> None:
        snapshot = self._snapshot(
            dates=["2019-01-02", "2021-01-04", "2024-01-02", "2026-01-02"],
            requested_start=date(2011, 1, 2),
        )

        split = make_evaluation_split(snapshot)

        self.assertEqual(split.method, "chronological_65_35")
        self.assertIsNone(split.requested_test_cutoff)
        self.assertEqual(split.training.row_count, 2)
        self.assertEqual(split.test.row_count, 2)

    def test_full_window_without_native_test_bar_fails_explicitly(self) -> None:
        snapshot = self._snapshot(dates=["2011-01-03", "2020-12-31"])

        with self.assertRaisesRegex(ValueError, "native bar"):
            make_evaluation_split(snapshot)

    def test_usable_snapshot_rejects_frame_bounds_that_disagree_with_metadata(self) -> None:
        snapshot = self._snapshot()

        with self.assertRaisesRegex(ValueError, "actual history bounds"):
            replace(snapshot, first_date=date(2011, 1, 4))

    def test_trade_dates_drop_crossing_trade_by_dates_not_row_count(self) -> None:
        split = make_evaluation_split(self._snapshot())

        self.assertFalse(trade_dates_belong_to_partition(
            date(2020, 12, 31), date(2021, 1, 4), date(2021, 1, 8), split.training,
        ))
        self.assertTrue(trade_dates_belong_to_partition(
            date(2021, 1, 4), date(2021, 1, 5), date(2021, 1, 8), split.test,
        ))

    def test_invalid_history_is_not_fingerprinted_and_audit_concern_is_display_only(self) -> None:
        invalid = self._frame(["2011-01-03", "2026-01-02"])
        invalid.loc[1, "close"] = 0
        concern = self._frame(["2011-01-03", "2026-01-02"])
        concern.loc[1, "high"] = 90_000

        with patch("flexible_rulebook.history._load_ticker_history", side_effect=(invalid, concern)):
            invalid_snapshot = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))
            concern_snapshot = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))

        self.assertEqual(invalid_snapshot.quality_state, "invalid")
        self.assertIsNone(invalid_snapshot.fingerprint)
        self.assertEqual(concern_snapshot.quality_state, "display_only")
        self.assertIsNotNone(concern_snapshot.fingerprint)

    def test_ohlc_ordering_quality_ratio_ignores_volume_scale(self) -> None:
        frame = self._frame(["2011-01-03", "2026-01-02"])
        frame.loc[1, "high"] = 95_000
        frame.loc[1, "volume"] = 10_000_000

        with patch("flexible_rulebook.history._load_ticker_history", return_value=frame):
            snapshot = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))

        self.assertEqual(snapshot.quality_state, "display_only")
        self.assertIn("OHLC ordering mismatch exceeds 1%", snapshot.quality_reasons)

    def test_same_as_of_and_row_count_but_corrected_close_changes_fingerprint(self) -> None:
        first = self._frame(["2011-01-03", "2026-01-02"])
        corrected = first.copy(deep=True)
        corrected.loc[0, "close"] += 1

        with patch("flexible_rulebook.history._load_ticker_history", side_effect=(first, corrected)):
            before = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))
            after = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))

        self.assertEqual(len(before.frame), len(after.frame))
        self.assertEqual(before.as_of_date, after.as_of_date)
        self.assertNotEqual(before.fingerprint, after.fingerprint)

    def test_ordered_volume_and_date_changes_change_fingerprint(self) -> None:
        first = self._frame(["2011-01-03", "2026-01-02"])
        volume_changed = first.copy(deep=True)
        volume_changed.loc[1, "volume"] += 1
        date_changed = first.copy(deep=True)
        date_changed.loc[0, "date"] = "2011-01-04"

        with patch("flexible_rulebook.history._load_ticker_history", side_effect=(first, volume_changed, date_changed)):
            baseline = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))
            changed_volume = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))
            changed_date = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))

        self.assertNotEqual(baseline.fingerprint, changed_volume.fingerprint)
        self.assertNotEqual(baseline.fingerprint, changed_date.fingerprint)

    def test_evidence_anchor_accepts_append_but_rejects_correction_and_unavailable_range(self) -> None:
        old = self._frame(["2011-01-03", "2026-01-02"])
        later_window = self._frame(["2011-01-05", "2026-01-05"])
        corrected = old.copy(deep=True)
        corrected.loc[0, "volume"] += 1

        with patch("flexible_rulebook.history._load_ticker_history", return_value=old):
            historical = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 2))
        anchor: EvidenceSourceAnchor = make_evidence_source_anchor(historical)

        with patch("flexible_rulebook.history._load_ticker_history", return_value=later_window):
            later = load_flexible_history(object(), "VCB", as_of=date(2026, 1, 5))
        self.assertNotEqual(historical.fingerprint, later.fingerprint)

        with patch("flexible_rulebook.history._load_ticker_history", return_value=old):
            self.assertEqual(verify_evidence_source_anchor(object(), anchor), "match")
        with patch("flexible_rulebook.history._load_ticker_history", return_value=corrected):
            self.assertEqual(verify_evidence_source_anchor(object(), anchor), "changed")
        with patch("flexible_rulebook.history._load_ticker_history", return_value=pd.DataFrame()):
            self.assertEqual(verify_evidence_source_anchor(object(), anchor), "unavailable")


if __name__ == "__main__":
    unittest.main()
