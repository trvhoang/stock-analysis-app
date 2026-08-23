import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from backtest_engine import data_quality

try:
    from backtest_engine import universe_audit
except ImportError:
    universe_audit = None


def make_history(pre_2021_close: int, latest_close: int) -> pd.DataFrame:
    dates = list(pd.date_range("2011-08-09", "2020-12-31", periods=11))
    dates.append(pd.Timestamp("2026-08-07"))
    pre_2021_prices = [
        round(100_000 * (pre_2021_close / 100_000) ** (step / 10))
        for step in range(11)
    ]
    pre_2021_prices[-1] = pre_2021_close
    return pd.DataFrame(
        {
            "date": dates,
            "open": [*pre_2021_prices, latest_close],
            "high": [*(value + 1_000 for value in pre_2021_prices), latest_close + 1_000],
            "low": [*(value - 1_000 for value in pre_2021_prices), latest_close - 1_000],
            "close": [*pre_2021_prices, latest_close],
            "volume": [1_000 + step * 100 for step in range(12)],
        }
    )


def make_continuous_history(start: str, end: str) -> pd.DataFrame:
    dates = pd.bdate_range(start, end)
    return pd.DataFrame(
        {
            "date": dates,
            "open": [50_000] * len(dates),
            "high": [51_000] * len(dates),
            "low": [49_000] * len(dates),
            "close": [50_000] * len(dates),
            "volume": [1_000] * len(dates),
        }
    )


class PriceAuditTests(unittest.TestCase):
    def test_factor_like_move_is_indeterminate_without_mutating_raw_prices(self):
        source = make_history(100_000, 130_000)
        source.loc[source.index[-2], "close"] = 100_000
        source.loc[source.index[-1], "close"] = 115_000
        source.loc[source.index[-1], ["open", "high", "low"]] = [115_000, 116_000, 114_000]
        raw_close = source["close"].copy()

        audit_history = getattr(data_quality, "audit_history", None)
        audit = audit_history("AAA", source) if audit_history is not None else None

        self.assertIsNotNone(audit_history)
        self.assertEqual(getattr(audit, "status", None), "indeterminate")
        self.assertEqual(len(getattr(audit, "findings", ())), 1)
        self.assertEqual(audit.findings[0].close_return_pct, 15.0)
        pd.testing.assert_series_equal(source["close"], raw_close)

    def test_missing_required_coverage_is_excluded_as_invalid(self):
        audit_history = getattr(data_quality, "audit_history", None)
        audit = (
            audit_history(
                "AAA",
                make_history(110_000, 120_000).iloc[1:].reset_index(drop=True),
                required_start_date=date(2011, 8, 9),
                required_end_date=date(2026, 8, 9),
                expected_terminal_date=date(2026, 8, 7),
            )
            if audit_history is not None
            else None
        )

        self.assertIsNotNone(audit_history)
        self.assertEqual(getattr(audit, "status", None), "invalid")
        self.assertTrue(any("coverage" in error for error in getattr(audit, "errors", ())))

    def test_suspicious_volume_cannot_explain_away_a_close_discontinuity(self):
        source = make_history(100_000, 115_000)
        source.loc[source.index[-1], ["open", "high", "low"]] = [115_000, 116_000, 114_000]
        source.loc[source.index[-1], "volume"] = 99_999_999
        audit_history = getattr(data_quality, "audit_history", None)
        audit = audit_history("AAA", source) if audit_history is not None else None

        self.assertIsNotNone(audit_history)
        self.assertEqual(getattr(audit, "status", None), "indeterminate")
        self.assertEqual(audit.findings[0].volume_ratio, 99_999_999 / 2_000)


