"""Focused contracts for pure Backtest Lab page helpers."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from backtest_engine.listing_status import ListingStatus
from pages import backtest_lab
from pages.backtest_lab import (
    _delete_by_locator,
    _display_price,
    _display_win_rate,
    _create_position_from_form,
    _load_position_overview,
    _overview_position_id,
    _position_date_value,
    _position_delete_summary,
    _position_row_locator,
    _position_horizon,
    _position_selection_widget_key,
    _pruned_selection,
    _raw_current_value,
    _saved_set_label,
    _ticker_chunks,
    _validated_delete_locator,
    _validation_result_for_ticker,
    _validation_tickers,
    _visible_position_ids,
    _view_metric,
    format_job_status,
    parse_batch_tickers,
    schedule_status_refresh,
)


class BacktestLabHelperTests(unittest.TestCase):
    def test_group_manager_projection_filters_live_status_without_mutating_groups(self) -> None:
        build_rows = getattr(backtest_lab, "_group_manager_rows", None)
        filter_rows = getattr(backtest_lab, "_filter_group_manager_rows", None)
        self.assertTrue(callable(build_rows))
        self.assertTrue(callable(filter_rows))
        latest = pd.Timestamp("2026-09-08").date()
        rows = build_rows(
            (
                SimpleNamespace(group_name="BANK", tickers=("VCB", "LTG")),
                SimpleNamespace(group_name="EMPTY", tickers=()),
            ),
            {
                "VCB": ListingStatus("VCB", "listed", latest, latest),
                "LTG": ListingStatus("LTG", "delisted", pd.Timestamp("2026-06-19").date(), latest),
            },
        )

        self.assertEqual("Listed", rows[0]["Status"])
        self.assertEqual("Delisted", rows[1]["Status"])
        self.assertEqual("—", rows[2]["Ticker"])
        self.assertEqual(
            [rows[0]],
            filter_rows(rows, ticker="vcb", states=("Listed",), group_name="BANK"),
        )
        self.assertEqual(3, len(rows))

    def test_parse_batch_tickers_normalizes_deduplicates_and_bounds_input(self) -> None:
        self.assertEqual(parse_batch_tickers(" fpt, VCB fpt\nree "), ("FPT", "VCB", "REE"))
        with self.assertRaisesRegex(ValueError, "between 1 and 15"):
            parse_batch_tickers("  ")
        with self.assertRaisesRegex(ValueError, "between 1 and 2"):
            parse_batch_tickers("FPT VCB REE", maximum=2)

    def test_validation_tickers_uses_manual_or_selected_group_contract(self) -> None:
        self.assertEqual(
            _validation_tickers("fpt, vcb", "-", "/signals", MagicMock()),
            ("FPT", "VCB"),
        )
        resolver = MagicMock(return_value=("VCB", "REE"))
        self.assertEqual(
            _validation_tickers("ignored", "Large cap", "/signals", resolver),
            ("VCB", "REE"),
        )
        resolver.assert_called_once_with("Large cap", "/signals")
        with self.assertRaisesRegex(ValueError, "has no tickers"):
            _validation_tickers("", "Empty", "/signals", lambda *_: ())

    def test_ticker_chunks_and_validation_result_preserve_batch_identity(self) -> None:
        tickers = ("FPT", "VCB", "REE", "HPG", "MSN")
        self.assertEqual(_ticker_chunks(tickers, size=2), (("FPT", "VCB"), ("REE", "HPG"), ("MSN",)))
        single = {"ticker": "FPT", "result": "single"}
        batch = {"by_ticker": {"VCB": {"ticker": "VCB", "result": "batch"}}}
        self.assertEqual(_validation_result_for_ticker(single, "FPT"), single)
        self.assertEqual(_validation_result_for_ticker(batch, "VCB"), batch["by_ticker"]["VCB"])
        self.assertIsNone(_validation_result_for_ticker(batch, "FPT"))
        self.assertIsNone(_validation_result_for_ticker("bad", "FPT"))

    def test_status_refresh_and_rendering_are_deterministic(self) -> None:
        sleep = MagicMock()
        rerun = MagicMock()
        schedule_status_refresh(False, sleep, rerun)
        sleep.assert_not_called()
        rerun.assert_not_called()
        schedule_status_refresh(True, sleep, rerun)
        sleep.assert_called_once_with(1)
        rerun.assert_called_once_with()
        self.assertEqual(format_job_status(SimpleNamespace(state="running", progress=0.456)), "Running — 46%")
        self.assertEqual(format_job_status(SimpleNamespace(state="requires_regeneration", progress=0)), "Requires regeneration — 100%")
        self.assertEqual(
            backtest_lab.format_ticker_result(
                SimpleNamespace(
                    ticker="LTG",
                    state="skipped",
                    error_texts=(
                        "Delisted: ticker latest 2026-06-19; VN-Index latest 2026-09-08.",
                    ),
                )
            ),
            "LTG: skipped — Delisted: ticker latest 2026-06-19; VN-Index latest 2026-09-08.",
        )
        self.assertEqual(_view_metric(None), "N/A")
        self.assertEqual(_view_metric(pd.NA), "N/A")
        self.assertEqual(_view_metric(1.234, 1), "1.2")

    def test_validation_win_rate_display_uses_one_decimal_half_up(self) -> None:
        self.assertEqual(_display_win_rate("52.67857142857143"), "52.7%")
        self.assertEqual(_display_win_rate("51.61290322580645"), "51.6%")
        self.assertEqual(_display_win_rate("52.65"), "52.7%")
        self.assertEqual(_display_win_rate(None), "—")

    def test_saved_set_and_raw_price_helpers_reject_ambiguous_values(self) -> None:
        saved = {
            "signal_reference": {
                "schema_version": 5,
                "horizon": "swing",
                "rulebook_id": "rule-1",
                "preferred_variant": "no-theme",
            }
        }
        self.assertEqual(_position_horizon(saved), "swing")
        self.assertEqual(_saved_set_label(saved), "Swing — rule-1 — no-theme")
        self.assertEqual(_saved_set_label({}), "Historical saved set")
        self.assertEqual(_raw_current_value("20125", "latest_close"), 20125)
        for value in (0, -1, 1.5, "bad"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "positive raw integer"):
                    _raw_current_value(value, "latest_close")

    def test_position_identity_helpers_preserve_visible_selection_only(self) -> None:
        rows = ({"id": "one"}, {"id": "two"})
        visible = _visible_position_ids(rows)
        self.assertEqual(visible, ("one", "two"))
        self.assertEqual(_pruned_selection({"one", "hidden"}, visible), {"one"})
        self.assertEqual(_position_selection_widget_key("one"), "backtest_position_select_v4_one")
        with self.assertRaisesRegex(ValueError, "non-empty id"):
            _overview_position_id({"id": ""})

    def test_position_locator_validation_and_delete_routing_are_explicit(self) -> None:
        manual = {"record_source": "manual", "ticker": "FPT", "id": "manual-1"}
        legacy = {
            "record_source": "legacy", "ticker": "VCB", "id": "old-1",
            "theme_variant": "no-theme", "metric": "win_rate",
        }
        self.assertEqual(_position_row_locator({"position_locator": manual}), manual)
        self.assertEqual(_validated_delete_locator(manual), manual)
        manual_delete, legacy_delete = MagicMock(return_value={"ok": True}), MagicMock(return_value={"ok": True})
        self.assertEqual(_delete_by_locator(manual, "/positions", legacy_delete, manual_delete), {"ok": True})
        manual_delete.assert_called_once_with("FPT", "manual-1", "/positions")
        self.assertEqual(_delete_by_locator(legacy, "/positions", legacy_delete, manual_delete), {"ok": True})
        legacy_delete.assert_called_once_with("VCB", "no-theme", "win_rate", "old-1", "/positions")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            _validated_delete_locator({"record_source": "manual", "ticker": "FPT"})

    def test_position_display_helpers_handle_missing_values_without_raw_leaks(self) -> None:
        self.assertEqual(_display_price(20125), 20.125)
        self.assertEqual(_display_price("bad"), "-")
        self.assertEqual(_position_delete_summary({"ticker": "fpt", "status": "open", "actual_buy_price": 20125}), "fpt — OPEN — BUY 20.125 k VND")
        self.assertEqual(_position_date_value("not-a-date", fallback=pd.Timestamp("2026-08-14").date()), pd.Timestamp("2026-08-14").date())

    @patch("pages.backtest_lab.create_manual_position")
    def test_create_position_form_preserves_manual_and_saved_signal_contracts(self, create_position) -> None:
        buy_date = pd.Timestamp("2026-08-14").date()
        _create_position_from_form(
            "FPT", "Manual P&L only", {}, 20.125, buy_date, 0, "/positions"
        )
        create_position.assert_called_once_with(
            "FPT", 20125, buy_date, quantity=None, positions_dir="/positions"
        )

        create_position.reset_mock()
        candidate = {
            "current": {"latest_close": 20125, "latest_atr": 500.5, "as_of_date": "2026-08-14"},
            "signal_date": "2026-08-12",
            "monitoring": {"match_level": 0.75},
            "horizon": "swing",
            "signal_reference": {"schema_version": 5, "rulebook_id": "rule-1"},
        }
        _create_position_from_form(
            "FPT", "Swing — rule-1", {"Swing — rule-1": candidate}, 20.125, buy_date, 100, "/positions"
        )
        kwargs = create_position.call_args.kwargs
        self.assertEqual(create_position.call_args.args[:3], ("FPT", 20125, buy_date))
        self.assertEqual(kwargs["quantity"], 100)
        self.assertEqual(kwargs["entry_context"]["current_price"], 20125)
        self.assertEqual(kwargs["entry_context"]["match_level"], 0.75)
        self.assertEqual(kwargs["entry_context"]["signal_date"], "2026-08-12")
        self.assertEqual(
            kwargs["risk_snapshot"],
            {"atr": 501, "stop_loss": 19374, "take_profit": 21378, "max_hold_bars": 22},
        )
        self.assertEqual(kwargs["positions_dir"], "/positions")

        create_position.reset_mock()
        flexible = {
            **candidate,
            "signal_reference": {
                "schema_version": 6,
                "origin": "flexible",
                "rulebook_id": "frb2_" + "a" * 64,
            },
        }
        _create_position_from_form(
            "FPT", "Swing — Flexible", {"Swing — Flexible": flexible},
            20.125, buy_date, 100, "/positions",
        )
        self.assertIsNone(create_position.call_args.kwargs["risk_snapshot"])

    @patch("pages.backtest_lab.create_manual_position")
    def test_create_position_form_rejects_delisted_ticker_before_any_position_write(self, create_position) -> None:
        with self.assertRaisesRegex(ValueError, "Delisted"):
            _create_position_from_form(
                "LTG", "Manual P&L only", {}, 20.125,
                pd.Timestamp("2026-09-08").date(), 100, "/positions",
                listing_guard=lambda _ticker: (_ for _ in ()).throw(
                    ValueError("Delisted: ticker latest 2026-06-19; VN-Index latest 2026-09-08.")
                ),
            )
        create_position.assert_not_called()

    @patch("pages.backtest_lab.summarize_positions", return_value=[{"ticker": "FPT"}])
    @patch("pages.backtest_lab.load_completed_trading_sessions", return_value={"FPT": ["2026-08-14"]})
    @patch("pages.backtest_lab.load_latest_close_prices", return_value={"FPT": {"close": 20125}})
    @patch("pages.backtest_lab.load_all_positions")
    def test_load_position_overview_reuses_one_coherent_read_snapshot(self, load_all, load_latest, load_sessions, summarize):
        records = [{"ticker": "FPT", "status": "open"}]
        load_all.return_value = (records, ["legacy warning"])
        engine = MagicMock()

        overview = _load_position_overview(engine, "/positions")

        self.assertEqual(overview, {"rows": [{"ticker": "FPT"}], "errors": ["legacy warning"]})
        load_all.assert_called_once_with("/positions")
        self.assertEqual(tuple(load_latest.call_args.args[0]), ("FPT",))
        self.assertIs(load_latest.call_args.args[1], engine)
        load_sessions.assert_called_once_with(records, {"FPT": {"close": 20125}}, engine)
        summarize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
