"""Schema-4 catalog contracts for Top-3 exploratory rulebooks."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backtest_engine.config import rulebook_for
from backtest_engine.models import RulebookExecution
from backtest_engine.persistence import save_rulebook_result
from backtest_engine.signal_catalog import (
    list_current_signal_set_rows,
    list_saved_signal_options,
    tickers_with_no_saved_signal,
)


def _metrics(n=5, win_rate=60.0, profit_pct=3.0, sharpe=0.4):
    return {"n": n, "win_rate": win_rate, "profit_pct": profit_pct, "sharpe": sharpe if n >= 2 else None, "p_value": None, "p_value_status": "not_estimated_n_le_block_size"}


def _candidate(gates, win_rate=60.0):
    rulebook = rulebook_for("swing")
    execution = RulebookExecution(rulebook, gates)
    return {
        "rulebook_id": execution.rule_id,
        "selected_gates": list(gates),
        "preferred_variant": "no-background-theme",
        "treatments": {
            "no-background-theme": {"theme_variant": "no-background-theme", "theme_mode": None, "training": _metrics(win_rate=win_rate), "test": _metrics(n=1), "training_dsr": None, "dsr_status": "unavailable"},
            "background-theme": {"theme_variant": "background-theme", "theme_mode": "AND", "training": _metrics(n=1), "test": _metrics(n=0), "training_dsr": None, "dsr_status": "unavailable"},
        },
    }


def _success_document():
    candidates = [
        _candidate(("rulebook_adx_gate",), 62.0),
        _candidate(("rulebook_rsi_upcross",), 61.0),
        _candidate(("rulebook_volume_gate",), 60.0),
        _candidate(("rulebook_joint_trend_pass",), 59.0),
    ]
    return {
        "horizon": "swing", "terminal_state": "success", "empty": False,
        "failure_reason": None, "rejection_reason": None,
        "evaluation_label": "Exploratory — gross", "rulebook": rulebook_for("swing").to_dict(),
        "audit_eligibility": {"source": "fresh_v3_raw_history", "eligible": True, "status": "clean", "reasons": [], "warnings": [], "effective_date_range": ["2011-01-03", "2026-01-02"]},
        "requested_date_range": {"start": "2011-01-03", "end": "2026-01-02", "reason": None},
        "effective_data_range": {"start": "2011-01-03", "end": "2026-01-02", "reason": None},
        "split": {"method": "calendar_10y_5y", "train": {"start": "2011-01-03", "end": "2021-01-01"}, "test": {"start": "2021-01-04", "end": "2026-01-02"}},
        "candidates": candidates,
        "top_rulebook_ids": [item["rulebook_id"] for item in candidates[:3]],
    }


class SignalCatalogTests(unittest.TestCase):
    def test_v2_is_ignored_by_current_catalog_and_discovery_without_warnings(self):
        with TemporaryDirectory() as directory:
            legacy = Path(directory) / "VCB" / "VCB_signals_no-background-theme.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
            catalog = list_current_signal_set_rows(directory)
            self.assertEqual(catalog["valid"], [])
            self.assertEqual(catalog["invalid"], [])
            self.assertEqual(tickers_with_no_saved_signal(("VCB",), directory), ("VCB",))

    def test_catalog_exposes_exactly_top_three_preferred_rulebooks_with_both_treatments(self):
        with TemporaryDirectory() as directory:
            save_rulebook_result("VCB", _success_document(), directory)
            catalog = list_current_signal_set_rows(directory)
            options = list_saved_signal_options("VCB", directory)

        self.assertEqual([row["Rulebook"] for row in catalog["valid"]], [
            "swing_rulebook_v4__adx", "swing_rulebook_v4__rsi_upcross", "swing_rulebook_v4__volume",
        ])
        self.assertTrue(all(row["Evaluation"] == "Exploratory — gross" for row in catalog["valid"]))
        self.assertTrue(all(set(row["Treatments"]) == {"no-background-theme", "background-theme"} for row in catalog["valid"]))
        self.assertEqual(len(options), 3)


if __name__ == "__main__":
    unittest.main()
