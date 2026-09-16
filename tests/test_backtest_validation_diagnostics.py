"""Read-only calendar, entry-event, and direction trace contracts."""

from datetime import date
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from backtest_engine.models import RulebookExecution
from backtest_engine.config import rulebook_for
from backtest_engine.validation_diagnostics import (
    diagnose_candidate,
    audit_saved_candidates,
    summarize_entry_events,
    trajectory_facts,
)
from backtest_engine.persistence import save_rulebook_result
from tests.test_backtest_signal_catalog import _success_document


def _history(periods: int = 60) -> pd.DataFrame:
    dates = pd.bdate_range("2026-06-01", periods=periods)
    close = pd.Series(range(100_000, 100_000 + periods), dtype="int64")
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close + 100,
        "low": close - 100,
        "close": close,
        "volume": 1_000_000,
    })


class ValidationDiagnosticTests(unittest.TestCase):
    def test_entry_summary_never_turns_an_unknown_warmup_level_into_a_signal(self):
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]),
            "rulebook_missing_required_input": [True, False, False, False],
        })

        summary = summarize_entry_events(
            frame,
            pd.Series([True, True, False, True]),
        )

        self.assertEqual(1, summary["observed_event_count"])
        self.assertEqual("2026-08-06", summary["latest_event_date"])
        self.assertEqual(0, summary["age_native_bars"])

    def test_trajectory_requires_price_direction_and_trend_not_adx_slope_alone(self):
        frame = pd.DataFrame({
            "close": [100, 99, 98, 97],
            "rulebook_joint_trend_pass": [True, True, False, False],
            "rulebook_rsi": [60.0, 55.0, 50.0, 45.0],
            "rulebook_adx_14": [28.0, 25.0, 20.0, 16.0],
        })

        facts = trajectory_facts(
            frame,
            ("rulebook_joint_trend_pass", "rulebook_rsi_upcross", "rulebook_adx_gate"),
            "swing",
        )

        self.assertTrue(facts["close_declines_three_bars"])
        self.assertTrue(facts["joint_trend_fails"])
        self.assertTrue(facts["rsi_below_entry_level"])
        self.assertTrue(facts["adx_below_minimum_and_falling"])
        self.assertTrue(facts["trajectory_a"])
        self.assertTrue(facts["trajectory_b"])
        self.assertTrue(facts["trajectory_c"])

    def test_candidate_trace_filters_non_session_row_before_indicator_frame(self):
        ticker = _history()
        vnindex = ticker.drop(index=[20]).reset_index(drop=True)
        execution = RulebookExecution(rulebook_for("swing"), ("rulebook_joint_trend_pass",))
        candidate = {
            "rulebook_id": execution.rule_id,
            "selected_gates": list(execution.selected_gates),
            "preferred_variant": "no-background-theme",
        }

        trace = diagnose_candidate(
            "TCX",
            horizon="swing",
            candidate=candidate,
            ticker_raw=ticker,
            vnindex_raw=vnindex,
            requested_end=date(2026, 8, 21),
        )

        self.assertEqual(59, trace["native_bar_count"])
        self.assertEqual(
            [ticker["date"].iloc[20].date().isoformat()],
            trace["calendar"]["excluded_ticker_dates"],
        )
        self.assertEqual("TCX", trace["ticker"])
        self.assertEqual("swing", trace["horizon"])

    def test_all_top_candidates_reuse_one_ticker_and_one_vnindex_load(self):
        raw = _history()
        with TemporaryDirectory() as directory:
            save_rulebook_result("TCX", _success_document(), directory)
            with patch(
                "backtest_engine.validation_diagnostics.load_ticker_history",
                return_value=raw,
            ) as loader:
                audit_saved_candidates(
                    object(),
                    signal_dir=directory,
                    as_of=raw["date"].iloc[-1].date(),
                )

        self.assertEqual(2, loader.call_count)


if __name__ == "__main__":
    unittest.main()
