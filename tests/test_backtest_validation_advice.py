"""Top-3 replay, selected-gate monitoring, and audit safety contracts."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from backtest_engine.config import rulebook_for
from backtest_engine import validation_advice
from backtest_engine.listing_status import ListingStatus
from backtest_engine.validation_advice import monitoring_match_level, validate_saved_signals


class ValidationAdviceTests(unittest.TestCase):
    def setUp(self) -> None:
        listed = ListingStatus("VCB", "listed", date(2026, 9, 8), date(2026, 9, 8))
        self.listing_statuses = patch(
            "backtest_engine.validation_advice.load_listing_statuses",
            return_value={"VCB": listed},
        )
        self.listing_statuses.start()
        self.addCleanup(self.listing_statuses.stop)

    def test_validate_delisted_ticker_is_unavailable_without_replay(self):
        delisted = ListingStatus(
            "LTG", "delisted", date(2026, 6, 19), date(2026, 9, 8),
        )
        with patch(
            "backtest_engine.validation_advice.load_listing_statuses",
            return_value={"LTG": delisted}, create=True,
        ), patch(
            "backtest_engine.validation_advice.load_manual_position_history",
            return_value={"history": []},
        ), patch(
            "backtest_engine.validation_advice.load_current_rulebook_document",
        ) as document:
            result = validate_saved_signals("LTG", object())

        self.assertEqual(
            [{"availability": "unavailable", "reason": delisted.reason}],
            result["results"],
        )
        document.assert_not_called()

    def test_position_action_maps_buy_expiry_sell_and_hold(self):
        position_action = getattr(validation_advice, "_position_action", None)
        position = {
            "risk_snapshot": {"stop_loss": 48000, "take_profit": 54000}
        }

        self.assertTrue(callable(position_action))
        self.assertEqual(
            position_action({"literal_entry": True}, None, True), "can BUY"
        )
        self.assertEqual(
            position_action({"literal_entry": False}, None, False),
            "expired BUY",
        )
        self.assertEqual(
            position_action(
                {"literal_entry": False, "latest_close": 50000},
                position,
                False,
            ),
            "HOLD",
        )
        self.assertEqual(
            position_action(
                {"literal_entry": True, "latest_close": 50000},
                position,
                False,
            ),
            "HOLD",
        )

    def test_position_action_uses_explicit_exit_or_deterioration_not_consumed_entry(self):
        position_action = getattr(validation_advice, "_position_action", None)
        position = {"risk_snapshot": {"stop_loss": 48000, "take_profit": 54000}}

        self.assertEqual(
            position_action(
                {"literal_entry": False, "technical_exit": True, "latest_close": 50000},
                position,
                False,
            ),
            "can SELL",
        )
        self.assertEqual(
            position_action(
                {"literal_entry": False, "deteriorated": True, "latest_close": 50000},
                position,
                False,
            ),
            "can SELL",
        )
        self.assertEqual(
            position_action({"latest_close": 50000}, {"risk_snapshot": None}, False),
            "HOLD",
        )

    def test_position_action_sells_at_frozen_stop_or_take_profit(self):
        position_action = getattr(validation_advice, "_position_action", None)
        position = {
            "risk_snapshot": {"stop_loss": 48000, "take_profit": 54000}
        }

        self.assertTrue(callable(position_action))
        self.assertEqual(
            position_action(
                {"literal_entry": True, "latest_close": 48000},
                position,
                False,
            ),
            "can SELL",
        )
        self.assertEqual(
            position_action(
                {"literal_entry": True, "latest_close": 54000},
                position,
                False,
            ),
            "can SELL",
        )

    def test_monitoring_uses_only_selected_boolean_gates_and_equal_theme_factor(self):
        current = {"gate_facts": {"rulebook_adx_gate": True, "rulebook_rsi_upcross": False}, "theme_eligible": True}
        self.assertEqual(
            monitoring_match_level("swing", ("rulebook_adx_gate", "rulebook_rsi_upcross"), "no-background-theme", current, rulebook_for("swing")),
            (50.0, "nearly_match"),
        )
        self.assertEqual(
            monitoring_match_level("swing", ("rulebook_adx_gate", "rulebook_rsi_upcross"), "background-theme", current, rulebook_for("swing")),
            (66.67, "nearly_match"),
        )

    def test_validate_replays_preferred_top_candidate_and_blocks_evidence_ineligible_buy(self):
        candidate = {
            "rulebook_id": "swing_rulebook_v5__adx", "candidate_role": "baseline_control",
            "selected_gates": ["rulebook_adx_gate"], "preferred_variant": "background-theme",
            "treatments": {
                "background-theme": {
                    "training": {"win_rate": 62.5}, "test": {"win_rate": 55.0},
                },
            },
        }
        replay = {
            "candidate": candidate, "preferred_variant": "background-theme",
            "current": {
                "literal_entry": True, "gate_facts": {"rulebook_adx_gate": True},
                "theme_eligible": True, "signal_date": "2026-08-14",
            },
            "audit_eligibility": {"eligible": True},
            "evidence_eligibility": {"eligible": False, "status": "ineligible", "reasons": ["coverage_ratio_below_0.95"]},
        }
        document = {"terminal_state": "success", "top_rulebook_ids": [candidate["rulebook_id"]]}
        with patch("backtest_engine.validation_advice.load_current_rulebook_document", return_value=document), patch(
            "backtest_engine.validation_advice.check_current_situation", return_value=replay
        ), patch("backtest_engine.validation_advice.load_manual_position_history", return_value={"history": []}):
            result = validate_saved_signals("VCB", object())

        item = result["results"][0]
        self.assertEqual(item["preferred_variant"], "background-theme")
        self.assertFalse(item["buy_eligible"])
        self.assertEqual(item["buy_block_reason"], "evidence_ineligible")
        self.assertEqual(item["signal_reference"]["schema_version"], 5)
        self.assertEqual(item["signal_date"], "2026-08-14")
        self.assertEqual(
            item["win_rate"], {"training": 62.5, "test": 55.0}
        )

    def test_ongoing_signal_state_keeps_buy_eligible_after_event_gate_is_consumed(self):
        candidate = {
            "rulebook_id": "swing_rulebook_v5__rsi_upcross",
            "candidate_role": "baseline_control",
            "selected_gates": ["rulebook_rsi_upcross"],
            "preferred_variant": "no-background-theme",
            "treatments": {},
        }
        replay = {
            "candidate": candidate,
            "preferred_variant": "no-background-theme",
            "current": {
                "literal_entry": False,
                "signal_state": {"state": "ongoing", "reasons": []},
                "gate_facts": {"rulebook_rsi_upcross": False},
            },
            "audit_eligibility": {"eligible": True},
            "evidence_eligibility": {"eligible": True, "status": "eligible", "reasons": []},
        }
        document = {"terminal_state": "success", "top_rulebook_ids": [candidate["rulebook_id"]]}
        with patch("backtest_engine.validation_advice.load_current_rulebook_document", return_value=document), patch(
            "backtest_engine.validation_advice.check_current_situation", return_value=replay
        ), patch("backtest_engine.validation_advice.load_manual_position_history", return_value={"history": []}):
            result = validate_saved_signals("VCB", object())

        item = result["results"][0]
        self.assertTrue(item["buy_eligible"])
        self.assertEqual(item["position_action"], "can BUY")
        self.assertEqual(item["signal_state"]["state"], "ongoing")

    def test_manual_and_schema_four_positions_do_not_consume_current_v5_identity(self):
        candidate = {"rulebook_id": "swing_rulebook_v5__adx", "candidate_role": "baseline_control", "selected_gates": ["rulebook_adx_gate"], "preferred_variant": "no-background-theme", "treatments": {}}
        replay = {
            "candidate": candidate,
            "preferred_variant": "no-background-theme",
            "current": {"literal_entry": True, "gate_facts": {"rulebook_adx_gate": True}},
            "audit_eligibility": {"eligible": True},
            "evidence_eligibility": {"eligible": True, "status": "eligible", "reasons": []},
        }
        document = {"terminal_state": "success", "top_rulebook_ids": [candidate["rulebook_id"]]}
        history = {"history": [
            {"status": "open", "signal_reference": None},
            {"status": "open", "signal_reference": {"schema_version": 4, "horizon": "swing", "rulebook_id": "swing_rulebook_v4__adx", "preferred_variant": "no-background-theme"}},
        ]}
        with patch("backtest_engine.validation_advice.load_current_rulebook_document", return_value=document), patch(
            "backtest_engine.validation_advice.check_current_situation", return_value=replay
        ), patch("backtest_engine.validation_advice.load_manual_position_history", return_value=history):
            result = validate_saved_signals("VCB", object())

        item = result["results"][0]
        self.assertTrue(item["buy_eligible"])
        self.assertEqual(item["position_action"], "can BUY")
        self.assertEqual(len(result["historical_positions"]), 2)

    def test_validate_projects_flexible_artifact_with_the_three_shared_classes(self):
        artifact = {
            "ticker": "VCB",
            "horizon": "swing",
            "rulebook_id": "frb2_" + "a" * 64,
            "semantic_digest": "a" * 64,
            "evaluation_label": "Exploratory — gross",
            "evaluation_reference": {"evaluation_id": "frev2_" + "b" * 64},
            "evaluation": {
                "metrics": {
                    "training": {"n": 12, "win_rate": 60.0, "total_return_pct": 14.0, "sharpe": 1.0},
                    "test": {"n": 7, "win_rate": 55.0, "total_return_pct": 9.0, "sharpe": 0.5},
                },
            },
        }
        inspection = SimpleNamespace(
            support_percentage=100.0,
            signal_state="Fresh",
            signal_date=date(2026, 9, 8),
            as_of_date=date(2026, 9, 8),
            latest_close=50_000.0,
            latest_atr=1_000.0,
            has_prior_event=True,
            live_entry_support=True,
            all_gates_support=True,
            technical_exit=False,
            age_native_bars=0,
        )
        with patch(
            "backtest_engine.validation_advice._flexible_artifacts_for_ticker",
            return_value=(artifact,),
            create=True,
        ), patch(
            "backtest_engine.validation_advice.replay_flexible_signal_artifact",
            return_value={"artifact": artifact, "inspection": inspection},
            create=True,
        ), patch(
            "backtest_engine.validation_advice.load_manual_position_history",
            return_value={"history": []},
        ), patch(
            "backtest_engine.validation_advice.load_current_rulebook_document",
            return_value=None,
        ):
            result = validate_saved_signals("VCB", object())

        item = result["results"][0]
        self.assertEqual("closely_match", item["monitoring"]["match_classification"])
        self.assertEqual("can BUY", item["position_action"])
        self.assertEqual("flexible", item["signal_reference"]["origin"])
        self.assertEqual(6, item["signal_reference"]["schema_version"])
        self.assertEqual({"training": 60.0, "test": 55.0}, item["win_rate"])


if __name__ == "__main__":
    unittest.main()
