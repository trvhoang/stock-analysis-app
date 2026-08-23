import unittest
from unittest.mock import patch

import pandas as pd

from backtest_engine.data_quality import (
    audit_history,
    history_coverage_years,
    load_ticker_history,
    normalize_ohlc_for_backtest,
    validate_ohlcv,
)


REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def make_valid_frame():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"]),
            "open": pd.Series([50300, 50400, 50500], dtype="int64"),
            "high": pd.Series([50600, 50700, 50800], dtype="int64"),
            "low": pd.Series([50000, 50100, 50200], dtype="int64"),
            "close": pd.Series([50400, 50500, 50600], dtype="int64"),
            "volume": pd.Series([1000, 0, 1200], dtype="int64"),
        }
    )


class DataQualityTests(unittest.TestCase):
    def test_closed_weekly_coverage_uses_the_w_fri_label_cutoff(self):
        history = pd.DataFrame(
            {
                "date": pd.to_datetime(["2021-08-20", "2026-08-20"]),
                "open": [50_000, 50_000],
                "high": [51_000, 51_000],
                "low": [49_000, 49_000],
                "close": [50_000, 50_000],
                "volume": [1_000, 1_000],
            }
        )

        friday = history_coverage_years(history, today=pd.Timestamp("2026-08-21").date())
        saturday = history_coverage_years(history, today=pd.Timestamp("2026-08-22").date())
        monday = history_coverage_years(history, today=pd.Timestamp("2026-08-24").date())

        self.assertEqual(saturday["midterm_history_years"], monday["midterm_history_years"])
        self.assertGreater(saturday["midterm_history_years"], friday["midterm_history_years"])
        self.assertGreaterEqual(saturday["swing_history_years"], 5.0)

    def test_missing_columns_are_structural_errors(self):
        report = validate_ohlcv(make_valid_frame().drop(columns="volume"))

        self.assertFalse(report.is_valid)
        self.assertIsNone(report.valid_frame)
        self.assertTrue(any("volume" in error for error in report.errors))

    def test_duplicate_or_unsorted_dates_block_indicators(self):
        duplicate = make_valid_frame()
        duplicate.loc[2, "date"] = duplicate.loc[1, "date"]
        unsorted = make_valid_frame().iloc[[1, 0, 2]].reset_index(drop=True)

        duplicate_report = validate_ohlcv(duplicate)
        unsorted_report = validate_ohlcv(unsorted)

        self.assertFalse(duplicate_report.is_valid)
        self.assertTrue(any("duplicate" in error.lower() for error in duplicate_report.errors))
        self.assertFalse(unsorted_report.is_valid)
        self.assertTrue(any("order" in error.lower() for error in unsorted_report.errors))

    def test_missing_or_non_positive_prices_block_indicators(self):
        invalid = make_valid_frame()
        invalid.loc[0, "close"] = 0
        invalid.loc[1, "low"] = pd.NA

        report = validate_ohlcv(invalid)

        self.assertFalse(report.is_valid)
        self.assertGreaterEqual(len(report.errors), 2)

    def test_minor_ohlc_order_mismatch_warns_without_blocking_indicators(self):
        invalid = make_valid_frame()
        invalid.loc[0, "high"] = invalid.loc[0, "close"] - 1
        invalid.loc[1, "low"] = invalid.loc[1, "open"] + 1

        report = validate_ohlcv(invalid)
        audit = audit_history("AAA", invalid)

        self.assertTrue(report.is_valid)
        self.assertEqual(audit.status, "clean")
        self.assertTrue(any("OHLC" in warning for warning in audit.warnings))

    def test_material_ohlc_mismatch_is_audit_invalid(self):
        invalid = make_valid_frame()
        invalid.loc[0, "high"] = 49_000

        audit = audit_history("AAA", invalid)

        self.assertEqual(audit.status, "invalid")
        self.assertTrue(any("1.00%" in error for error in audit.errors))

    def test_backtest_envelope_repairs_only_the_derived_frame(self):
        source = make_valid_frame()
        source.loc[0, "high"] = source.loc[0, "close"] - 1
        source.loc[1, "low"] = source.loc[1, "open"] + 1

        normalized = normalize_ohlc_for_backtest(source)

        self.assertEqual(normalized.loc[0, "high"], source.loc[0, "close"])
        self.assertEqual(normalized.loc[1, "low"], source.loc[1, "open"])
        self.assertEqual(source.loc[0, "high"], source.loc[0, "close"] - 1)
        self.assertEqual(source.loc[1, "low"], source.loc[1, "open"] + 1)

    def test_zero_volume_is_explicit_warning_not_structural_failure(self):
        report = validate_ohlcv(make_valid_frame())

        self.assertTrue(report.is_valid)
        self.assertTrue(any("zero volume" in warning.lower() for warning in report.warnings))

    def test_large_close_move_is_warning_and_does_not_mutate_raw_values(self):
        source = make_valid_frame()
        source.loc[1, "close"] = 55000
        source.loc[1, "high"] = 55100
        source.loc[1, "low"] = 50300
        raw_close = source["close"].copy()

        report = validate_ohlcv(source)

        self.assertTrue(report.is_valid)
        self.assertTrue(any("7%" in warning for warning in report.warnings))
        pd.testing.assert_series_equal(report.valid_frame["close"], raw_close)
        pd.testing.assert_series_equal(source["close"], raw_close)

    def test_weekend_gap_is_not_flagged_but_long_gap_is_explicit_finding(self):
        weekend = make_valid_frame()
        weekend.loc[2, "date"] = pd.Timestamp("2025-01-06")
        long_gap = weekend.copy()
        long_gap.loc[2, "date"] = pd.Timestamp("2025-01-20")

        weekend_report = validate_ohlcv(weekend)
        long_gap_report = validate_ohlcv(long_gap)

        self.assertFalse(any("gap" in warning.lower() for warning in weekend_report.warnings))
        self.assertTrue(any("gap" in warning.lower() for warning in long_gap_report.warnings))
        self.assertTrue(long_gap_report.is_valid)

    def test_history_loader_uses_bound_parameters_and_closes_raw_connection(self):
        class FakeConnection:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class FakeEngine:
            def __init__(self, connection):
                self.connection = connection

            def raw_connection(self):
                return self.connection

        connection = FakeConnection()
        engine = FakeEngine(connection)
        returned = make_valid_frame()

        with patch("backtest_engine.data_quality.pd.read_sql", return_value=returned) as read_sql:
            result = load_ticker_history("FPT", "2025-01-01", "2025-01-31", engine)

        query = read_sql.call_args.args[0]
        params = read_sql.call_args.kwargs["params"]
        self.assertIn("%(ticker)s", query)
        self.assertIn("%(start_date)s", query)
        self.assertIn("%(end_date)s", query)
        self.assertNotIn("FPT", query)
        self.assertEqual(params["ticker"], "FPT")
        self.assertEqual(params["start_date"], "2025-01-01")
        self.assertEqual(params["end_date"], "2025-01-31")
        self.assertTrue(connection.closed)
        pd.testing.assert_frame_equal(result, returned)


if __name__ == "__main__":
    unittest.main()
