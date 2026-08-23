"""Strict schema-4 aggregate artifact contracts."""

from datetime import date
from tempfile import TemporaryDirectory
import unittest

from backtest_engine.config import rulebook_for
from backtest_engine.models import RulebookExecution
from backtest_engine.persistence import (
    load_rulebook_result,
    save_rulebook_result,
    signal_artifact_path,
    validate_rulebook_document,
)


def _range(start="2011-01-03", end="2026-01-02"):
    return {"start": start, "end": end, "reason": None}


def _audit():
    return {
        "source": "fresh_v3_raw_history",
        "eligible": True,
        "status": "clean",
        "reasons": [],
        "warnings": [],
        "effective_date_range": ["2011-01-03", "2026-01-02"],
    }


def _metrics(n=5, win_rate=60.0, profit_pct=3.5, sharpe=0.4):
    return {
        "n": n,
        "win_rate": win_rate,
        "profit_pct": profit_pct,
        "sharpe": sharpe if n >= 2 else None,
        "p_value": None if n <= 20 else 0.03,
        "p_value_status": "not_estimated_n_le_block_size" if n <= 20 else "informational",
    }


def _candidate(gates=("rulebook_adx_gate",), preferred="no-background-theme"):
    rulebook = rulebook_for("swing")
    no_theme = RulebookExecution(rulebook, gates)
    themed = RulebookExecution(rulebook, gates, "background-theme", "AND")
    return {
        "rulebook_id": no_theme.rule_id,
        "selected_gates": list(gates),
        "preferred_variant": preferred,
        "treatments": {
            "no-background-theme": {
                "theme_variant": "no-background-theme",
                "theme_mode": None,
                "training": _metrics(),
                "test": _metrics(n=1, win_rate=100.0, profit_pct=1.0),
                "training_dsr": None,
                "dsr_status": "unavailable",
            },
            "background-theme": {
                "theme_variant": "background-theme",
                "theme_mode": "AND",
                "training": _metrics(n=1, win_rate=100.0, profit_pct=1.0),
                "test": _metrics(n=0, win_rate=0.0, profit_pct=0.0),
                "training_dsr": None,
                "dsr_status": "unavailable",
            },
        },
    }


def _success_document():
    candidate = _candidate()
    return {
        "horizon": "swing",
        "terminal_state": "success",
        "empty": False,
        "failure_reason": None,
        "rejection_reason": None,
        "evaluation_label": "Exploratory — gross",
        "rulebook": rulebook_for("swing").to_dict(),
        "audit_eligibility": _audit(),
        "requested_date_range": _range(),
        "effective_data_range": _range(),
        "split": {
            "method": "calendar_10y_5y",
            "train": {"start": "2011-01-03", "end": "2021-01-01"},
            "test": {"start": "2021-01-04", "end": "2026-01-02"},
        },
        "candidates": [candidate],
        "top_rulebook_ids": [candidate["rulebook_id"]],
    }


class Schema4PersistenceTests(unittest.TestCase):
    def test_success_round_trips_one_ticker_horizon_aggregate(self):
        with TemporaryDirectory() as directory:
            path = save_rulebook_result("VCB", _success_document(), directory)
            result = load_rulebook_result(path)

            self.assertEqual(signal_artifact_path("VCB", "swing", directory).name, "VCB_signals_swing.json")
            self.assertEqual(result["schema_version"], 4)
            self.assertEqual(result["ticker"], "VCB")
            self.assertEqual(result["top_rulebook_ids"], ["swing_rulebook_v4__adx"])

    def test_success_rejects_top_id_not_ranked_candidate(self):
        payload = _success_document()
        payload["top_rulebook_ids"] = ["missing_rulebook"]

        with self.assertRaisesRegex(ValueError, "top_rulebook_ids"):
            validate_rulebook_document({**payload, "schema_version": 4, "ticker": "VCB", "evaluated_at": "2026-08-22T00:00:00+07:00"})

    def test_success_rejects_non_candidate_n_and_degenerate_p_value(self):
        payload = _success_document()
        payload["candidates"][0]["treatments"]["no-background-theme"]["training"]["n"] = 4
        with self.assertRaisesRegex(ValueError, "minimum"):
            validate_rulebook_document({**payload, "schema_version": 4, "ticker": "VCB", "evaluated_at": "2026-08-22T00:00:00+07:00"})

        payload = _success_document()
        training = payload["candidates"][0]["treatments"]["no-background-theme"]["training"]
        training["p_value"] = 0.01
        with self.assertRaisesRegex(ValueError, "p_value"):
            validate_rulebook_document({**payload, "schema_version": 4, "ticker": "VCB", "evaluated_at": "2026-08-22T00:00:00+07:00"})

    def test_success_accepts_informational_p_value_above_block_size(self):
        payload = _success_document()
        payload["candidates"][0]["treatments"]["no-background-theme"]["training"] = _metrics(
            n=21, win_rate=61.0, profit_pct=4.0, sharpe=0.5
        )

        self.assertTrue(validate_rulebook_document({
            **payload, "schema_version": 4, "ticker": "VCB",
            "evaluated_at": "2026-08-22T00:00:00+07:00",
        }))


if __name__ == "__main__":
    unittest.main()
