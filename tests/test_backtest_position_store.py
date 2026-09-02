"""Schema-5 current and frozen historical position identity contracts."""

from datetime import date
from tempfile import TemporaryDirectory
import unittest

from backtest_engine.config import rulebook_for
from backtest_engine.manual_position_store import build_v5_risk_snapshot, create_manual_position, load_manual_position_history
from backtest_engine.models import RulebookExecution
from backtest_engine.position_identity import (
    validate_position_snapshot,
    validate_v4_position_snapshot,
    validate_v5_position_snapshot,
)


def _eligible_evidence(eligible=True):
    return {
        "status": "eligible" if eligible else "ineligible",
        "eligible": eligible,
        "reasons": [] if eligible else ["coverage_ratio_below_0.95"],
        "common_as_of": "2026-08-20",
        "first_available_bar": "2011-08-22",
        "last_available_bar": "2026-08-20",
        "ticker_fingerprint": "a" * 64,
        "vnindex_fingerprint": "b" * 64,
        "observed_sessions": 3700 if eligible else 3500,
        "expected_sessions": 3700,
        "coverage_ratio": 1.0 if eligible else 3500 / 3700,
        "max_gap_sessions": 0,
    }


def _reference(horizon, gates=("rulebook_adx_gate",)):
    execution = RulebookExecution(rulebook_for(horizon), gates)
    preferred = "no-background-theme"
    candidate = {
        "rulebook_id": execution.rule_id, "candidate_role": "baseline_control", "selected_gates": list(gates), "preferred_variant": preferred,
        "treatments": {
            "no-background-theme": {"theme_variant": preferred, "theme_mode": None, "training": {"n": 5}, "test": {"n": 1}},
            "background-theme": {"theme_variant": "background-theme", "theme_mode": "AND", "training": {"n": 1}, "test": {"n": 0}},
        },
    }
    return {"schema_version": 5, "contract_version": "backtest_schema5_v1", "ticker": "FPT", "horizon": horizon, "rulebook_id": execution.rule_id, "preferred_variant": preferred, "evidence_eligibility": _eligible_evidence(), "exploratory_candidate": candidate}


def _v4_reference(horizon="swing", gates=("rulebook_adx_gate",)):
    suffixes = {
        "rulebook_adx_gate": "adx",
        "rulebook_joint_trend_pass": "joint_trend",
        "rulebook_rsi_upcross": "rsi_upcross",
        "rulebook_volume_gate": "volume",
    }
    rulebook_id = f"{horizon}_rulebook_v4__" + "__".join(suffixes[gate] for gate in gates)
    preferred = "no-background-theme"
    candidate = {
        "rulebook_id": rulebook_id,
        "selected_gates": list(gates),
        "preferred_variant": preferred,
        "treatments": {
            preferred: {"theme_variant": preferred},
            "background-theme": {"theme_variant": "background-theme"},
        },
    }
    return {"schema_version": 4, "ticker": "FPT", "horizon": horizon, "rulebook_id": rulebook_id, "preferred_variant": preferred, "audit_eligible": True, "exploratory_candidate": candidate}


class PositionStoreTests(unittest.TestCase):
    def test_v5_risk_snapshot_uses_the_selected_rulebook(self):
        self.assertEqual(build_v5_risk_snapshot("swing", 2, 100), {"atr": 2, "stop_loss": 97, "take_profit": 105, "max_hold_bars": 22})
        self.assertEqual(build_v5_risk_snapshot("midterm", 2, 100)["max_hold_bars"], 16)

    def test_snapshot_routes_current_writes_to_v5_and_keeps_v4_v3_readable_history(self):
        v5 = _reference("swing")
        self.assertEqual(validate_v5_position_snapshot(v5)["rulebook_id"], "swing_rulebook_v5__adx")
        self.assertEqual(validate_position_snapshot(v5)["schema_version"], 5)
        v4 = _v4_reference()
        self.assertEqual(validate_v4_position_snapshot(v4)["rulebook_id"], "swing_rulebook_v4__adx")
        self.assertEqual(validate_position_snapshot(v4)["schema_version"], 4)
        v3_history = {"schema_version": 3, "ticker": "FPT", "horizon": "swing", "theme_variant": "no-background-theme", "rule_id": "old", "metrics": ["win_rate"], "signal_set": {"old": True}}
        self.assertEqual(validate_position_snapshot(v3_history)["schema_version"], 3)
        with self.assertRaisesRegex(ValueError, "schema_version"):
            validate_position_snapshot({"schema_version": 99})

    def test_v5_positions_can_coexist_by_rulebook_and_reject_historical_references(self):
        with TemporaryDirectory() as directory:
            adx = create_manual_position(
                "FPT", 100, date(2026, 8, 1), signal_reference=_reference("swing"),
                entry_context={"match_level": 0.0, "current_price": 100},
                risk_snapshot={"atr": 2, "stop_loss": 97, "take_profit": 105, "max_hold_bars": 22}, positions_dir=directory,
            )
            rsi = create_manual_position(
                "FPT", 100, date(2026, 8, 1), signal_reference=_reference("swing", ("rulebook_rsi_upcross",)),
                entry_context={"match_level": 0.0, "current_price": 100},
                risk_snapshot={"atr": 2, "stop_loss": 97, "take_profit": 105, "max_hold_bars": 22}, positions_dir=directory,
            )
            with self.assertRaisesRegex(ValueError, "schema_version 5"):
                create_manual_position("FPT", 100, date(2026, 8, 1), signal_reference=_v4_reference(), positions_dir=directory)
            with self.assertRaisesRegex(ValueError, "schema_version 5"):
                create_manual_position("FPT", 100, date(2026, 8, 1), signal_reference={"schema_version": 3}, positions_dir=directory)
            history = load_manual_position_history("FPT", directory)

        self.assertNotEqual(adx["id"], rsi["id"])
        self.assertEqual(len(history["history"]), 2)

    def test_new_signal_backed_position_rejects_evidence_ineligible_reference(self):
        reference = _reference("swing")
        reference["evidence_eligibility"] = _eligible_evidence(False)
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "evidence-ineligible"):
                create_manual_position(
                    "FPT", 100, date(2026, 8, 1), signal_reference=reference,
                    entry_context={"match_level": 0.0, "current_price": 100},
                    risk_snapshot={"atr": 2, "stop_loss": 97, "take_profit": 105, "max_hold_bars": 22},
                    positions_dir=directory,
                )


if __name__ == "__main__":
    unittest.main()
