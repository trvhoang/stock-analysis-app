"""Phase-B risk formulas, routing, and batch contracts."""

from __future__ import annotations

import unittest
import tempfile
from unittest.mock import patch

import pandas as pd

from backtest_engine.position_risk import (
    elapsed_time_percent,
    assess_no_signal_position,
    risk_label,
    render_risk_suggestion,
    score_signal_risk,
    list_validate_position_candidates,
)
from backtest_engine.manual_position_store import create_manual_position
from tests.test_backtest_position_store import _reference


class PositionRiskTests(unittest.TestCase):
    def test_labels_use_exact_inclusive_boundaries_and_render_two_horizons(self):
        self.assertEqual(risk_label(40.0), "low")
        self.assertEqual(risk_label(40.01), "medium")
        self.assertEqual(risk_label(60.0), "medium")
        self.assertEqual(risk_label(60.01), "high")
        self.assertEqual(risk_label(80.0), "high")
        self.assertEqual(risk_label(80.01), "very")
        self.assertEqual(
            render_risk_suggestion({"swing": 25.0, "midterm": 75.0}),
            "Swing: 25.0% - low\nMid-term: 75.0% - high",
        )
        self.assertEqual(
            render_risk_suggestion({"swing": 40.04}),
            "Swing: 40.0% - medium",
        )

    def test_signal_score_uses_raw_stop_atr_holding_and_t_plus_three_clocks(self):
        self.assertEqual(
            score_signal_risk(
                entry_price=100_000,
                stop_loss=80_000,
                latest_close=80_000,
                latest_atr=4_000,
                holding_bars=3,
                max_hold_bars=22,
                strength_drop=0.0,
                elapsed_time=elapsed_time_percent("swing", 3),
            ),
            100.0,
        )
        self.assertEqual(elapsed_time_percent("swing", 3), 13.64)
        self.assertEqual(elapsed_time_percent("midterm", 3), 3.75)
        self.assertEqual(
            score_signal_risk(
                entry_price=100_000,
                stop_loss=80_000,
                latest_close=100_000,
                latest_atr=4_000,
                holding_bars=3,
                max_hold_bars=22,
                strength_drop=0.0,
                elapsed_time=elapsed_time_percent("swing", 3),
            ),
            11.82,
        )

    @patch("backtest_engine.position_risk.build_rulebook_frame")
    def test_no_signal_assessment_counts_all_four_current_no_theme_gates(self, build_frame):
        build_frame.side_effect = [
            pd.DataFrame(
                [{
                    "rulebook_adx_gate": True,
                    "rulebook_joint_trend_pass": True,
                    "rulebook_rsi_upcross": True,
                    "rulebook_volume_gate": False,
                }]
            ),
            pd.DataFrame(
                [{
                    "rulebook_adx_gate": True,
                    "rulebook_joint_trend_pass": False,
                    "rulebook_rsi_upcross": False,
                    "rulebook_volume_gate": False,
                }]
            ),
        ]

        result = assess_no_signal_position(
            pd.DataFrame({"date": pd.to_datetime(["2026-08-21"])}),
            pd.Timestamp("2026-08-21").date(),
        )

        self.assertEqual(result, {"availability": "available", "scores": {"swing": 25.0, "midterm": 75.0}})

    def test_candidates_include_only_open_manual_pnl_positions(self):
        with tempfile.TemporaryDirectory() as directory:
            opened = create_manual_position("FPT", 50_000, "2026-08-01", positions_dir=directory)
            create_manual_position("FPT", 50_000, "2026-08-01", actual_sell_price=51_000, sell_date="2026-08-02", positions_dir=directory)
            candidates = list_validate_position_candidates(directory)

        self.assertEqual([candidate["id"] for candidate in candidates], [opened["id"]])
        self.assertEqual(candidates[0]["evaluation"], "Swing + Mid-term")

    def test_candidates_include_current_v5_signal_position(self):
        with tempfile.TemporaryDirectory() as directory:
            opened = create_manual_position(
                "FPT",
                50_000,
                "2026-08-01",
                signal_reference=_reference("swing"),
                entry_context={"match_level": 100.0, "current_price": 50_000, "as_of_date": "2026-08-01"},
                risk_snapshot={"atr": 1_000, "stop_loss": 48_500, "take_profit": 52_500, "max_hold_bars": 22},
                positions_dir=directory,
            )
            candidates = list_validate_position_candidates(directory)

        self.assertEqual([candidate["id"] for candidate in candidates], [opened["id"]])
        self.assertEqual(candidates[0]["evaluation"], "Swing")


if __name__ == "__main__":
    unittest.main()
