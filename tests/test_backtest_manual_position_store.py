"""Generic manual history preserves P&L records and new V5 exploratory links."""

import tempfile
import unittest

from backtest_engine.manual_position_store import (
    close_manual_position,
    create_manual_position,
    load_manual_position_history,
    update_manual_position_risk_suggestion,
    update_manual_position,
)
from tests.test_backtest_position_store import _reference


def _entry_context():
    return {"match_level": 100.0, "current_price": 50300, "as_of_date": "2026-08-12"}


def _risk_snapshot():
    return {"atr": 1200, "stop_loss": 48500, "take_profit": 53300, "max_hold_bars": 22}


def _flexible_reference():
    return {
        "schema_version": 6,
        "contract_version": "flexible_rulebook_signal_v1",
        "origin": "flexible",
        "ticker": "FPT",
        "horizon": "swing",
        "rulebook_id": "frb2_" + "a" * 64,
        "semantic_digest": "a" * 64,
        "evaluation_id": "frev2_" + "b" * 64,
        "evaluation_label": "Exploratory — gross",
        "metrics": {
            "training": {"n": 12, "win_rate": 60.0, "profit_pct": 14.0, "sharpe": 1.0},
            "test": {"n": 7, "win_rate": 55.0, "profit_pct": 9.0, "sharpe": 0.5},
        },
    }


class ManualPositionStoreTests(unittest.TestCase):
    def test_creates_open_and_closed_pnl_only_records(self):
        with tempfile.TemporaryDirectory() as directory:
            opened = create_manual_position("FPT", 50300, "2026-08-08", positions_dir=directory)
            closed = create_manual_position("FPT", 50000, "2026-08-02", actual_sell_price=52000, sell_date="2026-08-10", quantity=100, positions_dir=directory)
            history = load_manual_position_history("FPT", directory)
        self.assertEqual((opened["status"], closed["status"], len(history["history"])), ("open", "closed", 2))

    def test_v5_open_reference_prevents_only_its_exact_rulebook_overlap(self):
        reference = _reference("swing")
        with tempfile.TemporaryDirectory() as directory:
            record = create_manual_position("FPT", 50300, "2026-08-07", signal_reference=reference, entry_context=_entry_context(), risk_snapshot=_risk_snapshot(), positions_dir=directory)
            with self.assertRaisesRegex(ValueError, "already has an OPEN position"):
                create_manual_position("FPT", 50400, "2026-08-08", signal_reference=reference, entry_context=_entry_context(), risk_snapshot=_risk_snapshot(), positions_dir=directory)
        self.assertEqual(record["signal_reference"]["schema_version"], 5)

    def test_flexible_open_reference_preserves_full_immutable_ids_and_blocks_overlap(self):
        reference = _flexible_reference()
        with tempfile.TemporaryDirectory() as directory:
            record = create_manual_position(
                "FPT", 50300, "2026-08-07", signal_reference=reference,
                entry_context=_entry_context(), risk_snapshot=_risk_snapshot(), positions_dir=directory,
            )
            with self.assertRaisesRegex(ValueError, "already has an OPEN position"):
                create_manual_position(
                    "FPT", 50400, "2026-08-08", signal_reference=reference,
                    entry_context=_entry_context(), risk_snapshot=_risk_snapshot(), positions_dir=directory,
                )
        self.assertEqual(6, record["signal_reference"]["schema_version"])
        self.assertEqual("flexible", record["signal_reference"]["origin"])
        self.assertEqual(reference["rulebook_id"], record["signal_reference"]["rulebook_id"])

    def test_flexible_reference_can_preserve_pnl_without_a_baseline_risk_snapshot(self):
        """Flexible rules must not inherit unrelated baseline exit settings."""

        with tempfile.TemporaryDirectory() as directory:
            record = create_manual_position(
                "FPT", 50300, "2026-08-07", signal_reference=_flexible_reference(),
                entry_context=_entry_context(), risk_snapshot=None, positions_dir=directory,
            )

        self.assertEqual(6, record["signal_reference"]["schema_version"])
        self.assertIsNone(record["risk_snapshot"])

    def test_update_recalculates_risk_and_close_writes_same_record(self):
        with tempfile.TemporaryDirectory() as directory:
            opened = create_manual_position("FPT", 50300, "2026-08-07", signal_reference=_reference("swing"), entry_context=_entry_context(), risk_snapshot=_risk_snapshot(), positions_dir=directory)
            updated = update_manual_position("FPT", opened["id"], {"actual_buy_price": 51500, "quantity": 100}, directory)
            closed = close_manual_position("FPT", opened["id"], 53000, "2026-08-10", directory)
        self.assertEqual(updated["risk_snapshot"]["stop_loss"], 49700)
        self.assertEqual((closed["id"], closed["status"]), (opened["id"], "closed"))

    def test_risk_text_overwrites_and_buy_changes_clear_while_close_preserves(self):
        with tempfile.TemporaryDirectory() as directory:
            opened = create_manual_position("FPT", 50300, "2026-08-07", positions_dir=directory)
            assessed = update_manual_position_risk_suggestion(
                "FPT", opened["id"], "Swing: 42.00% - medium", directory
            )
            quantity_only = update_manual_position(
                "FPT", opened["id"], {"quantity": 100}, directory
            )
            cleared = update_manual_position(
                "FPT", opened["id"], {"actual_buy_price": 51500}, directory
            )
            update_manual_position_risk_suggestion("FPT", opened["id"], "Unavailable", directory)
            closed = close_manual_position("FPT", opened["id"], 53000, "2026-08-10", directory)

        self.assertEqual(assessed["risk_suggestion_text"], "Swing: 42.00% - medium")
        self.assertEqual(quantity_only["risk_suggestion_text"], "Swing: 42.00% - medium")
        self.assertNotIn("risk_suggestion_text", cleared)
        self.assertEqual(closed["risk_suggestion_text"], "Unavailable")


if __name__ == "__main__":
    unittest.main()
