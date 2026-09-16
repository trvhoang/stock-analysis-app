"""Live Listed/Delisted contract tests for Backtest source status."""

from datetime import date
from unittest import TestCase
from unittest.mock import patch

import pandas as pd


class _Connection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Engine:
    def __init__(self) -> None:
        self.connection = _Connection()

    def raw_connection(self) -> _Connection:
        return self.connection


class ListingStatusTests(TestCase):
    def test_exact_vnindex_latest_is_listed_and_stale_or_missing_ticker_is_delisted(self) -> None:
        from backtest_engine.listing_status import load_listing_statuses

        engine = _Engine()
        rows = pd.DataFrame(
            {
                "ticker": ["FPT", "LTG", "VNINDEX"],
                "latest_session": [
                    date(2026, 9, 8),
                    date(2026, 6, 19),
                    date(2026, 9, 8),
                ],
            }
        )
        with patch("backtest_engine.listing_status.pd.read_sql", return_value=rows) as read_sql:
            statuses = load_listing_statuses(("fpt", "LTG", "EMPTY"), engine)

        self.assertEqual(statuses["FPT"].state, "listed")
        self.assertEqual(statuses["LTG"].state, "delisted")
        self.assertEqual(statuses["EMPTY"].state, "delisted")
        self.assertEqual(statuses["FPT"].ticker_latest, date(2026, 9, 8))
        self.assertEqual(statuses["LTG"].reason, "Delisted: ticker latest 2026-06-19; VN-Index latest 2026-09-08.")
        self.assertEqual(statuses["EMPTY"].reason, "Delisted: ticker has no latest session; VN-Index latest 2026-09-08.")
        self.assertTrue(engine.connection.closed)
        self.assertIn("ticker = ANY(%(tickers)s)", read_sql.call_args.args[0])
        self.assertEqual(read_sql.call_args.kwargs["params"]["tickers"], ["FPT", "LTG", "EMPTY"])

    def test_missing_vnindex_latest_stops_status_classification_safely(self) -> None:
        from backtest_engine.listing_status import (
            VNIndexListingStatusUnavailable,
            load_listing_statuses,
        )

        engine = _Engine()
        rows = pd.DataFrame({"ticker": ["FPT"], "latest_session": [date(2026, 9, 8)]})
        with patch("backtest_engine.listing_status.pd.read_sql", return_value=rows):
            with self.assertRaisesRegex(VNIndexListingStatusUnavailable, "VN-Index"):
                load_listing_statuses(("FPT",), engine)

        self.assertTrue(engine.connection.closed)
