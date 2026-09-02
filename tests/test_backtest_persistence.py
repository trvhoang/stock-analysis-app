"""Strict schema-5 aggregate artifact contracts."""

from datetime import date
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backtest_engine.config import rulebook_for
from backtest_engine.models import RulebookExecution
from backtest_engine.persistence import (
    load_rulebook_result,
    save_regeneration_marker,
    save_rulebook_result,
    signal_artifact_path,
    validate_rulebook_document,
    write_regeneration_marker,
)


def _range(start="2011-01-03", end="2026-01-02"):
    return {"start": start, "end": end, "reason": None}


def _audit():
    return {
        "source": "fresh_schema5_raw_history",
        "eligible": True,
        "status": "clean",
        "reasons": [],
        "warnings": [],
        "effective_date_range": ["2011-01-03", "2026-01-02"],
    }


def _eligible_evidence():
    return {
        "status": "eligible",
        "eligible": True,
        "reasons": [],
        "common_as_of": "2026-01-02",
        "first_available_bar": "2011-01-03",
        "last_available_bar": "2026-01-02",
        "ticker_fingerprint": "a" * 64,
        "vnindex_fingerprint": "b" * 64,
        "observed_sessions": 3700,
        "expected_sessions": 3700,
        "coverage_ratio": 1.0,
        "max_gap_sessions": 0,
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
        "candidate_role": "baseline_control",
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
        "contract_version": "backtest_schema5_v1",
        "partition_labels": {
            "training": "in-sample",
            "test": "historical test — previously observed",
        },
        "horizon": "swing",
        "terminal_state": "success",
        "empty": False,
        "failure_reason": None,
        "rejection_reason": None,
        "evaluation_label": "Exploratory — gross",
        "rulebook": rulebook_for("swing").to_dict(),
        "audit_eligibility": _audit(),
        "evidence_eligibility": _eligible_evidence(),
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


def _stored(payload, *, schema_version=5):
    return {
        **payload,
        "schema_version": schema_version,
        "ticker": "VCB",
        "evaluated_at": "2026-08-22T00:00:00+07:00",
    }


class Schema5PersistenceTests(unittest.TestCase):
    def test_success_round_trips_one_ticker_horizon_aggregate(self):
        with TemporaryDirectory() as directory:
            path = save_rulebook_result("VCB", _success_document(), directory)
            result = load_rulebook_result(path)

            self.assertEqual(signal_artifact_path("VCB", "swing", directory).name, "VCB_signals_swing.json")
            self.assertEqual(result["schema_version"], 5)
            self.assertEqual(result["contract_version"], "backtest_schema5_v1")
            self.assertEqual(result["ticker"], "VCB")
            self.assertEqual(result["top_rulebook_ids"], ["swing_rulebook_v5__adx"])

    def test_schema_four_is_rejected_without_migration(self):
        with self.assertRaisesRegex(ValueError, "unsupported rulebook result schema"):
            validate_rulebook_document(_stored(_success_document(), schema_version=4))

    def test_schema5_requires_exact_partition_and_evidence_labels(self):
        payload = _stored(_success_document())

        self.assertTrue(validate_rulebook_document(payload))
        self.assertEqual(
            "historical test — previously observed",
            payload["partition_labels"]["test"],
        )
        payload["partition_labels"]["test"] = "untouched test"
        with self.assertRaisesRegex(ValueError, "partition_labels"):
            validate_rulebook_document(payload)

    def test_success_rejects_top_id_not_ranked_candidate(self):
        payload = _success_document()
        payload["top_rulebook_ids"] = ["missing_rulebook"]

        with self.assertRaisesRegex(ValueError, "top_rulebook_ids"):
            validate_rulebook_document(_stored(payload))

    def test_success_rejects_non_candidate_n_and_degenerate_p_value(self):
        payload = _success_document()
        payload["candidates"][0]["treatments"]["no-background-theme"]["training"]["n"] = 4
        with self.assertRaisesRegex(ValueError, "minimum"):
            validate_rulebook_document(_stored(payload))

        payload = _success_document()
        training = payload["candidates"][0]["treatments"]["no-background-theme"]["training"]
        training["p_value"] = 0.01
        with self.assertRaisesRegex(ValueError, "p_value"):
            validate_rulebook_document(_stored(payload))

    def test_success_accepts_informational_p_value_above_block_size(self):
        payload = _success_document()
        payload["candidates"][0]["treatments"]["no-background-theme"]["training"] = _metrics(
            n=21, win_rate=61.0, profit_pct=4.0, sharpe=0.5
        )

        self.assertTrue(validate_rulebook_document(_stored(payload)))

    def test_ineligible_success_remains_displayable(self):
        payload = _success_document()
        payload["evidence_eligibility"].update(
            {
                "status": "ineligible",
                "eligible": False,
                "reasons": ["coverage_ratio_below_0.95"],
                "observed_sessions": 3500,
                "coverage_ratio": 3500 / 3700,
            }
        )

        self.assertTrue(validate_rulebook_document(_stored(payload)))

    def test_empty_failed_and_regeneration_marker_round_trip(self):
        empty = _success_document()
        empty.update(
            {
                "terminal_state": "empty",
                "empty": True,
                "rejection_reason": "No baseline candidate met n >= 5.",
                "split": empty["split"],
                "candidates": [],
                "top_rulebook_ids": [],
            }
        )
        failed = _success_document()
        failed.update(
            {
                "terminal_state": "failed",
                "empty": True,
                "failure_reason": "source unavailable",
                "rejection_reason": None,
                "split": None,
                "candidates": [],
                "top_rulebook_ids": [],
            }
        )
        with TemporaryDirectory() as directory:
            empty_path = save_rulebook_result("VCB", empty, directory)
            self.assertEqual("empty", load_rulebook_result(empty_path)["terminal_state"])
            failed_path = save_rulebook_result("VCB", failed, directory)
            self.assertEqual("failed", load_rulebook_result(failed_path)["terminal_state"])
            marker_path = save_regeneration_marker("VCB", "swing", directory)
            marker = load_rulebook_result(marker_path)

        self.assertEqual("requires_regeneration", marker["terminal_state"])
        self.assertEqual("Regenerate under Backtest schema 5.", marker["rejection_reason"])
        self.assertEqual("unavailable", marker["evidence_eligibility"]["status"])

    def test_source_change_marker_round_trips_its_explicit_reason(self):
        reason = "Source history changed; regenerate Backtest schema 5."
        with TemporaryDirectory() as directory:
            path = signal_artifact_path("VCB", "swing", directory)
            write_regeneration_marker(path, "VCB", "swing", reason=reason)
            marker = load_rulebook_result(path)

        self.assertEqual(marker["terminal_state"], "requires_regeneration")
        self.assertEqual(marker["rejection_reason"], reason)
        self.assertEqual(marker["evidence_eligibility"]["reasons"], [reason])

    def test_malformed_evidence_and_atomic_replace_failure_preserve_previous_result(self):
        with TemporaryDirectory() as directory:
            path = save_rulebook_result("VCB", _success_document(), directory)
            malformed = _success_document()
            malformed["evidence_eligibility"]["ticker_fingerprint"] = "bad"
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                save_rulebook_result("VCB", malformed, directory)
            self.assertEqual("success", load_rulebook_result(path)["terminal_state"])

            replacement = _success_document()
            replacement["candidates"][0]["treatments"]["no-background-theme"]["training"]["profit_pct"] = 9.0
            with patch("backtest_engine.persistence.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    save_rulebook_result("VCB", replacement, directory)
            self.assertEqual("success", load_rulebook_result(path)["terminal_state"])


if __name__ == "__main__":
    unittest.main()