class FrozenUniverseTests(unittest.TestCase):
    def test_roster_audit_keeps_cleanliness_separate_from_history_coverage(self):
        auditor = (
            getattr(universe_audit, "audit_frozen_roster", None)
            if universe_audit is not None
            else None
        )
        roster = ("VCB", "REE")
        history = {
            "VCB": make_continuous_history("2016-08-01", "2026-08-20"),
            "REE": make_continuous_history("2020-08-01", "2026-08-20"),
        }

        self.assertIsNotNone(auditor)
        if auditor is None:
            return
        with patch(
            "backtest_engine.universe_audit.load_ticker_history",
            side_effect=lambda ticker, *_args: history[ticker],
        ), patch(
            "backtest_engine.universe_audit.load_frozen_roster_histories",
            return_value=history,
        ) as load_histories:
            report = auditor(roster, object(), today=date(2026, 8, 22))

        load_histories.assert_called_once_with(
            roster,
            date(1900, 1, 1),
            date(2026, 8, 22),
            unittest.mock.ANY,
        )

        self.assertEqual(tuple(item["ticker"] for item in report), roster)
        self.assertTrue(
            all(
                {
                    "price_audit_clean",
                    "study_history_sufficient",
                    "swing_history_years",
                    "midterm_history_years",
                } <= set(item)
                for item in report
            )
        )
        self.assertTrue(report[0]["price_audit_clean"])
        self.assertTrue(report[0]["study_history_sufficient"])
        self.assertTrue(report[1]["price_audit_clean"])
        self.assertFalse(report[1]["study_history_sufficient"])

    def _audits(self):
        returns = {
            "AAA": 190_000,
            "BBB": 170_000,
            "CCC": 20_000,
            "DDD": 40_000,
            "EEE": 100_000,
            "FFF": 105_000,
            "GGG": 115_000,
            "HHH": 125_000,
            "VCB": 110_000,
        }
        audit_history = getattr(data_quality, "audit_history", None)
        if audit_history is None:
            return ()
        return tuple(
            audit_history(ticker, make_history(pre_2021_close, pre_2021_close))
            for ticker, pre_2021_close in returns.items()
        )

    def test_selection_is_deterministic_and_uses_pre_2021_returns(self):
        selector = (
            getattr(universe_audit, "select_frozen_universe", None)
            if universe_audit is not None
            else None
        )

        selected = selector(self._audits()) if selector is not None else ()

        self.assertIsNotNone(selector)
        self.assertEqual(
            selected,
            ("VCB", "AAA", "BBB", "CCC", "DDD", "FFF", "GGG", "EEE"),
        )

    def test_vcb_is_required_clean_canary(self):
        selector = (
            getattr(universe_audit, "select_frozen_universe", None)
            if universe_audit is not None
            else None
        )
        audits = tuple(audit for audit in self._audits() if audit.ticker != "VCB")

        self.assertIsNotNone(selector)
        with self.assertRaisesRegex(ValueError, "VCB"):
            selector(audits)

    def test_candidate_audit_uses_the_shared_available_history_bounds(self):
        auditor = (
            getattr(universe_audit, "audit_candidates", None)
            if universe_audit is not None
            else None
        )
        full_history = make_history(110_000, 110_000)
        full_history.loc[0, "date"] = pd.Timestamp("2011-08-15")
        full_history.loc[full_history.index[-1], "date"] = pd.Timestamp("2026-08-10")
        late_history = full_history.iloc[1:].reset_index(drop=True)

        audits = auditor({"VCB": full_history, "LATE": late_history}) if auditor else ()
        by_ticker = {audit.ticker: audit for audit in audits}

        self.assertIsNotNone(auditor)
        self.assertEqual(by_ticker["VCB"].status, "clean")
        self.assertEqual(by_ticker["LATE"].status, "invalid")
        self.assertTrue(any("coverage starts" in error for error in by_ticker["LATE"].errors))

    def test_candidate_loader_uses_one_parameterized_raw_connection_query(self):
        loader = (
            getattr(universe_audit, "load_audit_candidates", None)
            if universe_audit is not None
            else None
        )

        class FakeConnection:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class FakeEngine:
            def __init__(self):
                self.connection = FakeConnection()

            def raw_connection(self):
                return self.connection

        engine = FakeEngine()
        self.assertIsNotNone(loader)
        if loader is None:
            return
        with patch(
            "backtest_engine.universe_audit.pd.read_sql",
            return_value=make_history(110_000, 120_000).assign(ticker="AAA"),
        ) as read_sql:
            result = loader(engine, date(2011, 8, 9), date(2026, 8, 9))

        self.assertEqual(tuple(result), ("AAA",))
        query = read_sql.call_args.args[0]
        self.assertIn("%(start_date)s", query)
        self.assertIn("%(end_date)s", query)
        self.assertIn("%(index_ticker)s", query)
        self.assertTrue(engine.connection.closed)


if __name__ == "__main__":
    unittest.main()
