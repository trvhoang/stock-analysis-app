"""Behavior tests for the Current Positions read model."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from backtest_engine.position_overview import (
    build_position_trade_rows,
    load_all_positions,
    load_completed_trading_sessions,
    load_latest_close_prices,
    summarize_positions,
)
from backtest_engine.manual_position_store import create_manual_position
from backtest_engine.position_store import open_position


def _signal(metric: str = "win_rate") -> dict[str, object]:
    return {
        "metric": metric,
        "theme_variant": "no-background-theme",
        "direction": "long",
        "certified_at": "2026-08-09T09:30:00+07:00",
        "combo": {
            "direction": "long",
            "horizon": "swing",
            "theme_variant": "no-background-theme",
            "theme_mode": None,
            "threshold_score_buy": 70,
            "indicators": {"trend_direction": ["MA cross"]},
        },
    }


def _position(
    ticker: str,
    *,
    status: str = "open",
    quantity: int | None = None,
    opened_at: str = "2026-08-01T09:00:00+07:00",
) -> dict[str, object]:
    return {
        "id": f"{ticker}-{status}-{quantity}",
        "ticker": ticker,
        "theme_variant": "no-background-theme",
        "metric": "win_rate",
        "status": status,
        "certified_signal": _signal(),
        "certified_at": "2026-08-09T09:30:00+07:00",
        "entry_context": {"match_level": 86.25, "current_price": 50000},
        "risk_snapshot": {
            "atr": 1000,
            "stop_loss": 48500,
            "take_profit": 52500,
            "max_hold_bars": 15,
        },
        "actual_buy_price": 50000,
        "quantity": quantity,
        "buy_date": "2026-08-01",
        "opened_at": opened_at,
        "actual_sell_price": 52000 if status == "closed" else None,
        "sell_date": "2026-08-10" if status == "closed" else None,
        "closed_at": "2026-08-10T09:00:00+07:00" if status == "closed" else None,
        "sell_reason": "manual" if status == "closed" else None,
    }


def _manual_position(
    ticker: str = "FPT",
    *,
    status: str = "closed",
    buy_date: str = "2026-08-02",
    sell_date: str | None = "2026-08-08",
) -> dict[str, object]:
    return {
        "id": f"manual-{ticker}-{buy_date}-{sell_date}",
        "ticker": ticker,
        "status": status,
        "origin": "current_positions",
        "signal_reference": None,
        "certified_signal": None,
        "entry_context": None,
        "risk_snapshot": None,
        "actual_buy_price": 50000,
        "quantity": None,
        "buy_date": buy_date,
        "opened_at": "2026-08-02T09:00:00+07:00",
        "actual_sell_price": 52000 if status == "closed" else None,
        "sell_date": sell_date if status == "closed" else None,
        "closed_at": "2026-08-08T09:00:00+07:00" if status == "closed" else None,
        "sell_reason": "manual" if status == "closed" else None,
    }


class PositionOverviewTests(unittest.TestCase):
    def test_legacy_position_never_displays_a_saved_risk_text(self):
        legacy = _position("FPT")
        legacy["risk_suggestion_text"] = "Swing: 99.00% - very"

        buy, _sell = build_position_trade_rows(
            {"ticker": "FPT", "status": "open", "record_source": "legacy", "position": legacy}
        )

        self.assertEqual(buy["risk_suggestion_text"], "N/A")
    def test_build_position_trade_rows_keeps_open_sell_actual_values_empty(self):
        overview = summarize_positions(
            (_position("FPT", status="open"),),
            {"FPT": {"close": 51000, "date": "2026-08-10"}},
        )[0]

        buy, sell = build_position_trade_rows(overview)

        self.assertEqual(buy["trade"], "BUY")
        self.assertEqual(buy["risk_suggestion_text"], "N/A")
        self.assertFalse(buy["risk_struck"])
        self.assertEqual(sell["trade"], "SELL")
        self.assertIsNone(sell["actual_sell_price"])
        self.assertIsNone(sell["sell_date"])
        self.assertEqual(sell["suggestion"]["stop_loss"], 48500)
        self.assertEqual(sell["suggestion"]["take_profit"], 52500)

    def test_closed_position_strikes_only_a_real_risk_suggestion(self):
        position = _manual_position("VCB", status="closed", sell_date="2026-08-10")
        position["record_source"] = "manual"
        position["risk_suggestion_text"] = "Swing: 90% - very"
        overview = summarize_positions((position,), {})[0]

        buy, sell = build_position_trade_rows(overview)

        self.assertEqual(buy["risk_suggestion_text"], "Swing: 90% - very")
        self.assertTrue(buy["risk_struck"])
        self.assertEqual(sell["actual_sell_price"], 52000)
        self.assertEqual(sell["sell_date"], "2026-08-10")

    def test_no_risk_snapshot_leaves_all_sell_suggestion_fields_unavailable(self):
        overview = summarize_positions(
            (_manual_position("FPT", status="open"),),
            {"FPT": {"close": 51000, "date": "2026-08-10"}},
        )[0]

        _buy, sell = build_position_trade_rows(overview)

        self.assertEqual(
            sell["suggestion"],
            {
                "projected_exit": None,
                "suggested_holding_bars": None,
                "stop_loss": None,
                "take_profit": None,
            },
        )

    def test_load_all_positions_merges_legacy_and_generic_records_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = open_position(
                "VCB",
                "no-background-theme",
                "win_rate",
                _signal(),
                {"match_level": 86.25, "current_price": 50000},
                {"atr": 1000, "stop_loss": 48500, "take_profit": 52500, "max_hold_bars": 15},
                50000,
                "2026-08-02",
                directory,
            )
            generic = create_manual_position(
                "FPT", 50000, "2026-08-02", positions_dir=directory
            )
            records, errors = load_all_positions(directory)

        self.assertEqual({record["record_source"] for record in records}, {"legacy", "manual"})
        self.assertEqual(errors, ())
        self.assertEqual({record["id"] for record in records}, {legacy["id"], generic["id"]})

    def test_completed_sessions_exclude_buy_and_use_last_session_on_or_before_calendar_sell(self):
        sessions = {"FPT": ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-07"]}
        row = summarize_positions(
            (_manual_position(buy_date="2026-08-02", sell_date="2026-08-08"),),
            {},
            sessions,
        )[0]

        self.assertEqual(row["holding_sessions"], 4)

    def test_completed_sessions_filter_shared_ticker_rows_per_position_dates(self):
        sessions = {"FPT": ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-07"]}
        rows = summarize_positions(
            (
                _manual_position(buy_date="2026-08-02", sell_date="2026-08-08"),
                _manual_position(buy_date="2026-08-04", sell_date="2026-08-05"),
            ),
            {},
            sessions,
        )

        self.assertEqual([row["holding_sessions"] for row in rows], [4, 1])

    def test_completed_sessions_uses_one_bound_query_per_refresh(self):
        connection = Mock()
        engine = Mock()
        engine.raw_connection.return_value = connection
        frame = pd.DataFrame(
            [
                {"ticker": "FPT", "date": "2026-08-03"},
                {"ticker": "FPT", "date": "2026-08-10"},
            ]
        )
        with patch(
            "backtest_engine.position_overview.pd.read_sql", return_value=frame
        ) as read_sql:
            sessions = load_completed_trading_sessions(
                (_manual_position("FPT", status="open", sell_date=None), _manual_position("VCB", status="open", sell_date=None)),
                {"FPT": {"date": "2026-08-10"}},
                engine,
            )

        read_sql.assert_called_once()
        self.assertEqual(read_sql.call_args.kwargs["params"]["tickers"], ["FPT"])
        self.assertEqual(sessions["FPT"][-1], "2026-08-10")
        connection.close.assert_called_once()

    def test_load_all_positions_reads_existing_records_and_isolates_bad_history(self):
        with tempfile.TemporaryDirectory() as directory:
            open_position(
                "FPT",
                "no-background-theme",
                "win_rate",
                _signal(),
                {"match_level": 86.25, "current_price": 50000},
                {"atr": 1000, "stop_loss": 48500, "take_profit": 52500, "max_hold_bars": 15},
                50000,
                "2026-08-01",
                directory,
            )
            bad_file = (
                Path(directory)
                / "VCB"
                / "VCB_positions_no-background-theme_profit.json"
            )
            bad_file.parent.mkdir()
            bad_file.write_text("not-json", encoding="utf-8")
            records, errors = load_all_positions(directory)

        self.assertEqual([record["ticker"] for record in records], ["FPT"])
        self.assertEqual(len(errors), 1)

    def test_latest_prices_uses_one_bound_query_for_unique_tickers(self):
        connection = Mock()
        engine = Mock()
        engine.raw_connection.return_value = connection
        result_frame = pd.DataFrame(
            [
                {"ticker": "FPT", "date": "2026-08-10", "close": 50300},
                {"ticker": "VCB", "date": "2026-08-10", "close": 60300},
            ]
        )
        with patch(
            "backtest_engine.position_overview.pd.read_sql",
            return_value=result_frame,
        ) as read_sql:
            prices = load_latest_close_prices(("FPT", "VCB", "FPT"), engine)

        self.assertEqual(prices["FPT"]["close"], 50300)
        self.assertEqual(prices["VCB"]["date"], "2026-08-10")
        read_sql.assert_called_once()
        self.assertEqual(read_sql.call_args.kwargs["params"]["tickers"], ["FPT", "VCB"])
        connection.close.assert_called_once()

    def test_latest_prices_skips_query_for_no_open_tickers(self):
        engine = Mock()

        self.assertEqual(load_latest_close_prices((), engine), {})

        engine.raw_connection.assert_not_called()

    def test_summary_uses_latest_price_for_open_and_sell_for_closed(self):
        rows = summarize_positions(
            (
                _position("VCB", quantity=100, opened_at="2026-08-02T09:00:00+07:00"),
                _position("FPT", status="closed", opened_at="2026-08-01T09:00:00+07:00"),
            ),
            {"VCB": {"close": 55000, "date": "2026-08-10"}},
        )

        self.assertEqual([row["ticker"] for row in rows], ["FPT", "VCB"])
        self.assertEqual(rows[0]["current_price"], None)
        self.assertEqual(rows[0]["profit_raw"], 2000)
        self.assertEqual(rows[0]["profit_pct"], 4.0)
        self.assertEqual(rows[1]["current_price"], 55000)
        self.assertEqual(rows[1]["profit_raw"], 500000)
        self.assertEqual(rows[1]["profit_pct"], 10.0)
        self.assertIsNone(rows[1]["actual_sell_price"])
        self.assertIsNone(rows[1]["closed_at"])

    def test_summary_marks_open_position_without_latest_price_unavailable(self):
        row = summarize_positions((_position("FPT"),), {})[0]

        self.assertIsNone(row["current_price"])
        self.assertIsNone(row["profit_raw"])
        self.assertIsNone(row["profit_pct"])

    def test_summary_preserves_v5_saved_set_identity_for_grouped_buy_rows(self):
        position = _position("FPT")
        position["signal_reference"] = {
            "schema_version": 5,
            "horizon": "midterm",
            "rulebook_id": "midterm_rulebook_v5__rsi",
            "preferred_variant": "no-background-theme",
        }

        overview = summarize_positions((position,), {})[0]
        buy, _sell = build_position_trade_rows(overview)

        self.assertEqual(
            overview["signal_set"],
            "Mid-term — midterm_rulebook_v5__rsi — no-background-theme",
        )
        self.assertEqual(buy["signal_set"], overview["signal_set"])


if __name__ == "__main__":
    unittest.main()
