"""Backtest Lab schema-5 UI copy, identity, and position-group contracts."""

from __future__ import annotations

from datetime import date
import inspect
import tempfile
import unittest
from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

from backtest_engine.manual_position_store import (
    create_manual_position,
    load_manual_position_history,
)
from pages import backtest_lab


class BacktestPageTests(unittest.TestCase):
    @staticmethod
    def _position_row(
        position_id: str = "manual-1",
        ticker: str = "FPT",
        status: str = "open",
        *,
        record_source: str = "manual",
        risk_suggestion_text: str | None = None,
    ) -> dict[str, object]:
        is_closed = status == "closed"
        locator: dict[str, object] = {
            "record_source": record_source,
            "ticker": ticker,
            "id": position_id,
        }
        if record_source == "legacy":
            locator.update(
                {
                    "theme_variant": "no-background-theme",
                    "metric": "win_rate",
                }
            )
        position: dict[str, object] = {
            "id": position_id,
            "ticker": ticker,
            "status": status,
            "actual_buy_price": 50000,
            "actual_sell_price": 52000 if is_closed else None,
            "quantity": None,
            "buy_date": "2026-08-01",
            "sell_date": "2026-08-10" if is_closed else None,
            "opened_at": "2026-08-01T09:00:00+07:00",
            "closed_at": "2026-08-10T09:00:00+07:00" if is_closed else None,
            "risk_snapshot": {
                "max_hold_bars": 22,
                "stop_loss": 48500,
                "take_profit": 52500,
            },
            "record_source": record_source,
            "position_locator": locator,
        }
        if record_source == "legacy":
            position.update(
                {
                    "theme_variant": "no-background-theme",
                    "metric": "win_rate",
                }
            )
        if risk_suggestion_text is not None:
            position["risk_suggestion_text"] = risk_suggestion_text
        return {
            "id": position_id,
            "ticker": ticker,
            "status": status,
            "actual_buy_price": 50000,
            "actual_sell_price": 52000 if is_closed else None,
            "quantity": None,
            "current_price": None if is_closed else 51000,
            "profit_raw": 2000 if is_closed else 1000,
            "profit_pct": 4.0 if is_closed else 2.0,
            "opened_at": position["opened_at"],
            "closed_at": position["closed_at"],
            "buy_date": "2026-08-01",
            "sell_date": position["sell_date"],
            "holding_sessions": 5 if is_closed else 4,
            "signal_set": "-",
            "record_source": record_source,
            "position_locator": locator,
            "position": position,
        }

    def _grouped_positions_app(self, rows, *, positions_dir="unused-positions"):
        return AppTest.from_string(
            "from pages.backtest_lab import render_backtest_page\n"
            "from backtest_engine.listing_status import ListingStatus\n"
            "from datetime import date\n"
            f"rows = {rows!r}\n"
            "def listing_statuses(tickers, _engine):\n"
            "    latest = date(2026, 9, 8)\n"
            "    return {ticker: ListingStatus(ticker, 'listed', latest, latest) for ticker in tickers}\n"
            "render_backtest_page(\n"
            "    engine=object(), status_dir='unused-status-dir',\n"
            "    signal_dir='unused-signal-dir',\n"
            f"    positions_dir={positions_dir!r},\n"
            "    position_overview_fn=lambda engine, positions_dir: "
            "{'rows': rows, 'errors': ()},\n"
            "    listing_statuses_fn=listing_statuses,\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

    @staticmethod
    def _validation_group_app(
        group_tickers=("VCB", "TCB"), failing_ticker=None, delisted_tickers=()
    ):
        return AppTest.from_string(
            "import streamlit as st\n"
            "from datetime import date\n"
            "from backtest_engine.listing_status import ListingStatus\n"
            "from pages.backtest_lab import render_backtest_page\n"
            f"group_tickers = {group_tickers!r}\n"
            f"delisted_tickers = {delisted_tickers!r}\n"
            "def group_choices(_signal_dir):\n"
            "    return ('-', 'N/A', 'ALL', 'BANK', 'TECH')\n"
            "def group_resolver(group_name, _signal_dir):\n"
            "    return group_tickers if group_name in ('ALL', 'BANK') else ('FPT', 'HPG') if group_name == 'TECH' else ()\n"
            "def validate(ticker, *_args):\n"
            "    st.session_state['validation_calls'] = st.session_state.get('validation_calls', []) + [ticker]\n"
            f"    if ticker == {failing_ticker!r}:\n"
            "        raise ValueError('broken artifact')\n"
            "    return {'ticker': ticker, 'results': [], 'historical_positions': []}\n"
            "def listing_statuses(tickers, _engine):\n"
            "    latest = date(2026, 9, 9)\n"
            "    return {ticker: ListingStatus(ticker, 'delisted' if ticker in delisted_tickers else 'listed', date(2026, 6, 19) if ticker in delisted_tickers else latest, latest) for ticker in tickers}\n"
            "render_backtest_page(\n"
            "    engine=object(), status_dir='unused-status', signal_dir='unused-signals',\n"
            "    positions_dir='unused-positions', validate_fn=validate,\n"
            "    group_choices_fn=group_choices, group_resolver_fn=group_resolver,\n"
            "    listing_statuses_fn=listing_statuses,\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

    @staticmethod
    def _collect_group_app():
        return AppTest.from_string(
            "import streamlit as st\n"
            "from types import SimpleNamespace\n"
            "from pages.backtest_lab import render_backtest_page\n"
            "def group_choices(_signal_dir):\n"
            "    return ('-', 'N/A', 'ALL', 'BANK', 'TECH')\n"
            "def group_resolver(group_name, _signal_dir):\n"
            "    return ('VCB', 'TCB') if group_name in ('ALL', 'BANK') else ('FPT', 'HPG') if group_name == 'TECH' else ()\n"
            "def submit(config, *_args):\n"
            "    st.session_state['collect_group_config'] = config.to_dict()\n"
            "    return 'collect-job'\n"
            "render_backtest_page(\n"
            "    engine=object(), engine_factory=lambda: None, status_dir='unused-status',\n"
            "    signal_dir='unused-signals', positions_dir='unused-positions',\n"
            "    submit_fn=submit, group_choices_fn=group_choices,\n"
            "    group_resolver_fn=group_resolver,\n"
            "    read_status_fn=lambda *_args: SimpleNamespace(state='queued', progress=0.0, output_paths=()),\n"
            "    schedule_refresh_fn=lambda *_args: None,\n"
            "    position_overview_fn=lambda engine, positions_dir: {'rows': [], 'errors': ()},\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

    @staticmethod
    def _position_select_widgets(app):
        return [item for item in app.checkbox if item.label == "Select"]

    def test_collect_has_no_theme_checkbox_and_uses_v5_request(self):
        source = inspect.getsource(backtest_lab)
        config = backtest_lab.build_backtest_batch_config(("FPT",), "swing", "15y")
        self.assertNotIn('checkbox("VN-Index AND treatment"', source)
        self.assertNotIn('checkbox("Include VN-Index AND"', source)
        self.assertEqual(config.to_dict()["request_type"], "backtest_batch_v5")

    def test_collect_defaults_to_lifetime_and_marks_the_worker_request(self):
        config = backtest_lab.build_backtest_batch_config(("FPT",), "swing", "Lifetime")
        app = self._collect_group_app()

        self.assertEqual("Lifetime", backtest_lab.TIME_RANGE_OPTIONS[0])
        self.assertTrue(config.use_lifetime_range)
        self.assertIsNone(config.start_date)
        self.assertIsNone(config.end_date)
        self.assertEqual("Lifetime", next(item for item in app.selectbox if item.label == "Range").value)

    def test_collect_horizon_defaults_to_both_and_queues_each_horizon_serially(self):
        app = self._collect_group_app()
        horizon = next(
            item for item in app.selectbox
            if item.key == "backtest_collect_horizon_v4"
        )

        configs = backtest_lab._collect_batch_configs(
            ("FPT", "VCB"), ("swing", "midterm"), "Lifetime", "N/A"
        )

        self.assertEqual(horizon.options, ["Both", "Swing", "Mid-term"])
        self.assertEqual(horizon.value, "Both")
        self.assertEqual([config.horizon for config in configs], ["swing", "midterm"])
        self.assertEqual(
            [config.tickers for config in configs], [("FPT", "VCB"), ("FPT", "VCB")]
        )

    def test_view_signal_rows_show_only_summary_train_test_columns(self):
        rows = backtest_lab._view_signal_rows(
            [
                {
                    "Ticker": "VCB",
                    "Horizon": "Swing",
                    "Evidence": "eligible",
                    "Preferred treatment": "background-theme",
                    "Training n": 5,
                    "Test n": 0,
                    "Training win rate %": 60.0,
                    "Test win rate %": None,
                    "Training profit %": 3.2,
                    "Test profit %": -1.0,
                    "Training Sharpe": 0.4,
                    "Test Sharpe": None,
                    "Rulebook": "hidden",
                    "Selected gates": ["hidden"],
                    "Treatments": {"hidden": True},
                    "Evaluation": "hidden",
                }
            ]
        )

        self.assertEqual(
            list(rows[0]),
            [
                "Ticker",
                "Horizon",
                "Evidence",
                "Theme",
                "Train-test",
                "n",
                "Win rate %",
                "Profit %",
                "Sharpe",
                "_ticker",
                "_horizon",
                "_rulebook_id",
            ],
        )
        self.assertEqual(
            rows[0],
            {
                "Ticker": "VCB",
                "Horizon": "Swing",
                "Evidence": "eligible",
                "Theme": "Included",
                "Train-test": "YES",
                "n": "5 - 0",
                "Win rate %": "60.0 - N/A",
                "Profit %": "3.2 - -1.0",
                "Sharpe": "0.4 - N/A",
                "_ticker": "VCB",
                "_horizon": "swing",
                "_rulebook_id": "hidden",
            },
        )

    def test_view_signal_metric_pairs_round_only_decimal_metrics(self):
        rows = backtest_lab._view_signal_rows(
            [{
                "Ticker": "VCB", "Horizon": "Swing", "Rulebook": "hidden",
                "Preferred treatment": "no-background-theme",
                "Training n": 5, "Test n": 0,
                "Training win rate %": 60.04, "Test win rate %": None,
                "Training profit %": 3.26, "Test profit %": -1.04,
                "Training Sharpe": 0.44, "Test Sharpe": 0.05,
            }]
        )

        self.assertEqual(rows[0]["n"], "5 - 0")
        self.assertEqual(rows[0]["Win rate %"], "60.0 - N/A")
        self.assertEqual(rows[0]["Profit %"], "3.3 - -1.0")
        self.assertEqual(rows[0]["Sharpe"], "0.4 - 0.1")

    def test_view_ticker_parser_uses_exact_comma_or_space_membership(self):
        filter_rows = getattr(backtest_lab, "_filter_view_signal_rows", None)

        self.assertTrue(callable(filter_rows))
        self.assertEqual(
            backtest_lab._parse_view_signal_tickers(" vcb, FPT  vcb "),
            ("VCB", "FPT"),
        )
        rows = [
            {"Ticker": "VCB", "Horizon": "Swing"},
            {"Ticker": "VC", "Horizon": "Swing"},
            {"Ticker": "FPT", "Horizon": "Mid-term"},
        ]
        self.assertEqual(
            filter_rows(
                rows,
                "vcb fpt",
                "Both",
            ),
            [rows[0], rows[2]],
        )
        self.assertEqual(
            filter_rows(
                [{"Ticker": "VCB", "Horizon": "Swing"}],
                "",
                "Both",
            ),
            [{"Ticker": "VCB", "Horizon": "Swing"}],
        )

    def test_view_signal_table_rows_use_visible_ordinals_and_default_hidden_columns(self):
        rows = backtest_lab._view_signal_rows([
            {
                "Ticker": "VCB", "Horizon": "Swing", "Rulebook": "swing_rulebook_v5__adx",
                "Preferred treatment": "no-background-theme",
                "Training n": 5, "Test n": 1,
                "Training win rate %": 60.0, "Test win rate %": 50.0,
                "Training profit %": 3.0, "Test profit %": 1.0,
                "Training Sharpe": 0.4, "Test Sharpe": None,
            },
            {
                "Ticker": "FPT", "Horizon": "Mid-term", "Rulebook": "midterm_rulebook_v5__adx",
                "Preferred treatment": "no-background-theme",
                "Training n": 5, "Test n": 1,
                "Training win rate %": 61.0, "Test win rate %": 51.0,
                "Training profit %": 3.1, "Test profit %": 1.1,
                "Training Sharpe": 0.5, "Test Sharpe": None,
            },
        ])

        table_rows = backtest_lab._view_signal_table_rows(rows)

        self.assertEqual([(row["No"], row["Select"]) for row in table_rows], [(1, False), (2, False)])
        self.assertEqual(backtest_lab._VIEW_SIGNAL_FIXED_COLUMNS, ("No", "Select", "Ticker"))
        self.assertNotIn("Evidence", backtest_lab._VIEW_SIGNAL_DEFAULT_COLUMNS)
        self.assertNotIn("Theme", backtest_lab._VIEW_SIGNAL_DEFAULT_COLUMNS)

    def test_view_signal_pagination_clamps_requested_page_and_keeps_page_rows(self):
        rows = [{"Ticker": f"T{index:02d}"} for index in range(1, 56)]

        page_rows, page, page_count = backtest_lab._paginate_view_signal_rows(
            rows, page_size=50, requested_page=99,
        )
        self.assertEqual((page, page_count), (2, 2))
        self.assertEqual([row["Ticker"] for row in page_rows], ["T51", "T52", "T53", "T54", "T55"])

    def test_view_signal_rows_keep_flexible_full_id_backstage(self):
        rulebook_id = "frb2_" + "a" * 64
        rows = backtest_lab._view_signal_rows([{
            "Ticker": "VCB", "Horizon": "Swing", "Rulebook": "Flexible · FR-AAAAAAAA",
            "_rulebook_id": rulebook_id, "Preferred treatment": "flexible",
            "Training n": 5, "Test n": 2,
            "Training win rate %": 60.0, "Test win rate %": 50.0,
            "Training profit %": 3.0, "Test profit %": 1.0,
            "Training Sharpe": 0.4, "Test Sharpe": 0.2,
        }])
        self.assertEqual(rulebook_id, rows[0]["_rulebook_id"])

    def test_view_signal_pagination_rejects_invalid_page_size(self):
        with self.assertRaisesRegex(ValueError, "page size"):
            backtest_lab._paginate_view_signal_rows([], page_size=75, requested_page=1)

    def test_view_signals_defaults_to_fifty_rows_per_page(self):
        rows = [
            {
                "Ticker": f"T{index:02d}", "Horizon": "Swing", "Rulebook": f"swing_rulebook_v5__{index}",
                "Preferred treatment": "no-background-theme",
                "Training n": 5, "Test n": 2,
                "Training win rate %": 60.0, "Test win rate %": 50.0,
                "Training profit %": 3.2, "Test profit %": 1.0,
                "Training Sharpe": 0.4, "Test Sharpe": 0.2,
            }
            for index in range(1, 56)
        ]
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            f"rows = {rows!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': rows, 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "lab._render_view('unused-signals', 'unused-positions', remove_fn=lambda *_a, **_k: None)\n"
        ).run()

    @staticmethod
    def _validate_filter_selectboxes(app):
        keys = (
            backtest_lab._VALIDATE_WIN_RATE_SORT_KEY,
            "backtest_validate_position_action_v4",
            "backtest_validate_horizon_v5",
            backtest_lab._VALIDATE_TRAIN_PROFIT_FILTER_KEY,
            backtest_lab._VALIDATE_TEST_PROFIT_FILTER_KEY,
            backtest_lab._VALIDATE_RESULT_TICKER_FILTER_KEY,
        )
        return [next(item for item in app.selectbox if item.key == key) for key in keys]

        page_size = next(item for item in app.selectbox if item.label == "Rows per page")
        self.assertEqual(page_size.value, 50)
        self.assertEqual(page_size.options, ["50", "100", "150"])

        next(
            item for item in app.button if item.help == "Next View Signals page"
        ).click().run()

        self.assertEqual(app.session_state[backtest_lab._VIEW_SIGNAL_PAGE_KEY], 2)
        self.assertTrue(any(item.value == "Page 2 of 2 — 55 signals" for item in app.caption))

    def test_view_signal_page_navigation_clears_previous_page_selection(self):
        rows = [
            {
                "Ticker": f"T{index:02d}", "Horizon": "Swing", "Rulebook": f"swing_rulebook_v5__{index}",
                "Preferred treatment": "no-background-theme",
                "Training n": 5, "Test n": 2,
                "Training win rate %": 60.0, "Test win rate %": 50.0,
                "Training profit %": 3.2, "Test profit %": 1.0,
                "Training Sharpe": 0.4, "Test Sharpe": 0.2,
            }
            for index in range(1, 56)
        ]
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            f"rows = {rows!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': rows, 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "lab._render_view('unused-signals', 'unused-positions', remove_fn=lambda *_a, **_k: None)\n"
        ).run()

        next(item for item in app.checkbox if item.label == "Select all visible").set_value(True).run()
        next(item for item in app.button if item.help == "Next View Signals page").click().run()

        self.assertEqual(app.session_state[backtest_lab._VIEW_SIGNAL_PAGE_KEY], 2)
        self.assertEqual(app.session_state[backtest_lab._VIEW_SIGNAL_SELECTED_KEYS_KEY], set())
        self.assertTrue(
            next(item for item in app.button if item.help == "Remove selected signals (0)").disabled
        )

    def test_view_signal_table_widget_key_is_deterministic_and_context_specific(self):
        first = backtest_lab._view_signal_table_widget_key(
            (("VCB", "swing", "swing_rulebook_v5__adx"),),
            (("VCB", "swing", "swing_rulebook_v5__adx"),),
            ("No", "Select", "Ticker"),
        )
        second = backtest_lab._view_signal_table_widget_key(
            (("VCB", "swing", "swing_rulebook_v5__adx"),),
            (),
            ("No", "Select", "Ticker"),
        )

        self.assertEqual(
            first,
            backtest_lab._view_signal_table_widget_key(
                (("VCB", "swing", "swing_rulebook_v5__adx"),),
                (("VCB", "swing", "swing_rulebook_v5__adx"),),
                ("No", "Select", "Ticker"),
            ),
        )
        self.assertNotEqual(first, second)

    def test_view_signals_renders_ticker_and_both_default_horizon_filters(self):
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': [], 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "lab._render_view('unused-signals')\n"
        ).run()

        self.assertEqual([item.label for item in app.text_input], ["Ticker"])
        self.assertEqual([item.label for item in app.selectbox], ["Horizon", "Rows per page"])
        self.assertEqual(app.selectbox[0].value, "Both")
        self.assertEqual(
            app.selectbox[0].options,
            ["Both", "Swing", "Mid-term"],
        )

    def test_view_signals_uses_native_columns_selection_and_disabled_empty_removal(self):
        row = {
            "Ticker": "VCB", "Horizon": "Swing", "Rulebook": "swing_rulebook_v5__adx",
            "Preferred treatment": "no-background-theme",
            "Training n": 5, "Test n": 2,
            "Training win rate %": 60.0, "Test win rate %": 50.0,
            "Training profit %": 3.2, "Test profit %": 1.0,
            "Training Sharpe": 0.4, "Test Sharpe": 0.2,
        }
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            f"row = {row!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': [row], 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "lab._render_view('unused-signals', 'unused-positions', remove_fn=lambda *_a, **_k: None)\n"
        ).run()

        self.assertEqual([item.label for item in app.pills], ["Table"])
        self.assertEqual(
            app.pills[0].value,
            ["Horizon", "Train-test", "n", "Win rate %", "Profit %", "Sharpe"],
        )
        self.assertEqual([item.label for item in app.checkbox], ["Select all visible"])
        source = inspect.getsource(backtest_lab._render_view)
        self.assertIn("st.data_editor(", source)
        self.assertIn("_VIEW_SIGNAL_FIXED_COLUMNS", source)
        self.assertIn("_VIEW_SIGNAL_DEFAULT_COLUMNS", source)
        self.assertIn("toolbar = st.empty()", source)
        self.assertIn("with toolbar.container():", source)
        self.assertIn('help="Choose visible View Signals columns"', source)
        self.assertIn('key="backtest_view_signal_columns_v5"', source)
        self.assertIn('st.caption("Table")', source)
        self.assertLess(source.index('st.caption("Table")'), source.index("st.popover"))
        self.assertIn('width="stretch"', source)
        remove = [item for item in app.button if item.label == ":material/delete:"][-1]
        self.assertTrue(remove.disabled)
        self.assertEqual(remove.help, "Remove selected signals (0)")

    def test_view_signals_select_all_applies_only_to_current_filtered_rows(self):
        rows = [
            {
                "Ticker": ticker, "Horizon": "Swing", "Rulebook": f"swing_rulebook_v5__{ticker.lower()}",
                "Preferred treatment": "no-background-theme",
                "Training n": 5, "Test n": 2,
                "Training win rate %": 60.0, "Test win rate %": 50.0,
                "Training profit %": 3.2, "Test profit %": 1.0,
                "Training Sharpe": 0.4, "Test Sharpe": 0.2,
            }
            for ticker in ("VCB", "FPT")
        ]
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            f"rows = {rows!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': rows, 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "lab._render_view('unused-signals', 'unused-positions', remove_fn=lambda *_a, **_k: None)\n"
        ).run()

        next(item for item in app.checkbox if item.label == "Select all visible").set_value(True).run()
        self.assertFalse([item for item in app.button if item.label == ":material/delete:"][-1].disabled)

        next(item for item in app.text_input if item.label == "Ticker").set_value("FPT").run()
        self.assertFalse([item for item in app.button if item.label == ":material/delete:"][-1].disabled)

    def test_view_signals_removal_action_requires_confirmation_before_delegating_identity(self):
        row = {
            "Ticker": "VCB", "Horizon": "Swing", "Rulebook": "swing_rulebook_v5__adx",
            "Preferred treatment": "no-background-theme",
            "Training n": 5, "Test n": 2,
            "Training win rate %": 60.0, "Test win rate %": 50.0,
            "Training profit %": 3.2, "Test profit %": 1.0,
            "Training Sharpe": 0.4, "Test Sharpe": 0.2,
        }
        app = AppTest.from_string(
            "from types import SimpleNamespace\n"
            "import pages.backtest_lab as lab\n"
            f"row = {row!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': [row], 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "def remove(keys, **kwargs):\n"
            "    assert [(item.ticker, item.horizon, item.rulebook_id) for item in keys] == [(\n"
            "        'VCB', 'swing', 'swing_rulebook_v5__adx')]\n"
            "    assert kwargs == {'signal_dir': 'unused-signals', 'positions_dir': 'unused-positions'}\n"
            "    return SimpleNamespace(removed=keys)\n"
            "lab._render_view('unused-signals', 'unused-positions', remove_fn=remove)\n"
        ).run()

        next(item for item in app.checkbox if item.label == "Select all visible").set_value(True).run()
        [item for item in app.button if item.label == ":material/delete:"][-1].click().run()

        self.assertFalse(any(item.value == "Removed 1 saved signal(s)." for item in app.success))
        self.assertIn(backtest_lab._VIEW_SIGNAL_PENDING_REMOVAL_KEY, app.session_state)
        next(item for item in app.button if item.label == "Remove selected signals").click().run()
        self.assertTrue(any(
            item.value == (
                "Removed 1 selected signal(s). View refreshed; Top 3 may now show "
                "other stored candidates."
            )
            for item in app.success
        ))
        self.assertTrue([item for item in app.button if item.label == ":material/delete:"][-1].disabled)
        self.assertEqual(app.exception, [])

    def test_view_signals_cancelled_removal_keeps_candidate_and_clears_pending_state(self):
        row = {
            "Ticker": "VCB", "Horizon": "Swing", "Rulebook": "swing_rulebook_v5__adx",
            "Preferred treatment": "no-background-theme",
            "Training n": 5, "Test n": 2,
            "Training win rate %": 60.0, "Test win rate %": 50.0,
            "Training profit %": 3.2, "Test profit %": 1.0,
            "Training Sharpe": 0.4, "Test Sharpe": 0.2,
        }
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            f"row = {row!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': [row], 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "def remove(*_args, **_kwargs):\n"
            "    raise AssertionError('removal must not occur when cancelled')\n"
            "lab._render_view('unused-signals', 'unused-positions', remove_fn=remove, rerun_fn=lambda: None)\n"
        ).run()

        next(item for item in app.checkbox if item.label == "Select all visible").set_value(True).run()
        next(item for item in app.button if item.label == ":material/delete:").click().run()
        next(item for item in app.button if item.label == "Cancel").click().run()

        self.assertNotIn(backtest_lab._VIEW_SIGNAL_PENDING_REMOVAL_KEY, app.session_state)
        self.assertEqual(app.exception, [])

    def test_view_signals_protected_removal_clears_selection_and_reports_identity(self):
        row = {
            "Ticker": "VCB", "Horizon": "Swing", "Rulebook": "swing_rulebook_v5__adx",
            "Preferred treatment": "no-background-theme",
            "Training n": 5, "Test n": 2,
            "Training win rate %": 60.0, "Test win rate %": 50.0,
            "Training profit %": 3.2, "Test profit %": 1.0,
            "Training Sharpe": 0.4, "Test Sharpe": 0.2,
        }
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            "from backtest_engine.signal_removal import SignalCandidateKey, SignalRemovalBlockedError\n"
            f"row = {row!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': [row], 'terminal': [], 'invalid': [], 'warnings': [],\n"
            "}\n"
            "def remove(_keys, **_kwargs):\n"
            "    raise SignalRemovalBlockedError((SignalCandidateKey(\n"
            "        'VCB', 'swing', 'swing_rulebook_v5__adx'),))\n"
            "lab._render_view('unused-signals', 'unused-positions', remove_fn=remove)\n"
        ).run()

        next(item for item in app.checkbox if item.label == "Select all visible").set_value(True).run()
        [item for item in app.button if item.label == ":material/delete:"][-1].click().run()
        next(item for item in app.button if item.label == "Remove selected signals").click().run()

        self.assertTrue(any("VCB / swing / swing_rulebook_v5__adx" in item.value for item in app.error))
        self.assertFalse([item for item in app.button if item.label == ":material/delete:"][-1].disabled)
        self.assertEqual(app.exception, [])

    def test_view_signals_render_omits_terminal_rows(self):
        row = {
            "Ticker": "VCB",
            "Horizon": "Swing",
            "Rulebook": "swing_rulebook_v5__adx",
            "Preferred treatment": "no-background-theme",
            "Training n": 5,
            "Test n": 2,
            "Training win rate %": 60.0,
            "Test win rate %": 50.0,
            "Training profit %": 3.2,
            "Test profit %": 1.0,
            "Training Sharpe": 0.4,
            "Test Sharpe": 0.2,
        }
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            f"row = {row!r}\n"
            "lab.list_current_signal_set_rows = lambda _dir: {\n"
            "    'valid': [row], 'terminal': [{'terminal_state': 'empty'}],\n"
            "    'invalid': [], 'warnings': ['catalog warning'],\n"
            "}\n"
            "lab._render_view('unused-signals')\n"
        ).run()

        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(
            list(app.dataframe[0].value.columns),
            ["No", "Select", "Ticker", "Horizon", "Train-test", "n", "Win rate %", "Profit %", "Sharpe"],
        )
        self.assertFalse(any(item.value == "Terminal results" for item in app.caption))
        self.assertTrue(any(item.value == "catalog warning" for item in app.warning))
        self.assertIn("height=720", inspect.getsource(backtest_lab._render_view))

    def test_validation_tickers_uses_manual_limit_or_every_resolved_group_member(self):
        self.assertEqual(
            backtest_lab._validation_tickers(
                "fpt, vcb", "-", "signals", lambda *_: ()
            ),
            ("FPT", "VCB"),
        )
        self.assertEqual(
            backtest_lab._validation_tickers(
                "ignored", "BANK", "signals", lambda *_: ("VCB", "TCB")
            ),
            ("VCB", "TCB"),
        )
        with self.assertRaisesRegex(ValueError, "between 1 and 15"):
            backtest_lab._validation_tickers(
                " ".join(f"T{i}" for i in range(16)),
                "-",
                "signals",
                lambda *_: (),
            )
        with self.assertRaisesRegex(ValueError, "no tickers"):
            backtest_lab._validation_tickers(
                "ignored", "N/A", "signals", lambda *_: ()
            )

    def test_validation_batches_chunk_group_members_continue_after_failure_and_preserve_order(self):
        calls = []

        def validate(ticker, *_args):
            calls.append(ticker)
            if ticker == "T16":
                raise ValueError("broken artifact")
            return {"ticker": ticker, "results": [], "historical_positions": []}

        tickers = tuple(f"T{i}" for i in range(1, 18))
        batch = backtest_lab._run_validation_batches(
            tickers, object(), "signals", "positions", validate
        )

        self.assertEqual(calls, list(tickers))
        self.assertEqual(
            batch["chunks"],
            (tuple(f"T{i}" for i in range(1, 16)), ("T16", "T17")),
        )
        self.assertEqual(
            list(batch["by_ticker"]),
            [ticker for ticker in tickers if ticker != "T16"],
        )
        self.assertEqual(batch["errors"], {"T16": "broken artifact"})

    def test_validation_batches_report_progress_after_success_and_failure(self):
        signature = inspect.signature(backtest_lab._run_validation_batches)
        self.assertIn("progress_fn", signature.parameters)
        progress = []

        def validate(ticker, *_args):
            if ticker == "BAD":
                raise ValueError("broken artifact")
            return {"ticker": ticker, "results": [], "historical_positions": []}

        batch = backtest_lab._run_validation_batches(
            ("VCB", "BAD"),
            object(),
            "signals",
            "positions",
            validate,
            progress_fn=lambda completed, total, ticker: progress.append(
                (completed, total, ticker)
            ),
        )

        self.assertEqual(progress, [(1, 2, "VCB"), (2, 2, "BAD")])
        self.assertEqual(batch["errors"], {"BAD": "broken artifact"})

    def test_validate_filters_delisted_tickers_before_replay_and_progress(self):
        from backtest_engine.listing_status import ListingStatus

        listed = ListingStatus("VCB", "listed", date(2026, 9, 9), date(2026, 9, 9))
        delisted = ListingStatus("LTG", "delisted", date(2026, 6, 19), date(2026, 9, 9))

        eligible = backtest_lab._listed_validation_tickers(
            ("LTG", "VCB"),
            object(),
            lambda _tickers, _engine: {"LTG": delisted, "VCB": listed},
        )

        self.assertEqual(eligible, ("VCB",))

    def test_collect_all_chunks_into_sequential_batches_without_persisting_all(self):
        tickers = tuple(f"T{index:02d}" for index in range(1, 17))

        configs = backtest_lab._collect_batch_configs(
            tickers, "swing", "15y", "ALL"
        )

        self.assertEqual([config.tickers for config in configs], [tickers[:15], tickers[15:]])
        self.assertEqual([config.group_name for config in configs], ["N/A", "N/A"])

    def test_collect_queue_runs_next_chunk_after_failed_chunk(self):
        configs = backtest_lab._collect_batch_configs(
            tuple(f"T{index:02d}" for index in range(1, 17)),
            "swing",
            "15y",
            "ALL",
        )
        calls = []

        def submit(config, *_args):
            calls.append(config.tickers)
            return f"job-{len(calls)}"

        queue = backtest_lab._advance_collect_queue(
            backtest_lab._new_collect_queue(configs),
            None,
            submit,
            object(),
            "status",
        )
        self.assertEqual(calls, [configs[0].tickers])
        self.assertEqual(queue["job_id"], "job-1")

        queue = backtest_lab._advance_collect_queue(
            queue,
            SimpleNamespace(
                state="failed", progress=1.0, output_paths=("failed.json",), error_text="broken"
            ),
            submit,
            object(),
            "status",
        )
        self.assertEqual(calls, [configs[0].tickers, configs[1].tickers])
        self.assertEqual(queue["job_id"], "job-2")
        self.assertEqual(queue["completed_batches"], 1)
        self.assertEqual(queue["errors"], ("Batch 1/2 failed: broken",))

        queue = backtest_lab._advance_collect_queue(
            queue,
            SimpleNamespace(
                state="done", progress=1.0, output_paths=("done.json",), error_text=None
            ),
            submit,
            object(),
            "status",
        )
        self.assertTrue(queue["complete"])
        self.assertEqual(queue["output_paths"], ("failed.json", "done.json"))

    def test_collect_blocks_second_run_while_serial_queue_is_active(self):
        app = self._collect_group_app()
        next(
            item for item in app.text_input if item.key == "backtest_collect_tickers_v4"
        ).set_value("FPT").run()
        next(item for item in app.button if item.label == "Run Backtest").click().run()
        app.run()

        self.assertTrue(
            next(item for item in app.button if item.label == "Run Backtest").disabled
        )

    def test_collect_accepts_a_minimal_polled_status_without_ticker_results(self):
        app = self._collect_group_app()

        next(
            item for item in app.text_input if item.key == "backtest_collect_tickers_v4"
        ).set_value("FPT").run()
        next(
            item for item in app.button if item.label == "Run Backtest"
        ).click().run()

        self.assertEqual(app.exception, [])

    def test_validation_result_for_ticker_supports_single_and_batch_state(self):
        fpt = {"ticker": "FPT", "results": []}
        vcb = {"ticker": "VCB", "results": []}
        self.assertIs(backtest_lab._validation_result_for_ticker(fpt, "FPT"), fpt)
        self.assertIs(
            backtest_lab._validation_result_for_ticker(
                {"by_ticker": {"FPT": fpt, "VCB": vcb}, "errors": {}}, "VCB"
            ),
            vcb,
        )

    def test_validated_candidates_uses_matching_ticker_from_batch_state(self):
        item = {
            "buy_eligible": True,
            "horizon": "swing",
            "rulebook_id": "swing_rulebook_v5__rsi",
            "preferred_variant": "no-background-theme",
            "signal_reference": {"schema_version": 5, "horizon": "swing"},
        }
        candidates = backtest_lab._validated_v5_candidates(
            {
                "by_ticker": {
                    "VCB": {
                        "ticker": "VCB",
                        "results": [item],
                        "historical_positions": [],
                    }
                },
                "errors": {},
            },
            "VCB",
        )

        self.assertEqual(
            list(candidates),
            ["Swing — swing_rulebook_v5__rsi — no-background-theme"],
        )

    def test_ui_copy_uses_exploratory_gross_without_certification_or_trade_claims(self):
        source = inspect.getsource(backtest_lab).lower()
        self.assertIn("exploratory — gross", source)
        self.assertNotIn("certification:", source)
        self.assertNotIn("profitable signal", source)
        self.assertNotIn("tradable", source)

    def test_position_table_labels_v5_rulebook_and_scales_raw_prices(self):
        rows = backtest_lab._display_position_rows(
            [
                {
                    "ticker": "FPT",
                    "status": "open",
                    "actual_buy_price": 50300,
                    "actual_sell_price": None,
                    "profit_pct": None,
                    "holding_sessions": 2,
                    "position": {
                        "signal_reference": {
                            "schema_version": 5,
                            "horizon": "swing",
                            "rulebook_id": "swing_rulebook_v5__adx",
                            "preferred_variant": "no-background-theme",
                        }
                    },
                }
            ]
        )
        self.assertEqual(
            rows[0]["Saved signal set"],
            "Swing — swing_rulebook_v5__adx — no-background-theme",
        )
        self.assertEqual(rows[0]["BUY (k VND)"], 50.3)
        self.assertIsNone(rows[0]["SELL (k VND)"])

    def test_backtest_page_has_shared_view_signals_tab_and_no_duplicate_tab_headers(self):
        app = self._grouped_positions_app([])

        self.assertEqual(
            [tab.label for tab in app.tabs],
            [
                "Collect Signals",
                "View Signals",
                "Validate Signals",
                "Current Positions",
                "Validate Positions",
                "Group Manager",
            ],
        )
        self.assertGreaterEqual(len(app.get("popover")), 1)
        self.assertEqual(
            inspect.getsource(backtest_lab._render_collect).count(
                'st.popover("View Signals")'
            ),
            0,
        )
        self.assertEqual(
            inspect.getsource(backtest_lab._render_validate).count(
                'st.popover("View Signals")'
            ),
            0,
        )
        validate_positions = app.tabs[4]
        self.assertFalse(any(item.value == "Validate Positions" for item in validate_positions.title))
        duplicate_headings = {
            backtest_lab._render_collect: 'st.subheader("Collect Signals")',
            backtest_lab._render_view: 'st.subheader("View Signals")',
            backtest_lab._render_validate: 'st.subheader("Validate Signals")',
            backtest_lab._render_positions: 'st.subheader("Current Positions")',
            backtest_lab._render_validate_positions: 'st.title("Validate Positions")',
            backtest_lab._render_group_manager: 'st.subheader("Group Manager")',
        }
        for renderer, heading in duplicate_headings.items():
            self.assertNotIn(heading, inspect.getsource(renderer))
        source = inspect.getsource(backtest_lab._render_validate_positions)
        self.assertIn('st.data_editor(', source)
        self.assertIn('"BUY price (k VND)"', source)
        self.assertIn('"Current price (k VND)"', source)
        self.assertIn('"Hold time"', source)
        self.assertIn("_validate_position_result_rows", source)
        self.assertIn(
            '"Risk"', inspect.getsource(backtest_lab._validate_position_result_rows)
        )
        self.assertIn('st.subheader(f"As of:', source)
        self.assertIn('st.button("Run validation"', source)
        self.assertTrue(any("No eligible OPEN positions." == item.value for item in app.info))
        self.assertEqual(app.exception, [])

    def test_current_positions_accepts_the_page_listing_status_provider(self):
        self.assertIn(
            "listing_statuses_fn",
            inspect.signature(backtest_lab._render_positions).parameters,
        )

    def test_group_manager_status_filter_uses_compact_pills(self):
        source = inspect.getsource(backtest_lab._render_group_manager)

        self.assertIn('st.caption("Status")', source)
        self.assertIn("st.popover(", source)
        self.assertIn("st.pills(", source)
        self.assertNotIn("st.multiselect(", source)

    def test_collect_places_tickers_above_horizon_range_group_and_action_row(self):
        source = inspect.getsource(backtest_lab._render_collect)

        self.assertIn(
            "collect_row = st.columns((3, 1, 1))",
            source,
        )
        self.assertIn("source_column, horizon_column, range_column, action_column = st.columns(4)", source)
        self.assertIn('source_column.selectbox(', source)
        self.assertIn("horizon_column.selectbox(", source)
        self.assertIn("range_column.selectbox(", source)
        self.assertIn("collect_row[1].selectbox(", source)
        self.assertIn("action_column.button(", source)

    def test_collect_edit_group_uses_two_members_per_row_and_destructive_x(self):
        source = inspect.getsource(backtest_lab._render_collect)

        self.assertIn("member_columns = st.columns(4)", source)
        self.assertIn('"X", key=', source)
        self.assertIn('type="primary"', source)

    def test_collect_renders_output_paths_in_four_columns(self):
        source = inspect.getsource(backtest_lab._render_collect)

        self.assertIn("result_columns = st.columns(4)", source)
        self.assertIn("with result_columns[index % 4]:", source)

    def test_collect_existing_group_locks_tickers_to_all_members(self):
        app = self._collect_group_app()
        group_choices = [item for item in app.selectbox if item.label == "Group"]

        self.assertEqual(len(group_choices), 1)
        group_choices[0].set_value("BANK").run()

        ticker_box = next(
            item for item in app.text_input if item.key == "backtest_collect_group_tickers_v4_BANK"
        )
        self.assertEqual(ticker_box.value, "VCB TCB")
        self.assertTrue(ticker_box.disabled)

    def test_collect_all_is_locked_virtual_group_after_new_group_option(self):
        app = self._collect_group_app()
        group = next(item for item in app.selectbox if item.label == "Group")

        self.assertEqual(group.options[:3], ["N/A", "New group…", "ALL"])
        group.set_value("ALL").run()

        ticker_box = next(
            item for item in app.text_input if item.key == "backtest_collect_group_tickers_v4_ALL"
        )
        self.assertEqual(ticker_box.value, "VCB TCB")
        self.assertTrue(ticker_box.disabled)
        self.assertIn("if group_selection in named_groups:", inspect.getsource(backtest_lab._render_collect))

    def test_collect_group_change_refreshes_disabled_tickers(self):
        app = self._collect_group_app()
        next(item for item in app.selectbox if item.label == "Group").set_value("BANK").run()
        next(item for item in app.selectbox if item.label == "Group").set_value("TECH").run()

        ticker_box = next(
            item for item in app.text_input if item.key == "backtest_collect_group_tickers_v4_TECH"
        )
        self.assertEqual(ticker_box.value, "FPT HPG")
        self.assertTrue(ticker_box.disabled)

    def test_collect_group_save_refreshes_disabled_tickers_with_new_member(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "import pages.backtest_lab as lab\n"
            "st.session_state.setdefault('members', ('VCB', 'TCB'))\n"
            "lab.replace_group_tickers = lambda _group, tickers, _dir: st.session_state.__setitem__('members', tuple(tickers))\n"
            "def groups(_dir): return ('-', 'N/A', 'ALL', 'BANK')\n"
            "def resolve(group, _dir): return st.session_state['members'] if group == 'BANK' else ()\n"
            "lab._render_collect(None, 'unused-status', 'unused-signals', lambda *_a: 'job', lambda *_a: None, lambda *_a: None, groups, resolve)\n"
        ).run()

        next(item for item in app.selectbox if item.label == "Group").set_value("BANK").run()
        next(item for item in app.text_input if item.label == "Add ticker").set_value("FPT").run()
        next(item for item in app.button if item.label == "Add").click().run()
        next(item for item in app.button if item.label == "Save Group").click().run()

        ticker_box = next(item for item in app.text_input if item.label == "Tickers")
        self.assertEqual(ticker_box.value, "FPT TCB VCB")
        self.assertTrue(ticker_box.disabled)

    def test_collect_group_add_clears_ticker_input_after_success(self):
        app = self._collect_group_app()
        next(item for item in app.selectbox if item.label == "Group").set_value("BANK").run()
        add_ticker = next(item for item in app.text_input if item.label == "Add ticker")

        add_ticker.set_value("FPT").run()
        next(item for item in app.button if item.label == "Add").click().run()

        self.assertEqual(
            next(item for item in app.text_input if item.label == "Add ticker").value,
            "",
        )

    def test_collect_new_group_submits_requested_name_and_manual_tickers(self):
        app = self._collect_group_app()
        group_choices = [item for item in app.selectbox if item.label == "Group"]

        self.assertEqual(len(group_choices), 1)
        group = group_choices[0]
        group.set_value("New group…").run()

        next(item for item in app.text_input if item.label == "New group name").set_value("health").run()
        next(
            item for item in app.text_input if item.key == "backtest_collect_tickers_v4"
        ).set_value("fpt vcb").run()
        next(item for item in app.button if item.label == "Run Backtest").click().run()

        self.assertEqual(app.session_state["collect_group_config"]["group_name"], "HEALTH")
        self.assertEqual(app.session_state["collect_group_config"]["tickers"], ("FPT", "VCB"))

    def test_validate_group_locks_resolved_tickers_and_runs_every_member(self):
        app = self._validation_group_app()
        self.assertTrue(
            any(item.label == "Ticker group" and item.value == "-" for item in app.selectbox)
        )
        self.assertTrue(any(item.label == "Class" for item in app.pills))

        group = next(item for item in app.selectbox if item.label == "Ticker group")
        group.set_value("BANK").run()
        ticker_box = next(
            item for item in app.text_input if item.key == "backtest_validate_group_tickers_v4_BANK"
        )
        self.assertEqual(ticker_box.value, "VCB TCB")
        self.assertTrue(ticker_box.disabled)

        next(item for item in app.button if item.label == "Validate").click().run()
        self.assertEqual(app.session_state["validation_calls"], ["VCB", "TCB"])

    def test_validate_silently_skips_delisted_group_members(self):
        app = self._validation_group_app(
            group_tickers=("VCB", "LTG"), delisted_tickers=("LTG",)
        )
        next(item for item in app.selectbox if item.label == "Ticker group").set_value("BANK").run()
        next(item for item in app.button if item.label == "Validate").click().run()

        self.assertEqual(app.session_state["validation_calls"], ["VCB"])
        self.assertFalse(any("Delisted:" in item.value for item in app.warning))

    def test_validate_group_change_refreshes_disabled_tickers(self):
        app = self._validation_group_app()
        next(item for item in app.selectbox if item.label == "Ticker group").set_value("BANK").run()
        next(item for item in app.selectbox if item.label == "Ticker group").set_value("TECH").run()

        ticker_box = next(
            item for item in app.text_input if item.key == "backtest_validate_group_tickers_v4_TECH"
        )
        self.assertEqual(ticker_box.value, "FPT HPG")
        self.assertTrue(ticker_box.disabled)

    def test_validate_disables_result_filters_until_cached_results_exist(self):
        app = self._validation_group_app()

        self.assertTrue(
            all(item.disabled for item in self._validate_filter_selectboxes(app))
        )

    def test_validate_enables_result_filters_when_cached_results_exist(self):
        item = {
            "availability": "available",
            "horizon": "swing",
            "rulebook_id": "rule",
            "preferred_variant": "no-background-theme",
            "monitoring": {"match_level": 100.0, "match_classification": "closely_match"},
            "position_action": "can BUY",
            "signal_date": "2026-09-04",
            "win_rate": {"training": 60.0, "test": 55.0},
            "audit_eligibility": {},
            "evidence_eligibility": {},
            "current": {},
            "candidate": {"treatments": {}},
            "evaluation_label": "Exploratory — gross",
            "partition_labels": {},
        }
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from datetime import date\n"
            "from backtest_engine.listing_status import ListingStatus\n"
            "from pages.backtest_lab import render_backtest_page\n"
            f"item = {item!r}\n"
            "st.session_state['backtest_v4_validation_result'] = "
            "{'by_ticker': {'FPT': {'results': [item], 'historical_positions': []}}}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', "
            "signal_dir='unused-signals', positions_dir='unused-positions', "
            "rerun_fn=lambda: None)\n"
        ).run()

        self.assertTrue(
            all(not item.disabled for item in self._validate_filter_selectboxes(app))
        )

    def test_validate_keeps_result_filters_disabled_for_unavailable_cache(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page\n"
            "st.session_state['backtest_v4_validation_result'] = "
            "{'by_ticker': {'FPT': {'results': [{'availability': 'unavailable', "
            "'horizon': 'swing', 'reason': 'missing source data'}], "
            "'historical_positions': []}}}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', "
            "signal_dir='unused-signals', positions_dir='unused-positions', "
            "rerun_fn=lambda: None)\n"
        ).run()

        self.assertTrue(
            all(item.disabled for item in self._validate_filter_selectboxes(app))
        )

    def test_validate_result_ticker_filter_lists_available_tickers_and_filters_cache(self):
        options_fn = getattr(backtest_lab, "_available_validation_ticker_options", None)
        self.assertTrue(callable(options_fn))
        self.assertEqual(
            options_fn({
                "FPT": {"results": [{"availability": "available"}]},
                "VCB": {"results": [{"availability": "available"}]},
                "DPM": {"results": [{"availability": "unavailable"}]},
            }),
            ("ALL", "FPT", "VCB"),
        )

        def item(rulebook_id):
            return {
                "availability": "available",
                "horizon": "swing",
                "rulebook_id": rulebook_id,
                "preferred_variant": "no-background-theme",
                "evaluation_label": "Exploratory — gross",
                "monitoring": {
                    "match_level": 100.0,
                    "match_classification": "closely_match",
                },
                "position_action": "can BUY",
                "audit_eligibility": {},
                "evidence_eligibility": {},
                "current": {},
                "candidate": {"treatments": {}},
                "partition_labels": {},
            }

        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page\n"
            f"fpt = {item('fpt-rule')!r}\n"
            f"vcb = {item('vcb-rule')!r}\n"
            "st.session_state['backtest_v4_validation_result'] = {'by_ticker': {'FPT': {'results': [fpt], 'historical_positions': []}, 'VCB': {'results': [vcb], 'historical_positions': []}}}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', signal_dir='unused-signals', positions_dir='unused-positions', rerun_fn=lambda: None)\n"
        ).run()

        ticker_filter = next(
            control for control in app.selectbox if control.label == "Ticker"
        )
        self.assertEqual(ticker_filter.options, ["ALL", "FPT", "VCB"])
        ticker_filter.set_value("FPT").run()
        self.assertEqual(
            [
                control.label for control in app.expander
                if control.label.endswith("— no-background-theme")
            ],
            ["FPT — fpt-rule — no-background-theme"],
        )

    def test_validation_horizon_filter_hides_other_horizon_results(self):
        item = {
            "availability": "available",
            "rulebook_id": "rule",
            "preferred_variant": "no-background-theme",
            "monitoring": {"match_level": 100.0, "match_classification": "closely_match"},
            "position_action": "can BUY",
            "signal_date": "2026-08-14",
            "win_rate": {"training": 62.5, "test": 55.0},
            "audit_eligibility": {},
            "evidence_eligibility": {},
            "current": {},
            "candidate": {"treatments": {}},
            "evaluation_label": "Exploratory — gross",
            "partition_labels": {},
        }
        app = AppTest.from_string(
            "from pages.backtest_lab import _render_validation_result\n"
            f"swing = {dict(item, horizon='swing')!r}\n"
            f"midterm = {dict(item, horizon='midterm')!r}\n"
            "_render_validation_result('VCB', {'results': [swing, midterm], 'historical_positions': []}, {'closely_match'}, 'ALL', 'Swing')\n"
        ).run()

        labels = [item.label for item in app.expander]
        self.assertTrue(any(label.startswith("VCB —") for label in labels))
        self.assertFalse(any("Mid-term" in label for label in labels))

    def test_validate_filters_keep_requested_order(self):
        source = inspect.getsource(backtest_lab._render_validate)

        self.assertEqual(
            backtest_lab._VALIDATE_WIN_RATE_SORT_OPTIONS,
            ("None", "Training DESC", "Test DESC"),
        )
        self.assertIn('"Win rate"', source)
        self.assertIn('"Train Profit %"', source)
        self.assertIn('"Test Profit %"', source)
        self.assertLess(source.index('st.caption("Class")'), source.index('"Win rate"'))
        self.assertLess(source.index('"Win rate"'), source.index('"Position actions"'))
        self.assertLess(source.index('"Horizon"'), source.index('"Train Profit %"'))
        self.assertLess(source.index('"Train Profit %"'), source.index('"Test Profit %"'))

    def test_validate_places_submit_in_first_control_row(self):
        source = inspect.getsource(backtest_lab._render_validate)

        self.assertIn("validate_row = st.columns((3, 2, 0.6))", source)
        self.assertIn("group_name = validate_row[1].selectbox(", source)
        self.assertIn(
            '"Ticker group", group_choices, key=group_key, width="stretch"',
            source,
        )
        self.assertIn("validate_clicked = validate_row[2].button(", source)
        self.assertLess(
            source.index("validate_clicked = validate_row[2].button("),
            source.index("filters = st.columns"),
        )
        self.assertNotIn("validate_clicked = filters[6].button(", source)

    def test_validate_profit_band_uses_preferred_treatment_exact_edges(self):
        def item(train_profit, test_profit, *, preferred="no-background-theme"):
            return {
                "preferred_variant": preferred,
                "candidate": {
                    "treatments": {
                        "no-background-theme": {
                            "training": {"profit_pct": train_profit},
                            "test": {"profit_pct": test_profit},
                        },
                        "background-theme": {
                            "training": {"profit_pct": 99.0},
                            "test": {"profit_pct": 99.0},
                        },
                    }
                },
            }

        self.assertEqual(
            backtest_lab._preferred_profit_band(item(5.0, 5.0), "training"),
            "potential",
        )
        self.assertEqual(
            backtest_lab._preferred_profit_band(item(15.0, 15.0), "training"),
            "potential",
        )
        self.assertEqual(
            backtest_lab._preferred_profit_band(item(15.01, 15.01), "training"),
            "profitable",
        )
        self.assertEqual(
            backtest_lab._preferred_profit_band(item(30.0, 30.0), "training"),
            "profitable",
        )
        self.assertEqual(
            backtest_lab._preferred_profit_band(item(30.01, 30.01), "training"),
            "attractive",
        )
        self.assertEqual(
            backtest_lab._preferred_profit_band(item(50.0, 50.0), "training"),
            "attractive",
        )
        self.assertEqual(
            backtest_lab._preferred_profit_band(item(50.01, 50.01), "training"),
            "outstanding",
        )
        self.assertEqual(
            backtest_lab._preferred_profit_band(
                item(1.0, 1.0, preferred="background-theme"), "training"
            ),
            "outstanding",
        )
        self.assertIsNone(backtest_lab._preferred_profit_band(item(4.99, 4.99), "training"))
        self.assertIsNone(backtest_lab._preferred_profit_band(item(None, None), "training"))

    def test_validate_profit_filter_labels_count_preferred_cached_metrics(self):
        def item(train_profit, test_profit):
            return {
                "preferred_variant": "no-background-theme",
                "candidate": {
                    "treatments": {
                        "no-background-theme": {
                            "training": {"profit_pct": train_profit},
                            "test": {"profit_pct": test_profit},
                        },
                        "background-theme": {
                            "training": {"profit_pct": 99.0},
                            "test": {"profit_pct": 99.0},
                        },
                    }
                },
            }

        labels = backtest_lab._profit_filter_labels(
            [
                item(5.0, 6.0),
                item(15.01, 16.0),
                item(30.01, 31.0),
                item(50.01, 51.0),
                item(4.99, 4.99),
            ],
            partition="training",
            other_partition="test",
            other_filter="all",
        )

        self.assertEqual(labels["all"], "All - 5")
        self.assertEqual(labels["potential"], "Potential (5% - 15%) - 1")
        self.assertEqual(labels["profitable"], "Profitable (>15% - 30%) - 1")
        self.assertEqual(labels["attractive"], "Attractive (>30% - 50%) - 1")
        self.assertEqual(labels["outstanding"], "Outstanding (>50%) - 1")

        filtered_labels = backtest_lab._profit_filter_labels(
            [
                item(5.0, 6.0),
                item(15.01, 16.0),
                item(30.01, 31.0),
                item(50.01, 51.0),
                item(4.99, 4.99),
            ],
            partition="training",
            other_partition="test",
            other_filter="outstanding",
        )
        self.assertEqual(filtered_labels["all"], "All - 1")
        self.assertEqual(filtered_labels["potential"], "Potential (5% - 15%) - 0")
        self.assertEqual(filtered_labels["profitable"], "Profitable (>15% - 30%) - 0")
        self.assertEqual(filtered_labels["attractive"], "Attractive (>30% - 50%) - 0")
        self.assertEqual(filtered_labels["outstanding"], "Outstanding (>50%) - 1")

    def test_validate_profit_filters_recover_stale_counted_display_values(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import _render_validate, _VALIDATE_TRAIN_PROFIT_FILTER_KEY, _VALIDATE_TEST_PROFIT_FILTER_KEY\n"
            "st.session_state[_VALIDATE_TRAIN_PROFIT_FILTER_KEY] = 'Potential (5% - 15%) - 2'\n"
            "st.session_state[_VALIDATE_TEST_PROFIT_FILTER_KEY] = 'Outstanding (>50%) - 1'\n"
            "st.session_state['backtest_v4_validation_result'] = {'by_ticker': {}}\n"
            "_render_validate(object(), 'unused-signals', 'unused-positions', lambda *_args: {}, lambda *_args: ('-',), lambda *_args: ())\n"
        ).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(
            next(item for item in app.selectbox if item.label == "Train Profit %").value,
            "potential",
        )
        self.assertEqual(
            next(item for item in app.selectbox if item.label == "Test Profit %").value,
            "outstanding",
        )

    def test_backtest_tabs_track_switches_with_a_reset_callback(self):
        source = inspect.getsource(backtest_lab.render_backtest_page)

        self.assertIn("key=_BACKTEST_TAB_KEY", source)
        self.assertIn("on_change=_reset_backtest_tab_state_on_change", source)

    def test_leaving_collect_resets_inputs_and_terminal_result(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "import pages.backtest_lab as lab\n"
            "st.session_state[lab._BACKTEST_PREVIOUS_TAB_KEY] = lab._BACKTEST_COLLECT_TAB\n"
            "st.session_state[lab._BACKTEST_TAB_KEY] = 'View Signals'\n"
            "st.session_state[lab._COLLECT_GROUP_KEY] = 'BANK'\n"
            "st.session_state['backtest_collect_tickers_v4'] = 'VCB TCB'\n"
            "st.session_state['backtest_collect_group_tickers_v4_BANK'] = 'VCB TCB'\n"
            "st.session_state[lab._COLLECT_QUEUE_KEY] = {'complete': True, 'output_paths': ('result.json',)}\n"
            "lab._reset_backtest_tab_state_on_change()\n"
        ).run()

        self.assertEqual(app.session_state[backtest_lab._COLLECT_GROUP_KEY], "N/A")
        self.assertEqual(app.session_state["backtest_collect_tickers_v4"], "")
        self.assertNotIn("backtest_collect_group_tickers_v4_BANK", app.session_state)
        self.assertNotIn(backtest_lab._COLLECT_QUEUE_KEY, app.session_state)

    def test_leaving_collect_preserves_active_queue(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "import pages.backtest_lab as lab\n"
            "st.session_state[lab._BACKTEST_PREVIOUS_TAB_KEY] = lab._BACKTEST_COLLECT_TAB\n"
            "st.session_state[lab._BACKTEST_TAB_KEY] = 'View Signals'\n"
            "st.session_state[lab._COLLECT_QUEUE_KEY] = {'complete': False, 'job_id': 'job-1'}\n"
            "lab._reset_backtest_tab_state_on_change()\n"
        ).run()

        self.assertEqual(
            app.session_state[backtest_lab._COLLECT_QUEUE_KEY],
            {"complete": False, "job_id": "job-1"},
        )

    def test_leaving_validate_resets_inputs_and_cached_result(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "import pages.backtest_lab as lab\n"
            "st.session_state[lab._BACKTEST_PREVIOUS_TAB_KEY] = lab._BACKTEST_VALIDATE_TAB\n"
            "st.session_state[lab._BACKTEST_TAB_KEY] = 'View Signals'\n"
            "st.session_state['backtest_validate_group_v4'] = 'BANK'\n"
            "st.session_state['backtest_validate_tickers_v4'] = 'VCB TCB'\n"
            "st.session_state['backtest_validate_group_tickers_v4_BANK'] = 'VCB TCB'\n"
            "st.session_state['backtest_v4_validation_result'] = {'by_ticker': {'VCB': {}}}\n"
            "lab._reset_backtest_tab_state_on_change()\n"
        ).run()

        self.assertEqual(app.session_state["backtest_validate_group_v4"], "-")
        self.assertEqual(app.session_state["backtest_validate_tickers_v4"], "")
        self.assertNotIn("backtest_validate_group_tickers_v4_BANK", app.session_state)
        self.assertNotIn("backtest_v4_validation_result", app.session_state)

    def test_validate_result_sorts_visible_candidates_by_selected_win_rate(self):
        def item(rulebook_id, training_win_rate, test_win_rate):
            return {
                "availability": "available",
                "horizon": "swing",
                "rulebook_id": rulebook_id,
                "preferred_variant": "no-background-theme",
                "monitoring": {
                    "match_level": 100.0,
                    "match_classification": "closely_match",
                },
                "position_action": "can BUY",
                "audit_eligibility": {},
                "evidence_eligibility": {},
                "current": {},
                "candidate": {
                    "treatments": {
                        "no-background-theme": {
                            "training": {
                                "win_rate": training_win_rate,
                                "profit_pct": 0.0,
                            },
                            "test": {
                                "win_rate": test_win_rate,
                                "profit_pct": 0.0,
                            },
                        }
                    }
                },
                "evaluation_label": "Exploratory — gross",
                "partition_labels": {},
            }

        low = item("low", 90.0, 10.0)
        high = item("high", 10.0, 90.0)
        app = AppTest.from_string(
            "from pages.backtest_lab import _render_validation_result\n"
            f"result = {{'results': [{low!r}, {high!r}], 'historical_positions': []}}\n"
            "_render_validation_result('FPT', result, {'closely_match'}, win_rate_partition='test')\n"
        ).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(
            [item.label for item in app.expander],
            [
                "FPT — high — no-background-theme",
                "FPT — low — no-background-theme",
            ],
        )

    def test_validate_training_sort_globally_ranks_candidates_across_tickers(self):
        def item(rulebook_id, training_win_rate):
            return {
                "availability": "available",
                "horizon": "swing",
                "rulebook_id": rulebook_id,
                "preferred_variant": "no-background-theme",
                "monitoring": {
                    "match_level": 100.0,
                    "match_classification": "closely_match",
                },
                "position_action": "can BUY",
                "signal_date": "2026-09-04",
                "win_rate": {"training": training_win_rate, "test": 50.0},
                "audit_eligibility": {},
                "evidence_eligibility": {},
                "current": {},
                "candidate": {
                    "treatments": {
                        "no-background-theme": {
                            "training": {"win_rate": training_win_rate, "profit_pct": 0.0},
                            "test": {"win_rate": 50.0, "profit_pct": 0.0},
                        }
                    }
                },
                "evaluation_label": "Exploratory — gross",
                "partition_labels": {},
            }

        shb = item("shb_low", 48.8)
        vib_high = item("vib_high", 57.7)
        vib_mid = item("vib_mid", 55.6)
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page, _VALIDATE_WIN_RATE_SORT_KEY\n"
            f"shb = {shb!r}\n"
            f"vib_high = {vib_high!r}\n"
            f"vib_mid = {vib_mid!r}\n"
            "st.session_state[_VALIDATE_WIN_RATE_SORT_KEY] = 'Training DESC'\n"
            "st.session_state['backtest_v4_validation_result'] = {'by_ticker': {"
            "'SHB': {'results': [shb], 'historical_positions': []}, "
            "'VIB': {'results': [vib_high, vib_mid], 'historical_positions': []}}}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', "
            "signal_dir='unused-signals', positions_dir='unused-positions', "
            "rerun_fn=lambda: None)\n"
        ).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(
            [item.label for item in app.expander if item.label.startswith(("SHB", "VIB"))],
            [
                "VIB — vib_high — no-background-theme",
                "VIB — vib_mid — no-background-theme",
                "SHB — shb_low — no-background-theme",
            ],
        )

    def test_validate_test_sort_globally_uses_test_win_rate_across_tickers(self):
        def item(rulebook_id, training_win_rate, test_win_rate):
            return {
                "availability": "available",
                "horizon": "swing",
                "rulebook_id": rulebook_id,
                "preferred_variant": "no-background-theme",
                "monitoring": {
                    "match_level": 100.0,
                    "match_classification": "closely_match",
                },
                "position_action": "can BUY",
                "signal_date": "2026-09-04",
                "win_rate": {"training": training_win_rate, "test": test_win_rate},
                "audit_eligibility": {},
                "evidence_eligibility": {},
                "current": {},
                "candidate": {
                    "treatments": {
                        "no-background-theme": {
                            "training": {"win_rate": training_win_rate, "profit_pct": 0.0},
                            "test": {"win_rate": test_win_rate, "profit_pct": 0.0},
                        }
                    }
                },
                "evaluation_label": "Exploratory — gross",
                "partition_labels": {},
            }

        shb = item("shb_mid", 90.0, 55.0)
        vib_high = item("vib_high", 10.0, 65.0)
        vib_low = item("vib_low", 80.0, 30.0)
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page, _VALIDATE_WIN_RATE_SORT_KEY\n"
            f"shb = {shb!r}\n"
            f"vib_high = {vib_high!r}\n"
            f"vib_low = {vib_low!r}\n"
            "st.session_state[_VALIDATE_WIN_RATE_SORT_KEY] = 'Test DESC'\n"
            "st.session_state['backtest_v4_validation_result'] = {'by_ticker': {"
            "'SHB': {'results': [shb], 'historical_positions': []}, "
            "'VIB': {'results': [vib_high, vib_low], 'historical_positions': []}}}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', "
            "signal_dir='unused-signals', positions_dir='unused-positions', "
            "rerun_fn=lambda: None)\n"
        ).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(
            [item.label for item in app.expander if item.label.startswith(("SHB", "VIB"))],
            [
                "VIB — vib_high — no-background-theme",
                "SHB — shb_mid — no-background-theme",
                "VIB — vib_low — no-background-theme",
            ],
        )

    def test_validate_result_keeps_stored_order_with_no_win_rate_sort(self):
        def item(rulebook_id, training_win_rate, test_win_rate):
            return {
                "availability": "available",
                "horizon": "swing",
                "rulebook_id": rulebook_id,
                "preferred_variant": "no-background-theme",
                "monitoring": {
                    "match_level": 100.0,
                    "match_classification": "closely_match",
                },
                "position_action": "can BUY",
                "audit_eligibility": {},
                "evidence_eligibility": {},
                "current": {},
                "candidate": {
                    "treatments": {
                        "no-background-theme": {
                            "training": {
                                "win_rate": training_win_rate,
                                "profit_pct": 0.0,
                            },
                            "test": {
                                "win_rate": test_win_rate,
                                "profit_pct": 0.0,
                            },
                        }
                    }
                },
                "evaluation_label": "Exploratory — gross",
                "partition_labels": {},
            }

        low = item("low", 90.0, 10.0)
        high = item("high", 10.0, 90.0)
        app = AppTest.from_string(
            "from pages.backtest_lab import _render_validation_result\n"
            f"result = {{'results': [{low!r}, {high!r}], 'historical_positions': []}}\n"
            "_render_validation_result('FPT', result, {'closely_match'}, win_rate_partition=None)\n"
        ).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(
            [item.label for item in app.expander],
            [
                "FPT — low — no-background-theme",
                "FPT — high — no-background-theme",
            ],
        )
        self.assertEqual(app.subheader, [])

    def test_validate_flat_result_prefixes_historical_positions(self):
        item = {
            "availability": "available",
            "horizon": "swing",
            "rulebook_id": "rule",
            "preferred_variant": "no-background-theme",
            "evaluation_label": "Exploratory — gross",
            "monitoring": {"match_level": 100.0, "match_classification": "closely_match"},
            "position_action": "can BUY",
            "audit_eligibility": {},
            "evidence_eligibility": {},
            "current": {},
            "candidate": {"treatments": {}},
            "partition_labels": {},
        }
        app = AppTest.from_string(
            "from pages.backtest_lab import _render_validation_result\n"
            f"item = {item!r}\n"
            "_render_validation_result('FPT', {'results': [item], 'historical_positions': [{}]}, {'closely_match'})\n"
        ).run()

        self.assertTrue(any(
            caption.value == "FPT: Historical positions are P&L/manual-management history only."
            for caption in app.caption
        ))

    def test_validate_classification_filters_latest_success_without_replay(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from datetime import date\n"
            "from backtest_engine.listing_status import ListingStatus\n"
            "from pages.backtest_lab import render_backtest_page\n"
            "item = {'availability': 'available', 'horizon': 'swing', 'rulebook_id': 'rule', 'preferred_variant': 'no-background-theme', 'evaluation_label': 'Exploratory — gross', 'monitoring': {'match_level': 10.0, 'match_classification': 'no_match'}, 'buy_block_reason': None, 'audit_eligibility': {}, 'current': {}, 'candidate': {'treatments': {}}}\n"
            "def validate(ticker, *_args):\n"
            "    st.session_state['validate_calls'] = st.session_state.get('validate_calls', 0) + 1\n"
            "    return {'ticker': ticker, 'results': [item], 'historical_positions': []}\n"
            "def listing_statuses(tickers, _engine): return {ticker: ListingStatus(ticker, 'listed', date(2026, 9, 9), date(2026, 9, 9)) for ticker in tickers}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', signal_dir='unused-signals', positions_dir='unused-positions', validate_fn=validate, position_overview_fn=lambda *_args: {'rows': [], 'errors': ()}, listing_statuses_fn=listing_statuses, rerun_fn=lambda: None)\n"
        ).run()
        next(
            item for item in app.text_input if item.key == "backtest_validate_tickers_v4"
        ).set_value("FPT").run()
        next(item for item in app.button if item.label == "Validate").click().run()
        next(item for item in app.pills if item.label == "Class").set_value(["Weak"]).run()

        self.assertEqual(app.session_state["validate_calls"], 1)
        self.assertFalse(any(item.value == "FPT" for item in app.subheader))
        self.assertEqual(
            [item for item in app.expander if item.label != "New Position"], []
        )

    def test_validate_trend_filter_filters_cached_results_without_replay(self):
        source = inspect.getsource(backtest_lab._render_validate)
        self.assertIn('st.caption("Trend")', source)

        def item(rulebook_id, state):
            return {
                "availability": "available",
                "horizon": "swing",
                "rulebook_id": rulebook_id,
                "preferred_variant": "no-background-theme",
                "evaluation_label": "Exploratory — gross",
                "monitoring": {
                    "match_level": 100.0,
                    "match_classification": "closely_match",
                },
                "position_action": "can BUY",
                "signal_state": {"state": state, "reasons": []},
                "audit_eligibility": {},
                "evidence_eligibility": {},
                "current": {},
                "candidate": {"treatments": {}},
                "partition_labels": {},
            }

        fresh = item("fresh-rule", "fresh")
        weakening = item("weakening-rule", "weakening")
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from datetime import date\n"
            "from backtest_engine.listing_status import ListingStatus\n"
            "from pages.backtest_lab import render_backtest_page\n"
            "def validate(ticker, *_args):\n"
            "    st.session_state['validate_calls'] = st.session_state.get('validate_calls', 0) + 1\n"
            f"    return {{'ticker': ticker, 'results': [{fresh!r}, {weakening!r}], 'historical_positions': []}}\n"
            "def listing_statuses(tickers, _engine): return {ticker: ListingStatus(ticker, 'listed', date(2026, 9, 9), date(2026, 9, 9)) for ticker in tickers}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', signal_dir='unused-signals', positions_dir='unused-positions', validate_fn=validate, position_overview_fn=lambda *_args: {'rows': [], 'errors': ()}, listing_statuses_fn=listing_statuses, rerun_fn=lambda: None)\n"
        ).run()

        next(
            control for control in app.text_input
            if control.key == "backtest_validate_tickers_v4"
        ).set_value("FPT").run()
        next(control for control in app.button if control.label == "Validate").click().run()
        next(control for control in app.pills if control.label == "Trend").set_value(
            ["Fresh"]
        ).run()

        self.assertEqual(app.session_state["validate_calls"], 1)
        self.assertEqual(
            [
                control.label for control in app.expander
                if control.label != "New Position"
            ],
            ["FPT — fresh-rule — no-background-theme"],
        )

    def test_validate_trend_filter_switches_between_dpm_like_state_sets(self):
        def item(rulebook_id, state):
            return {
                "availability": "available",
                "horizon": "swing",
                "rulebook_id": rulebook_id,
                "preferred_variant": "no-background-theme",
                "evaluation_label": "Exploratory — gross",
                "monitoring": {
                    "match_level": 100.0,
                    "match_classification": "closely_match",
                },
                "position_action": "expired BUY",
                "signal_state": {"state": state, "reasons": []},
                "audit_eligibility": {},
                "evidence_eligibility": {},
                "current": {},
                "candidate": {"treatments": {}},
                "partition_labels": {},
            }

        items = [
            *(item(f"invalidated-{index}", "invalidated") for index in range(5)),
            item("weakening", "weakening"),
        ]
        app = AppTest.from_string(
            "from datetime import date\n"
            "from backtest_engine.listing_status import ListingStatus\n"
            "from pages.backtest_lab import render_backtest_page\n"
            f"items = {items!r}\n"
            "def listing_statuses(tickers, _engine): return {ticker: ListingStatus(ticker, 'listed', date(2026, 9, 9), date(2026, 9, 9)) for ticker in tickers}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', signal_dir='unused-signals', positions_dir='unused-positions', validate_fn=lambda ticker, *_args: {'ticker': ticker, 'results': items, 'historical_positions': []}, position_overview_fn=lambda *_args: {'rows': [], 'errors': ()}, listing_statuses_fn=listing_statuses, rerun_fn=lambda: None)\n"
        ).run()
        next(
            control for control in app.text_input
            if control.key == "backtest_validate_tickers_v4"
        ).set_value("DPM").run()
        next(control for control in app.button if control.label == "Validate").click().run()

        def visible_candidates():
            return [
                control.label for control in app.expander
                if control.label.endswith("— no-background-theme")
            ]

        self.assertEqual(len(visible_candidates()), 6)
        trend = next(control for control in app.pills if control.label == "Trend")
        trend.set_value(["Fresh", "On-going", "Weakening"]).run()
        self.assertEqual(visible_candidates(), ["DPM — weakening — no-background-theme"])
        trend = next(control for control in app.pills if control.label == "Trend")
        trend.set_value(["Invalidated"]).run()
        self.assertEqual(len(visible_candidates()), 5)
        trend = next(control for control in app.pills if control.label == "Trend")
        trend.set_value(list(backtest_lab.TREND_STATE_OPTIONS)).run()
        self.assertEqual(len(visible_candidates()), 6)

    def test_validate_default_trend_filter_retains_legacy_cached_item(self):
        legacy_item = {
            "availability": "available",
            "horizon": "swing",
            "monitoring": {"match_classification": "closely_match"},
            "position_action": "can BUY",
        }

        self.assertEqual(
            backtest_lab._available_validation_items(
                [legacy_item],
                {"closely_match"},
                "ALL",
                "Both",
                set(backtest_lab.TREND_STATE_VALUES.values()),
            ),
            [legacy_item],
        )

    def test_validate_position_action_labels_count_valid_cached_items(self):
        labels_fn = getattr(backtest_lab, "_position_action_filter_labels", None)
        self.assertTrue(callable(labels_fn))
        items = [
            {"position_action": "can BUY"},
            {"position_action": "can BUY"},
            {"position_action": "expired BUY"},
            {"position_action": "HOLD"},
        ]

        self.assertEqual(
            labels_fn(items),
            {
                "ALL": "ALL - 4",
                "can BUY": "can BUY - 2",
                "expired BUY": "expired BUY - 1",
                "can SELL": "can SELL - 0",
                "HOLD": "HOLD - 1",
            },
        )

    def test_validate_position_action_filter_uses_all_default_and_two_rows(self):
        source = inspect.getsource(backtest_lab._render_validate)

        self.assertIn('"Position actions"', source)
        self.assertIn("_position_action_filter_labels", source)
        self.assertIn("tuple(action_labels)", source)
        self.assertIn('st.caption("Trend")', source)
        self.assertIn('"Horizon"', source)
        self.assertIn('st.caption("Class")', source)
        self.assertIn("_VIEW_SIGNAL_HORIZON_OPTIONS", source)
        self.assertIn("validate_row = st.columns", source)
        self.assertIn("filters = st.columns", source)
        self.assertLess(
            source.index("validate_row = st.columns"),
            source.index("filters = st.columns"),
        )
        self.assertLess(
            source.index('"Class"'),
            source.index('"Position actions"'),
        )
        self.assertLess(source.index('st.caption("Class")'), source.index("st.popover"))
        self.assertLess(
            source.index('"Position actions"'), source.index('st.caption("Trend")')
        )
        self.assertLess(
            source.index('st.caption("Trend")'), source.index('"Horizon"')
        )
        self.assertLess(
            source.index("validate_clicked = validate_row[2].button("),
            source.index("filters = st.columns"),
        )

    def test_validate_group_continues_after_ticker_failure(self):
        app = self._validation_group_app(failing_ticker="VCB")
        next(
            item for item in app.selectbox if item.label == "Ticker group"
        ).set_value("BANK").run()
        next(item for item in app.button if item.label == "Validate").click().run()

        self.assertEqual(app.session_state["validation_calls"], ["VCB", "TCB"])
        self.assertTrue(
            any("Validate VCB failed: broken artifact" == item.value for item in app.error)
        )

    def test_current_positions_keeps_toolbar_and_renders_buy_sell_group(self):
        app = self._grouped_positions_app([self._position_row()])
        source = inspect.getsource(backtest_lab._render_positions)

        ticker_filter = next(
            item
            for item in app.selectbox
            if item.key == backtest_lab._POSITION_TICKER_FILTER_KEY
        )
        self.assertEqual(ticker_filter.options, ["ALL", "FPT"])
        self.assertFalse(any(item.label == "Ticker filter" for item in app.text_input))
        self.assertTrue(any(item.label == "State" for item in app.pills))
        self.assertIn('st.caption("State")', source)
        self.assertLess(source.index('st.caption("State")'), source.index("st.popover"))
        self.assertTrue(any(item.label == "Sort by" for item in app.selectbox))
        self.assertTrue(any(item.label == "Direction" for item in app.selectbox))
        self.assertIn(
            'st.expander("New Position", expanded=False)',
            inspect.getsource(backtest_lab._render_new_position_section),
        )
        self.assertTrue(any(item.label == ":material/refresh:" for item in app.button))
        self.assertEqual(app.get("data_editor"), [])
        self.assertIn(
            'st.table(styled, width="content")',
            inspect.getsource(backtest_lab._render_position_trade_group),
        )

        group = next(item for item in app.expander if "FPT" in item.label)
        self.assertEqual(
            group.label,
            "FPT — OPEN — 2.00% — 4 sessions — BUY: 50.0 — "
            "SELL: Projected exit: - | Holding: 22 | SL/TP: 48.5 / 52.5",
        )
        self.assertEqual(group.dataframe, [])
        trade_frame = group.table[0].value
        self.assertEqual(trade_frame["Trade"].tolist(), ["BUY", "SELL"])
        self.assertEqual(trade_frame.loc[0, "Risk Suggestion"], "N/A")
        self.assertEqual(trade_frame.loc[1, "Actual SELL"], "-")
        self.assertTrue(any(button.label == "Edit position" for button in group.button))
        self.assertEqual(app.exception, [])

    def test_current_positions_ticker_dropdown_lists_loaded_tickers_and_filters_rows(self):
        app = self._grouped_positions_app(
            [
                self._position_row("manual-fpt", "FPT"),
                self._position_row("manual-vcb", "VCB"),
            ]
        )

        ticker_filter = next(
            item
            for item in app.selectbox
            if item.key == backtest_lab._POSITION_TICKER_FILTER_KEY
        )
        self.assertEqual(ticker_filter.options, ["ALL", "FPT", "VCB"])

        ticker_filter.set_value("VCB").run()

        position_expanders = [
            item
            for item in app.expander
            if " — OPEN — " in item.label
        ]
        self.assertEqual(
            [item.label.split(" — ", maxsplit=1)[0] for item in position_expanders],
            ["VCB"],
        )

    def test_validate_positions_offers_all_selection_and_finished_progress_feedback(self):
        source = inspect.getsource(backtest_lab._render_validate_positions)

        self.assertIn("st.checkbox(", source)
        self.assertIn('"All"', source)
        self.assertIn("_apply_validate_position_select_all", source)
        self.assertIn("progress = st.progress", source)
        self.assertIn("time.sleep(3)", source)

    def test_validate_position_result_risk_is_capitalized_and_horizon_separated(self):
        self.assertEqual(
            "Swing: 50.0% - 🟡 Medium | Mid-term: 75.0% - 🟠 High",
            backtest_lab._validate_position_risk_display(
                "Swing: 50.0% - medium\nMid-term: 75.0% - high"
            ),
        )
        self.assertEqual(
            "Swing: 25.0% - 🟢 Low | Mid-term: 100.0% - 🔴 Very",
            backtest_lab._validate_position_risk_display(
                "Swing: 25.0% - low\nMid-term: 100.0% - very"
            ),
        )
        self.assertEqual("N/A", backtest_lab._validate_position_risk_display("N/A"))

    def test_validate_position_result_shows_the_risk_level_color_legend(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages import backtest_lab as lab\n"
            "st.session_state[lab._VALIDATE_POSITION_RESULT_KEY] = {\n"
            "    'as_of_date': '2026-09-09',\n"
            "    'results': [{'ticker': 'FPT', 'evaluation': 'Swing', 'risk_suggestion': 'Swing: 50.0% - medium', 'result': 'Updated'}],\n"
            "}\n"
            "lab._render_validate_positions(object(), 'unused-positions', candidates_fn=lambda _dir: ())\n"
        ).run()

        self.assertIn(
            "🟢 Low · 🟡 Medium · 🟠 High · 🔴 Very",
            [item.value for item in app.caption],
        )

    def test_validate_position_result_rows_project_triangle_trend_before_profit(self):
        rows = backtest_lab._validate_position_result_rows(
            [{
                "ticker": "FPT", "evaluation": "Swing", "profit_pct": 2.0,
                "profit_raw": 2_000, "risk_suggestion": "Swing: 50.0% - medium",
                "result": "Updated",
            }]
        )

        self.assertEqual(
            [{
                "Ticker": "FPT", "Trend": "▲", "Profit %": "2.00%", "Profit": "2.00",
                "Risk": "Swing: 50.0% - 🟡 Medium", "Result": "Updated",
            }],
            rows,
        )

    def test_validate_position_result_rows_round_profit_to_two_decimals(self):
        rows = backtest_lab._validate_position_result_rows(
            [
                {"ticker": "AAA", "profit_raw": 2_344},
                {"ticker": "BBB", "profit_raw": -2_346},
                {"ticker": "CCC", "profit_raw": 0},
                {"ticker": "DDD", "profit_raw": None},
            ]
        )

        self.assertEqual(
            ["2.34", "-2.35", "0.00", "-"],
            [row["Profit"] for row in rows],
        )

    def test_validate_position_result_styles_color_only_the_trend_triangles(self):
        frame = pd.DataFrame(
            [
                {"Trend": "▲"},
                {"Trend": "▼"},
                {"Trend": "▶"},
                {"Trend": "-"},
            ]
        )

        styles = backtest_lab._validate_position_result_styles(frame)

        self.assertEqual("color: #22c55e", styles.loc[0, "Trend"])
        self.assertEqual("color: #ef4444", styles.loc[1, "Trend"])
        self.assertEqual("color: #eab308", styles.loc[2, "Trend"])
        self.assertEqual("", styles.loc[3, "Trend"])

    def test_validate_position_trend_uses_profit_direction(self):
        self.assertEqual(
            ("▲", "▼", "▶", "-"),
            tuple(
                backtest_lab._validate_position_trend(value)
                for value in (2_000, -2_000, 0, None)
            ),
        )

    def test_validate_positions_all_selects_every_current_candidate_for_batched_run(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page\n"
            "candidates = tuple({'id': f'position-{index}', 'ticker': f'T{index}', 'evaluation': 'Swing', 'position': {'buy_date': '2026-08-01'}} for index in range(1, 7))\n"
            "def validate(ids, *_args, progress_fn=None):\n"
            "    st.session_state['validated_position_ids'] = ids\n"
            "    progress_fn(min(5, len(ids)), len(ids))\n"
            "    progress_fn(len(ids), len(ids))\n"
            "    return {'as_of_date': '2026-09-04', 'results': []}\n"
            "render_backtest_page(\n"
            "    engine=object(), positions_dir='unused-positions',\n"
            "    risk_candidates_fn=lambda _positions_dir: candidates,\n"
            "    validate_positions_fn=validate,\n"
            "    position_overview_fn=lambda *_args: {'rows': [], 'errors': ()},\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

        next(item for item in app.checkbox if item.label == "All").set_value(True).run()
        next(item for item in app.button if item.label == "Run validation").click()
        app.run(timeout=5)

        self.assertEqual(
            tuple(f"position-{index}" for index in range(1, 7)),
            app.session_state["validated_position_ids"],
        )
        self.assertFalse(next(item for item in app.checkbox if item.label == "All").value)
        self.assertEqual(app.exception, [])

    def test_closed_position_expander_shows_actual_sell_price_only(self):
        app = self._grouped_positions_app([self._position_row(status="closed")])
        next(
            item for item in app.pills if item.label == "State"
        ).set_value(["OPEN", "CLOSED"]).run()

        group = next(item for item in app.expander if "FPT" in item.label)

        self.assertEqual(
            group.label,
            "FPT — CLOSED — 4.00% — 5 sessions — BUY: 50.0 — SELL: 52.0",
        )

    def test_new_position_form_uses_requested_field_rows(self):
        source = inspect.getsource(backtest_lab._render_new_position_section)

        self.assertIn("identity_row = st.columns((1, 1, 2))", source)
        self.assertIn("trade_row = st.columns(5)", source)
        self.assertLess(source.index("identity_row"), source.index("trade_row"))
        self.assertLess(source.index("trade_row"), source.index('"Add Position",'))

    def test_new_open_position_sell_date_is_empty(self):
        app = self._grouped_positions_app([])
        sell_date = next(item for item in app.date_input if item.label == "SELL date")

        self.assertIsNone(sell_date.value)

    def test_new_position_success_resets_all_form_values_to_defaults(self):
        with tempfile.TemporaryDirectory() as positions_dir:
            app = self._grouped_positions_app([], positions_dir=positions_dir)
            next(
                item for item in app.text_input
                if item.key == "backtest_new_position_ticker_v4"
            ).set_value("FPT").run()
            next(item for item in app.number_input if item.label == "BUY price").set_value(51.2).run()
            next(item for item in app.number_input if item.label == "Volume (0 = unspecified)").set_value(100).run()
            next(item for item in app.number_input if item.label == "SELL price").set_value(52.0).run()

            next(item for item in app.button if item.label == "Add Position").click().run()
            app.run()
            app.run()

            self.assertEqual(
                next(
                    item for item in app.text_input
                    if item.key == "backtest_new_position_ticker_v4"
                ).value,
                "",
            )
            self.assertEqual(next(item for item in app.selectbox if item.label == "State").value, "OPEN")
            self.assertEqual(next(item for item in app.selectbox if item.label == "Saved signal set").value, "Manual P&L only")
            self.assertEqual(next(item for item in app.number_input if item.label == "BUY price").value, 0.001)
            self.assertEqual(next(item for item in app.number_input if item.label == "Volume (0 = unspecified)").value, 0)
            self.assertEqual(next(item for item in app.number_input if item.label == "SELL price").value, 0.0)
            self.assertIsNone(next(item for item in app.date_input if item.label == "SELL date").value)

    def test_position_mutations_render_busy_states(self):
        create_source = inspect.getsource(backtest_lab._render_new_position_section)
        delete_source = inspect.getsource(backtest_lab._render_delete_confirmation)

        self.assertIn('on_click=_mark_position_create_busy', create_source)
        self.assertIn('with st.spinner("Adding position…")', create_source)
        self.assertIn('on_click=_mark_position_delete_busy', delete_source)
        self.assertIn('with st.spinner("Deleting selected positions…")', delete_source)

    def test_validation_result_shows_action_and_collapsed_json(self):
        source = inspect.getsource(backtest_lab._render_validation_candidate)
        self.assertIn("position_action", source)
        self.assertIn("signal_state", source)
        self.assertIn("expanded=False", source)
        self.assertLess(source.index("action ="), source.index("st.caption"))
        item = {
            "availability": "available",
            "horizon": "swing",
            "rulebook_id": "rule",
            "preferred_variant": "no-background-theme",
            "evaluation_label": "Exploratory — gross",
            "monitoring": {
                "match_level": 100.0,
                "match_classification": "closely_match",
            },
            "position_action": "can BUY",
            "signal_state": {"state": "ongoing", "reasons": []},
            "signal_date": "2026-08-14",
            "win_rate": {"training": 62.5, "test": 55.0},
            "audit_eligibility": {},
            "evidence_eligibility": {"status": "eligible"},
            "partition_labels": {"training": "in-sample", "test": "historical test — previously observed"},
            "current": {},
            "candidate": {"treatments": {}},
        }
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            f"item = {item!r}\n"
            "lab._render_validation_result(\n"
            "    'VCB', {'results': [item], 'historical_positions': []},\n"
            "    {'closely_match'},\n"
            ")\n"
        ).run()

        self.assertTrue(any(
            entry.value == (
                "Monitoring: 100.0% - closely match | can BUY | trend: On-going | "
                "signal date: 14/08/2026 | win rate training / test: 62.5% / 55.0%"
            )
            for entry in app.markdown
        ))
        self.assertTrue(any(entry.value == "Evidence: eligible" for entry in app.caption))

    def test_validation_result_displays_regeneration_reason(self):
        app = AppTest.from_string(
            "import pages.backtest_lab as lab\n"
            "lab._render_validation_result(\n"
            "    'VCB', {'results': [{'availability': 'unavailable', 'reason': 'source_history_changed'}], 'historical_positions': []},\n"
            "    {'closely_match'},\n"
            ")\n"
        ).run()

        self.assertTrue(any(
            item.value == "VCB: Validation unavailable: source_history_changed"
            for item in app.warning
        ))

    def test_new_position_refreshes_saved_sets_for_committed_ticker(self):
        eligible = {
            "buy_eligible": True,
            "horizon": "swing",
            "rulebook_id": "swing_rulebook_v5__rsi_upcross",
            "preferred_variant": "no-background-theme",
            "signal_reference": {"schema_version": 5, "horizon": "swing"},
        }
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page\n"
            f"eligible = {eligible!r}\n"
            "if 'new_position_validation_calls' not in st.session_state:\n"
            "    st.session_state['new_position_validation_calls'] = []\n"
            "def validate(ticker, *_args):\n"
            "    st.session_state['new_position_validation_calls'] = st.session_state.get('new_position_validation_calls', []) + [ticker]\n"
            "    return {'ticker': ticker, 'results': [eligible], 'historical_positions': []}\n"
            "render_backtest_page(\n"
            "    engine=object(), status_dir='unused-status', signal_dir='unused-signals',\n"
            "    positions_dir='unused-positions', validate_fn=validate,\n"
            "    position_overview_fn=lambda engine, positions_dir: {'rows': [], 'errors': ()},\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

        ticker = next(
            item for item in app.text_input if item.key == "backtest_new_position_ticker_v4"
        )
        ticker.set_value("fpt").run()

        self.assertEqual(app.session_state["new_position_validation_calls"], ["FPT"])
        ticker = next(
            item for item in app.text_input if item.key == "backtest_new_position_ticker_v4"
        )
        self.assertEqual(ticker.value, "FPT")
        saved_set = next(item for item in app.selectbox if item.label == "Saved signal set")
        self.assertEqual(
            saved_set.options,
            [
                "Manual P&L only",
                "Swing — swing_rulebook_v5__rsi_upcross — no-background-theme",
            ],
        )

    def test_ineligible_saved_signal_set_message_lists_each_set_and_signal_date(self):
        message = backtest_lab._ineligible_saved_signal_set_message(
            "VIC",
            {
                "results": [
                    {
                        "buy_block_reason": "evidence_ineligible",
                        "signal_date": "2026-08-24",
                        "horizon": "swing",
                        "rulebook_id": "swing_rulebook_v5__adx",
                        "preferred_variant": "no-background-theme",
                    },
                    {
                        "buy_block_reason": "evidence_ineligible",
                        "signal_date": "2026-09-04",
                        "horizon": "swing",
                        "rulebook_id": "swing_rulebook_v5__rsi_upcross",
                        "preferred_variant": "background-theme",
                    },
                    {
                        "buy_block_reason": "evidence_ineligible",
                        "signal_date": "invalid",
                        "horizon": "midterm",
                        "rulebook_id": "midterm_rulebook_v5__volume",
                        "preferred_variant": "no-background-theme",
                    },
                ]
            },
        )

        self.assertEqual(
            "VIC: saved signal sets found, but none are BUY-eligible "
            "(evidence ineligible).\n\n"
            "- Swing — swing_rulebook_v5__adx — no-background-theme - signal date: 24/08/2026\n"
            "- Swing — swing_rulebook_v5__rsi_upcross — background-theme - signal date: 04/09/2026\n"
            "- Mid-term — midterm_rulebook_v5__volume — no-background-theme - signal date: —",
            message,
        )

    def test_new_position_is_collapsed_section_before_filters(self):
        section_source = inspect.getsource(backtest_lab._render_new_position_section)
        positions_source = inspect.getsource(backtest_lab._render_positions)

        self.assertIn('st.expander("New Position", expanded=False)', section_source)
        self.assertNotIn('st.popover("New position")', section_source)
        self.assertIn("identity_row = st.columns((1, 1, 2))", section_source)
        self.assertIn("trade_row = st.columns(5)", section_source)
        self.assertIn('"BUY price"', section_source)
        self.assertIn('"SELL price"', section_source)
        self.assertNotIn('"New BUY price', section_source)
        self.assertLess(
            positions_source.index("_render_new_position_section("),
            positions_source.index("toolbar = st.columns(5)"),
        )

    def test_closed_group_marks_only_real_risk_suggestion_as_historical(self):
        row = self._position_row(
            "legacy-1",
            "VCB",
            "closed",
            record_source="manual",
            risk_suggestion_text="Swing: 90% - very",
        )
        buy, sell = backtest_lab.build_position_trade_rows(row)
        frame = backtest_lab._position_trade_display_frame(buy, sell)
        styles = backtest_lab._position_trade_display_styles(frame, buy=buy)

        self.assertEqual(frame.loc[0, "Risk Suggestion"], "Swing: 90% - very")
        self.assertEqual(styles.loc[0, "Risk Suggestion"], "text-decoration: line-through")
        self.assertEqual(int((styles == "text-decoration: line-through").sum().sum()), 1)
        self.assertEqual(frame.loc[1, "Actual SELL"], "52.0 / 2026-08-10")

    def test_position_trade_display_separates_rulebook_and_theme(self):
        buy, sell = backtest_lab.build_position_trade_rows(self._position_row())
        for variant, theme in (
            ("no-background-theme", "Excluded"),
            ("background-theme", "Included"),
        ):
            with self.subTest(variant=variant):
                buy["signal_set"] = (
                    f"Swing — swing_rulebook_v5__joint_trend — {variant}"
                )

                frame = backtest_lab._position_trade_display_frame(buy, sell)

                self.assertEqual(
                    frame.loc[0, "Saved signal set"],
                    f"swing_rulebook_v5__joint_trend\nTheme: {theme}",
                )
                self.assertEqual(frame.loc[1, "Saved signal set"], "-")
                self.assertEqual(frame.loc[0, "Risk Suggestion"], "N/A")

    def test_editor_row_to_updates_retains_raw_price_and_optional_volume_contract(self):
        updates = backtest_lab._editor_row_to_updates(
            {
                "State": "CLOSED",
                "BUY price (k)": 51.0,
                "BUY date": date(2026, 8, 1),
                "Volume": 100,
                "SELL price (k)": 52.0,
                "SELL date": date(2026, 8, 10),
            }
        )

        self.assertEqual(updates["status"], "closed")
        self.assertEqual(updates["actual_buy_price"], 51000)
        self.assertEqual(updates["actual_sell_price"], 52000)
        self.assertEqual(updates["quantity"], 100)

    def test_position_filter_sort_and_immutable_locator_routing_are_preserved(self):
        rows = [
            self._position_row("manual-new", "FPT"),
            self._position_row("legacy-old", "VCB", record_source="legacy"),
        ]
        rows[0]["opened_at"] = "2026-08-10T09:00:00+07:00"
        rows[1]["opened_at"] = "2026-08-01T09:00:00+07:00"
        ordered = backtest_lab._filter_and_sort_positions(
            rows, "", ("OPEN",), "Open date", "ASC"
        )
        self.assertEqual(
            [row["id"] for row in ordered], ["legacy-old", "manual-new"]
        )
        filtered = backtest_lab._filter_and_sort_positions(
            rows, "fpt", ("OPEN",), "Open date", "ASC"
        )
        self.assertEqual([row["id"] for row in filtered], ["manual-new"])

        calls = []

        def legacy_update(*args):
            calls.append(("legacy", args))
            return {"id": args[3]}

        def manual_update(*args):
            calls.append(("manual", args))
            return {"id": args[1]}

        result = backtest_lab._update_by_locator(
            rows[1]["position_locator"],
            {"actual_buy_price": 51000},
            "positions",
            legacy_update,
            manual_update,
        )
        self.assertEqual(result["id"], "legacy-old")
        self.assertEqual([kind for kind, _args in calls], ["legacy"])
        self.assertEqual(calls[0][1][:4], ("VCB", "no-background-theme", "win_rate", "legacy-old"))

    def test_group_local_editor_updates_the_existing_manual_history(self):
        with tempfile.TemporaryDirectory() as directory:
            position = create_manual_position(
                "FPT", 50000, "2026-08-01", positions_dir=directory
            )
            row = self._position_row(position["id"])
            row["opened_at"] = position["opened_at"]
            row["position"]= position
            row["position_locator"] = {
                "record_source": "manual",
                "ticker": "FPT",
                "id": position["id"],
            }
            app = self._grouped_positions_app([row], positions_dir=directory)

            next(
                button for button in app.button if button.label == "Edit position"
            ).click().run()
            next(
                item for item in app.number_input if item.label == "BUY price (k)"
            ).set_value(51.0).run()
            next(
                button
                for button in app.button
                if button.label == "Save position changes"
            ).click().run()

            saved = load_manual_position_history("FPT", directory)["history"][0]

        self.assertEqual(saved["actual_buy_price"], 51000)
        self.assertEqual(app.exception, [])

    def test_failed_group_edit_preserves_entered_values(self):
        row = self._position_row()
        app = AppTest.from_string(
            "from pages.backtest_lab import render_backtest_page\n"
            f"rows = {[row]!r}\n"
            "def reject(*args, **kwargs):\n"
            "    raise ValueError('edit rejected')\n"
            "render_backtest_page(\n"
            "    engine=object(), status_dir='unused-status-dir',\n"
            "    signal_dir='unused-signal-dir', positions_dir='unused-positions',\n"
            "    position_overview_fn=lambda engine, positions_dir: "
            "{'rows': rows, 'errors': ()}, manual_update_fn=reject,\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

        next(
            button for button in app.button if button.label == "Edit position"
        ).click().run()
        buy_input = next(
            item for item in app.number_input if item.label == "BUY price (k)"
        )
        buy_input.set_value(51.0).run()
        next(
            button for button in app.button if button.label == "Save position changes"
        ).click().run()

        self.assertEqual(
            next(
                item for item in app.number_input if item.label == "BUY price (k)"
            ).value,
            51.0,
        )
        self.assertTrue(any("edit rejected" in item.value for item in app.error))
        self.assertEqual(app.exception, [])

    def test_select_all_visible_syncs_groups_in_both_directions_and_delete_state(self):
        app = self._grouped_positions_app(
            [
                self._position_row("manual-1", "FPT"),
                self._position_row("legacy-2", "VCB", record_source="legacy"),
            ]
        )
        select_all = next(
            item for item in app.checkbox if item.label == "Select all visible"
        )
        delete = next(
            button for button in app.button if button.label == ":material/delete:"
            and button.help == "Delete selected positions (0)"
        )
        self.assertTrue(delete.disabled)

        select_all.set_value(True).run()

        self.assertEqual(
            [widget.value for widget in self._position_select_widgets(app)],
            [True, True],
        )
        self.assertFalse(
            next(
                button for button in app.button if button.label == ":material/delete:"
                and button.help == "Delete selected positions (2)"
            ).disabled
        )

        next(
            item for item in app.checkbox if item.label == "Select all visible"
        ).set_value(False).run()

        self.assertEqual(
            [widget.value for widget in self._position_select_widgets(app)],
            [False, False],
        )
        self.assertTrue(
            next(
                button for button in app.button if button.label == ":material/delete:"
                and button.help == "Delete selected positions (0)"
            ).disabled
        )
        self.assertEqual(app.exception, [])

    def test_group_delete_requires_confirmation_and_prevalidates_every_locator(self):
        rows = [
            self._position_row("manual-1", "FPT"),
            self._position_row("legacy-2", "VCB", record_source="legacy"),
        ]
        entries = backtest_lab._prepare_batch_delete(
            rows, {"manual-1", "legacy-2"}
        )
        self.assertEqual(
            [entry["position_id"] for entry in entries],
            ["manual-1", "legacy-2"],
        )
        invalid = [rows[0], {**rows[1], "position_locator": {"id": "legacy-2"}}]
        with self.assertRaises(ValueError):
            backtest_lab._prepare_batch_delete(
                invalid, {"manual-1", "legacy-2"}
            )

        app = self._grouped_positions_app(rows)
        next(
            item for item in app.checkbox if item.label == "Select all visible"
        ).set_value(True).run()
        next(
            button for button in app.button if button.label == ":material/delete:"
            and button.help == "Delete selected positions (2)"
        ).click().run()
        self.assertEqual(len(app.get("dialog")), 1)
        self.assertTrue(
            any(button.label == "Confirm permanent delete" for button in app.button)
        )
        self.assertEqual(app.exception, [])

    def test_pending_delete_confirmation_requires_unchanged_display_context(self):
        context = backtest_lab._position_display_context(
            "fpt", ("open",), "Open date", "asc"
        )
        confirmation = {
            "selected_ids": ("manual-1",),
            "display_context": context,
        }
        self.assertTrue(
            backtest_lab._delete_confirmation_is_current(
                confirmation,
                ("manual-1",),
                ("manual-1",),
                backtest_lab._position_display_context(
                    " FPT ", ("OPEN",), "Open date", "ASC"
                ),
            )
        )
        for changed_context in (
            backtest_lab._position_display_context(
                "VCB", ("OPEN",), "Open date", "ASC"
            ),
            backtest_lab._position_display_context(
                "FPT", ("OPEN", "CLOSED"), "Open date", "ASC"
            ),
            backtest_lab._position_display_context(
                "FPT", ("OPEN",), "Ticker", "ASC"
            ),
            backtest_lab._position_display_context(
                "FPT", ("OPEN",), "Open date", "DESC"
            ),
        ):
            self.assertFalse(
                backtest_lab._delete_confirmation_is_current(
                    confirmation,
                    ("manual-1",),
                    ("manual-1",),
                    changed_context,
                )
            )

    def test_batch_delete_feedback_retains_two_second_success_and_rerun_safe_error(self):
        entries = ({"summary": "FPT — OPEN — BUY 50.0 k VND"},)
        success = backtest_lab._batch_delete_feedback(1, entries, None, None)
        self.assertEqual(
            success,
            {
                "level": "success",
                "message": "1 positions permanently deleted.",
                "duration_seconds": 2,
            },
        )

        error = backtest_lab._batch_delete_feedback(
            0, entries, entries[0], ValueError("delete rejected")
        )
        self.assertEqual(error["level"], "error")
        self.assertIsNone(error["duration_seconds"])
        self.assertIn("Deleted 0 of 1 positions", error["message"])
        self.assertIn("delete rejected", error["message"])


if __name__ == "__main__":
    unittest.main()
