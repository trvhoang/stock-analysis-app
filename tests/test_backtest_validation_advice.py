"""Top-3 replay, selected-gate monitoring, and audit safety contracts."""

import unittest
from unittest.mock import patch

from backtest_engine.config import rulebook_for
from backtest_engine import validation_advice
from backtest_engine.validation_advice import monitoring_match_level, validate_saved_signals


class ValidationAdviceTests(unittest.TestCase):
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
            "can SELL",
        )
        self.assertEqual(
            position_action(
                {"literal_entry": True, "latest_close": 50000},
                position,
                False,
            ),
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

    def test_validate_replays_preferred_top_candidate_and_blocks_audit_ineligible_buy(self):
        candidate = {"rulebook_id": "swing_rulebook_v4__adx", "selected_gates": ["rulebook_adx_gate"], "preferred_variant": "background-theme", "treatments": {}}
        replay = {
            "candidate": candidate, "preferred_variant": "background-theme",
            "current": {"literal_entry": True, "gate_facts": {"rulebook_adx_gate": True}, "theme_eligible": True},
            "audit_eligibility": {"eligible": False},
        }
        document = {"terminal_state": "success", "top_rulebook_ids": [candidate["rulebook_id"]]}
        with patch("backtest_engine.validation_advice.load_current_rulebook_document", return_value=document), patch(
            "backtest_engine.validation_advice.check_current_situation", return_value=replay
        ), patch("backtest_engine.validation_advice.load_manual_position_history", return_value={"history": []}):
            result = validate_saved_signals("VCB", object())

        item = result["results"][0]
        self.assertEqual(item["preferred_variant"], "background-theme")
        self.assertFalse(item["buy_eligible"])
        self.assertEqual(item["buy_block_reason"], "audit_ineligible")


if __name__ == "__main__":
    unittest.main()
