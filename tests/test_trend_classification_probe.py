import unittest
from unittest.mock import patch

import pandas as pd

from scripts.validate_trend_classification import (
    collect_probability_records,
    select_tickers,
)


class TestTrendClassificationProbe(unittest.TestCase):
    def make_result(self, ticker, total_signals=40):
        return {
            "ticker": ticker,
            "start_date": "2025-01-01",
            "end_date": "2025-01-07",
            "current_delta": 2.0,
            "total_signals": total_signals,
            "possibility_up": 40.0,
            "possibility_down": 10.0,
        }

    def test_collects_records_in_deterministic_order(self):
        calls = []

        def fake_analyzer(ticker, validation_days, result_days, engine):
            calls.append((ticker, validation_days, result_days, engine))
            return self.make_result(ticker)

        records, excluded = collect_probability_records(
            ["BBB", "AAA"], [(10, 5), (5, 5)], "engine", analyzer=fake_analyzer
        )

        self.assertEqual(excluded, [])
        self.assertEqual(
            list(zip(records["ticker"], records["validation_days"])),
            [("AAA", 5), ("AAA", 10), ("BBB", 5), ("BBB", 10)],
        )
        self.assertEqual(len(calls), 4)
        self.assertEqual(records.loc[0, "possibility_up"], 40.0)
        self.assertEqual(records.loc[0, "total_signals"], 40)

    def test_collects_none_zero_signal_and_exception_reasons(self):
        def fake_analyzer(ticker, validation_days, result_days, engine):
            if ticker == "NONE":
                return None
            if ticker == "ZERO":
                return self.make_result(ticker, total_signals=0)
            raise RuntimeError("probe failure")

        records, excluded = collect_probability_records(
            ["ERROR", "NONE", "ZERO"], [(5, 5)], "engine", analyzer=fake_analyzer
        )

        self.assertTrue(records.empty)
        self.assertEqual(
            [(row["ticker"], row["reason"]) for row in excluded],
            [
                ("ERROR", "probe failure"),
                ("NONE", "no valid signals"),
                ("ZERO", "no valid signals"),
            ],
        )

    def test_selects_tickers_with_bound_query_and_hard_limit(self):
        class FakeConnection:
            def close(self):
                pass

        class FakeEngine:
            def raw_connection(self):
                return FakeConnection()

        with patch(
            "scripts.validate_trend_classification.pd.read_sql",
            return_value=pd.DataFrame({"ticker": ["BBB", "AAA"]}),
        ) as read_sql:
            tickers = select_tickers(FakeEngine(), limit=100)

        self.assertEqual(tickers, ["AAA", "BBB"])
        query, connection = read_sql.call_args.args
        params = read_sql.call_args.kwargs["params"]
        self.assertIsNotNone(connection)
        self.assertIn("%(excluded_ticker)s", query)
        self.assertEqual(params["ticker_limit"], 64)


if __name__ == "__main__":
    unittest.main()
