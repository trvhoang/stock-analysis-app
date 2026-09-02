"""Backtest Lab schema-5 UI copy, identity, and position-group contracts."""

from __future__ import annotations

from datetime import date
import inspect
import tempfile
import unittest

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
            f"rows = {rows!r}\n"
            "render_backtest_page(\n"
            "    engine=object(), status_dir='unused-status-dir',\n"
            "    signal_dir='unused-signal-dir',\n"
            f"    positions_dir={positions_dir!r},\n"
            "    position_overview_fn=lambda engine, positions_dir: "
            "{'rows': rows, 'errors': ()},\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

    @staticmethod
    def _validation_group_app(
        group_tickers=("VCB", "TCB"), failing_ticker=None
    ):
        return AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page\n"
            f"group_tickers = {group_tickers!r}\n"
            "def group_choices(_signal_dir):\n"
            "    return ('-', 'N/A', 'BANK')\n"
            "def group_resolver(group_name, _signal_dir):\n"
            "    return group_tickers if group_name == 'BANK' else ()\n"
            "def validate(ticker, *_args):\n"
            "    st.session_state['validation_calls'] = st.session_state.get('validation_calls', []) + [ticker]\n"
            f"    if ticker == {failing_ticker!r}:\n"
            "        raise ValueError('broken artifact')\n"
            "    return {'ticker': ticker, 'results': [], 'historical_positions': []}\n"
            "render_backtest_page(\n"
            "    engine=object(), status_dir='unused-status', signal_dir='unused-signals',\n"
            "    positions_dir='unused-positions', validate_fn=validate,\n"
            "    group_choices_fn=group_choices, group_resolver_fn=group_resolver,\n"
            "    rerun_fn=lambda: None,\n"
            ")\n"
        ).run()

    @staticmethod
    def _collect_group_app():
        return AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page\n"
            "def group_choices(_signal_dir):\n"
            "    return ('-', 'N/A', 'BANK')\n"
            "def group_resolver(group_name, _signal_dir):\n"
            "    return ('VCB', 'TCB') if group_name == 'BANK' else ()\n"
            "def submit(config, *_args):\n"
            "    st.session_state['collect_group_config'] = config.to_dict()\n"
            "    return None\n"
            "render_backtest_page(\n"
            "    engine=object(), engine_factory=lambda: None, status_dir='unused-status',\n"
            "    signal_dir='unused-signals', positions_dir='unused-positions',\n"
            "    submit_fn=submit, group_choices_fn=group_choices,\n"
            "    group_resolver_fn=group_resolver,\n"
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
        self.assertEqual([item.label for item in app.selectbox], ["Horizon"])
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

        self.assertEqual([item.label for item in app.multiselect], ["Columns"])
        self.assertEqual(
            app.multiselect[0].value,
            ["Horizon", "Train-test", "n", "Win rate %", "Profit %", "Sharpe"],
        )
        self.assertEqual([item.label for item in app.checkbox], ["Select all visible"])
        source = inspect.getsource(backtest_lab._render_view)
        self.assertIn("st.data_editor(", source)
        self.assertIn("_VIEW_SIGNAL_FIXED_COLUMNS", source)
        self.assertIn("_VIEW_SIGNAL_DEFAULT_COLUMNS", source)
        self.assertIn("toolbar = st.empty()", source)
        self.assertIn("with toolbar.container():", source)
        remove = [item for item in app.button if item.label == "🗑️"][-1]
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
        self.assertFalse([item for item in app.button if item.label == "🗑️"][-1].disabled)

        next(item for item in app.text_input if item.label == "Ticker").set_value("FPT").run()
        self.assertFalse([item for item in app.button if item.label == "🗑️"][-1].disabled)

    def test_view_signals_removal_action_delegates_selected_immutable_identity(self):
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
        [item for item in app.button if item.label == "🗑️"][-1].click().run()

        self.assertTrue(any(item.value == "Removed 1 saved signal(s)." for item in app.success))
        self.assertTrue([item for item in app.button if item.label == "🗑️"][-1].disabled)
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
        [item for item in app.button if item.label == "🗑️"][-1].click().run()

        self.assertTrue(any("VCB / swing / swing_rulebook_v5__adx" in item.value for item in app.error))
        self.assertTrue([item for item in app.button if item.label == "🗑️"][-1].disabled)
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
        self.assertEqual(app.dataframe[0].height, 720)

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
        self.assertNotIn("profitable", source)
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

    def test_backtest_page_has_shared_view_signals_tab_and_no_view_popovers(self):
        app = self._grouped_positions_app([])

        self.assertEqual(
            [tab.label for tab in app.tabs],
            [
                "Collect Signals",
                "View Signals",
                "Validate Signals",
                "Current Positions",
                "Validate Positions",
            ],
        )
        self.assertEqual(len(app.get("popover")), 0)
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
        self.assertTrue(
            any(item.value == "Validate Positions" for item in validate_positions.title)
        )
        source = inspect.getsource(backtest_lab._render_validate_positions)
        self.assertIn('st.data_editor(', source)
        self.assertIn('"BUY price (k VND)"', source)
        self.assertIn('"Current price (k VND)"', source)
        self.assertIn('"Hold time"', source)
        self.assertIn('"Risk"', source)
        self.assertIn('st.subheader(f"As of:', source)
        self.assertIn('st.button("Run validation"', source)
        self.assertTrue(any("No eligible OPEN positions." == item.value for item in app.info))
        self.assertEqual(app.exception, [])

    def test_collect_places_tickers_above_horizon_range_group_and_action_row(self):
        source = inspect.getsource(backtest_lab._render_collect)

        self.assertIn(
            "collect_row = st.columns((3, 1, 1))",
            source,
        )
        self.assertIn("horizon_column, range_column, action_column = st.columns(3)", source)
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
            item for item in app.text_input if item.key == "backtest_collect_group_tickers_v4"
        )
        self.assertEqual(ticker_box.value, "VCB TCB")
        self.assertTrue(ticker_box.disabled)

    def test_collect_new_group_submits_requested_name_and_manual_tickers(self):
        app = self._collect_group_app()
        group_choices = [item for item in app.selectbox if item.label == "Group"]

        self.assertEqual(len(group_choices), 1)
        group = group_choices[0]
        group.set_value("New group…").run()

        next(item for item in app.text_input if item.label == "New group name").set_value("tech").run()
        next(
            item for item in app.text_input if item.key == "backtest_collect_tickers_v4"
        ).set_value("fpt vcb").run()
        next(item for item in app.button if item.label == "Run Backtest").click().run()

        self.assertEqual(app.session_state["collect_group_config"]["group_name"], "TECH")
        self.assertEqual(app.session_state["collect_group_config"]["tickers"], ("FPT", "VCB"))

    def test_validate_group_locks_resolved_tickers_and_runs_every_member(self):
        app = self._validation_group_app()
        self.assertTrue(
            any(item.label == "Ticker group" and item.value == "-" for item in app.selectbox)
        )
        self.assertTrue(
            any(item.label == "Monitoring classifications" for item in app.multiselect)
        )

        group = next(item for item in app.selectbox if item.label == "Ticker group")
        group.set_value("BANK").run()
        ticker_box = next(
            item for item in app.text_input if item.key == "backtest_validate_group_tickers_v4"
        )
        self.assertEqual(ticker_box.value, "VCB TCB")
        self.assertTrue(ticker_box.disabled)

        next(item for item in app.button if item.label == "Validate").click().run()
        self.assertEqual(app.session_state["validation_calls"], ["VCB", "TCB"])

    def test_validate_classification_filters_latest_success_without_replay(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from pages.backtest_lab import render_backtest_page\n"
            "item = {'availability': 'available', 'horizon': 'swing', 'rulebook_id': 'rule', 'preferred_variant': 'no-background-theme', 'evaluation_label': 'Exploratory — gross', 'monitoring': {'match_level': 10.0, 'match_classification': 'no_match'}, 'buy_block_reason': None, 'audit_eligibility': {}, 'current': {}, 'candidate': {'treatments': {}}}\n"
            "def validate(ticker, *_args):\n"
            "    st.session_state['validate_calls'] = st.session_state.get('validate_calls', 0) + 1\n"
            "    return {'ticker': ticker, 'results': [item], 'historical_positions': []}\n"
            "render_backtest_page(engine=object(), status_dir='unused-status', signal_dir='unused-signals', positions_dir='unused-positions', validate_fn=validate, position_overview_fn=lambda *_args: {'rows': [], 'errors': ()}, rerun_fn=lambda: None)\n"
        ).run()
        next(
            item for item in app.text_input if item.key == "backtest_validate_tickers_v4"
        ).set_value("FPT").run()
        next(item for item in app.button if item.label == "Validate").click().run()
        next(item for item in app.multiselect if item.label == "Monitoring classifications").set_value(["Weak"]).run()

        self.assertEqual(app.session_state["validate_calls"], 1)
        self.assertFalse(any(item.value == "FPT" for item in app.subheader))
        self.assertEqual(
            [item for item in app.expander if item.label != "New Position"], []
        )

    def test_validate_position_action_filter_uses_all_default_and_two_rows(self):
        source = inspect.getsource(backtest_lab._render_validate)

        self.assertIn("POSITION_ACTION_OPTIONS", source)
        self.assertIn('"Position actions"', source)
        self.assertIn("tickers_row = st.columns", source)
        self.assertIn("filters = st.columns", source)
        self.assertLess(
            source.index("tickers_row = st.columns"),
            source.index("filters = st.columns"),
        )
        self.assertLess(
            source.index('"Monitoring classifications"'),
            source.index('"Position actions"'),
        )
        self.assertLess(
            source.index('"Position actions"'), source.index('"Validate"')
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

        self.assertTrue(any(item.label == "Ticker filter" for item in app.text_input))
        self.assertTrue(any(item.label == "Position state" for item in app.multiselect))
        self.assertTrue(any(item.label == "Sort by" for item in app.selectbox))
        self.assertTrue(any(item.label == "Direction" for item in app.selectbox))
        self.assertIn(
            'st.expander("New Position", expanded=False)',
            inspect.getsource(backtest_lab._render_new_position_section),
        )
        self.assertTrue(any(item.label == "↻" for item in app.button))
        self.assertEqual(app.get("data_editor"), [])

        group = next(item for item in app.expander if "FPT" in item.label)
        trade_frame = group.dataframe[0].value
        self.assertEqual(trade_frame["Trade"].tolist(), ["BUY", "SELL"])
        self.assertEqual(trade_frame.loc[0, "Risk Suggestion"], "N/A")
        self.assertEqual(trade_frame.loc[1, "Actual SELL"], "-")
        self.assertTrue(any(button.label == "Edit position" for button in group.button))
        self.assertEqual(app.exception, [])

    def test_new_position_form_uses_requested_field_rows(self):
        source = inspect.getsource(backtest_lab._render_new_position_section)

        self.assertIn("identity_row = st.columns((1, 1, 2))", source)
        self.assertIn("trade_row = st.columns(5)", source)
        self.assertLess(source.index("identity_row"), source.index("trade_row"))
        self.assertLess(source.index("trade_row"), source.index('st.button("Add Position"'))

    def test_new_open_position_sell_date_is_empty(self):
        app = self._grouped_positions_app([])
        sell_date = next(item for item in app.date_input if item.label == "SELL date")

        self.assertIsNone(sell_date.value)

    def test_validation_result_shows_action_and_collapsed_json(self):
        source = inspect.getsource(backtest_lab._render_validation_result)
        self.assertIn("position_action", source)
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
            entry.value == "Monitoring: 100.0% — closely match | can BUY"
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
            item.value == "Validation unavailable: source_history_changed"
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
            button for button in app.button if button.label == "Delete position"
        )
        self.assertTrue(delete.disabled)

        select_all.set_value(True).run()

        self.assertEqual(
            [widget.value for widget in self._position_select_widgets(app)],
            [True, True],
        )
        self.assertFalse(
            next(
                button for button in app.button if button.label == "Delete position"
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
                button for button in app.button if button.label == "Delete position"
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
            button for button in app.button if button.label == "Delete position"
        ).click().run()
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
