"""Phase-B risk formulas, routing, and batch contracts."""

from __future__ import annotations

import unittest
import tempfile
from datetime import date
from unittest.mock import patch

import pandas as pd

import backtest_engine.position_risk as position_risk
from backtest_engine.listing_status import ListingStatus
from backtest_engine.position_risk import (
    assess_signal_backed_position,
    elapsed_time_percent,
    assess_no_signal_position,
    risk_label,
    render_risk_suggestion,
    score_signal_risk,
    list_validate_position_candidates,
    validate_open_positions,
)
from backtest_engine.manual_position_store import create_manual_position
from tests.test_backtest_position_store import _reference


class PositionRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        latest = date(2026, 9, 8)

        def listed(tickers, _engine):
            return {
                ticker: ListingStatus(ticker, "listed", latest, latest)
                for ticker in tickers
            }

        self.listing_statuses = patch(
            "backtest_engine.position_risk.load_listing_statuses", side_effect=listed,
        )
        self.listing_statuses.start()
        self.addCleanup(self.listing_statuses.stop)

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
            pd.DataFrame({
                "date": pd.to_datetime(["2026-08-21"]),
                "open": [100], "high": [101], "low": [99],
                "close": [100], "volume": [1_000],
            }),
            pd.Timestamp("2026-08-21").date(),
            pd.DataFrame({
                "date": pd.to_datetime(["2026-08-21"]),
                "open": [100], "high": [101], "low": [99],
                "close": [100], "volume": [1_000],
            }),
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

    def test_signal_backed_t_plus_three_uses_saved_signal_date_before_legacy_as_of(self):
        history = pd.DataFrame({
            "date": pd.to_datetime(["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]),
            "open": [50_000] * 4, "high": [51_000] * 4, "low": [49_000] * 4,
            "close": [50_000] * 4, "volume": [1_000_000] * 4,
        })
        position = {
            "signal_reference": _reference("swing"),
            "entry_context": {
                "match_level": 100.0, "current_price": 50_000,
                "as_of_date": "2026-08-01", "signal_date": "2026-08-02",
            },
            "risk_snapshot": {"atr": 1_000, "stop_loss": 48_500, "take_profit": 52_500, "max_hold_bars": 22},
            "actual_buy_price": 50_000,
            "buy_date": "2026-08-04",
        }
        with patch(
            "backtest_engine.position_risk._calendar_prepare_position_history",
            return_value=(history, pd.Timestamp("2026-08-04").date()),
        ):
            result = assess_signal_backed_position(
                position, history, pd.Timestamp("2026-08-04").date(), history
            )

        self.assertEqual(result, {"availability": "t3_required"})

    def test_vnindex_load_failure_returns_failed_result_instead_of_escaping_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            opened = create_manual_position("FPT", 50_000, "2026-08-01", positions_dir=directory)
            with patch(
                "backtest_engine.position_risk._latest_dates",
                return_value={
                    "FPT": pd.Timestamp("2026-08-21").date(),
                    "VNINDEX": pd.Timestamp("2026-08-21").date(),
                },
            ), patch(
                "backtest_engine.position_risk.load_ticker_history",
                side_effect=OSError("VN-Index database unavailable"),
            ):
                result = validate_open_positions((opened["id"],), object(), directory)

        self.assertEqual("2026-08-21", result["as_of_date"])
        self.assertEqual("Failed — assess failed.", result["results"][0]["result"])

    def test_validation_result_includes_profit_snapshot_at_the_shared_as_of_bar(self):
        """Result P&L must use the same close and date that produced risk advice."""

        as_of = pd.Timestamp("2026-08-21").date()
        history = pd.DataFrame(
            {
                "date": pd.to_datetime([as_of]),
                "open": [51_000], "high": [51_500], "low": [50_500],
                "close": [51_000], "volume": [1_000_000],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            opened = create_manual_position(
                "FPT", 50_000, "2026-08-01", quantity=2, positions_dir=directory
            )
            with patch(
                "backtest_engine.position_risk._latest_dates",
                return_value={"FPT": as_of, "VNINDEX": as_of},
            ), patch(
                "backtest_engine.position_risk.load_ticker_history",
                return_value=history,
            ), patch(
                "backtest_engine.position_risk.assess_no_signal_position",
                return_value={"availability": "available", "scores": {"swing": 25.0}},
            ):
                result = validate_open_positions((opened["id"],), object(), directory)

        row = result["results"][0]
        self.assertEqual(2_000, row["profit_raw"])
        self.assertEqual(2.0, row["profit_pct"])

    def test_position_batches_keep_one_common_asof_and_report_each_five_position_batch(self):
        candidates = tuple(
            {
                "id": f"position-{index}",
                "ticker": f"T{index}",
                "evaluation": "Swing",
                "position": {},
            }
            for index in range(1, 7)
        )
        as_of = pd.Timestamp("2026-09-04").date()
        progress = []

        self.assertTrue(hasattr(position_risk, "validate_open_position_batches"))
        with patch.object(
            position_risk, "list_validate_position_candidates", return_value=candidates,
        ), patch.object(
            position_risk,
            "_latest_dates",
            return_value={
                **{candidate["ticker"]: as_of for candidate in candidates},
                "VNINDEX": as_of,
            },
        ), patch.object(
            position_risk,
            "_assess_selected_positions",
            side_effect=lambda selected, *_args: [
                {"position_id": item["id"], "ticker": item["ticker"]}
                for item in selected
            ],
        ) as assess:
            result = position_risk.validate_open_position_batches(
                tuple(candidate["id"] for candidate in candidates),
                object(),
                "positions",
                progress_fn=lambda completed, total: progress.append((completed, total)),
            )

        self.assertEqual("2026-09-04", result["as_of_date"])
        self.assertEqual(
            [candidate["id"] for candidate in candidates],
            [row["position_id"] for row in result["results"]],
        )
        self.assertEqual([(5, 6), (6, 6)], progress)
        self.assertEqual(
            [("position-1", "position-2", "position-3", "position-4", "position-5"), ("position-6",)],
            [tuple(item["id"] for item in call.args[0]) for call in assess.call_args_list],
        )

    def test_position_batches_skip_delisted_position_and_assess_listed_positions(self):
        candidates = (
            {"id": "fpt-open", "ticker": "FPT", "evaluation": "Swing", "position": {}},
            {"id": "ltg-open", "ticker": "LTG", "evaluation": "Swing", "position": {}},
        )
        as_of = date(2026, 9, 8)
        statuses = {
            "FPT": ListingStatus("FPT", "listed", as_of, as_of),
            "LTG": ListingStatus("LTG", "delisted", date(2026, 6, 19), as_of),
        }
        with patch.object(
            position_risk, "list_validate_position_candidates", return_value=candidates,
        ), patch.object(
            position_risk, "load_listing_statuses", return_value=statuses, create=True,
        ), patch.object(
            position_risk, "_latest_dates", return_value={"FPT": as_of, "VNINDEX": as_of},
        ), patch.object(
            position_risk, "_assess_selected_positions", return_value=[
                {"position_id": "fpt-open", "ticker": "FPT", "result": "Updated"}
            ],
        ) as assess:
            result = position_risk.validate_open_position_batches(
                ("fpt-open", "ltg-open"), object(), "positions",
            )

        self.assertEqual("2026-09-08", result["as_of_date"])
        self.assertEqual(["fpt-open", "ltg-open"], [row["position_id"] for row in result["results"]])
        self.assertEqual("Unavailable — ticker delisted.", result["results"][1]["result"])
        self.assertEqual(("fpt-open",), tuple(item["id"] for item in assess.call_args.args[0]))


if __name__ == "__main__":
    unittest.main()
