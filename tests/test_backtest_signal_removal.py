"""Schema-5 saved-candidate removal and interruption-recovery contracts."""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backtest_engine.config import rulebook_for
from backtest_engine.manual_position_store import (
    build_v5_risk_snapshot,
    create_manual_position,
)
from backtest_engine.models import RulebookExecution
from backtest_engine.persistence import (
    load_rulebook_result,
    replace_validated_rulebook_result,
    save_rulebook_result,
    signal_artifact_path,
    validate_rulebook_document,
)
from backtest_engine.signal_removal import (
    SignalCandidateKey,
    SignalRemovalBlockedError,
    recover_pending_signal_removal,
    remove_saved_signal_candidates,
)
from backtest_engine.signal_catalog import list_current_signal_set_rows


def _metrics(n=5, win_rate=60.0, profit_pct=3.0, sharpe=0.4):
    return {
        "n": n,
        "win_rate": win_rate,
        "profit_pct": profit_pct,
        "sharpe": sharpe if n >= 2 else None,
        "p_value": None,
        "p_value_status": "not_estimated_n_le_block_size",
    }


def _candidate(gates, *, win_rate, profit_pct, sharpe):
    execution = RulebookExecution(rulebook_for("swing"), gates)
    return {
        "rulebook_id": execution.rule_id,
        "candidate_role": "baseline_control",
        "selected_gates": list(gates),
        "preferred_variant": "no-background-theme",
        "treatments": {
            "no-background-theme": {
                "theme_variant": "no-background-theme",
                "theme_mode": None,
                "training": _metrics(win_rate=win_rate, profit_pct=profit_pct, sharpe=sharpe),
                "test": _metrics(n=1, win_rate=100.0, profit_pct=1.0, sharpe=0.0),
                "training_dsr": None,
                "dsr_status": "unavailable",
            },
            "background-theme": {
                "theme_variant": "background-theme",
                "theme_mode": "AND",
                "training": _metrics(n=1, win_rate=100.0, profit_pct=1.0, sharpe=0.0),
                "test": _metrics(n=0, win_rate=0.0, profit_pct=0.0, sharpe=0.0),
                "training_dsr": None,
                "dsr_status": "unavailable",
            },
        },
    }


def _success_document():
    candidates = [
        _candidate(("rulebook_adx_gate",), win_rate=64.0, profit_pct=4.0, sharpe=0.3),
        _candidate(("rulebook_rsi_upcross",), win_rate=63.0, profit_pct=5.0, sharpe=0.5),
        _candidate(("rulebook_volume_gate",), win_rate=62.0, profit_pct=6.0, sharpe=0.6),
        _candidate(("rulebook_joint_trend_pass",), win_rate=61.0, profit_pct=7.0, sharpe=0.8),
    ]
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
        "audit_eligibility": {
            "source": "fresh_schema5_raw_history", "eligible": True, "status": "clean",
            "reasons": [], "warnings": [],
            "effective_date_range": ["2011-01-03", "2026-01-02"],
        },
        "evidence_eligibility": {
            "status": "eligible", "eligible": True, "reasons": [],
            "common_as_of": "2026-01-02", "first_available_bar": "2011-01-03",
            "last_available_bar": "2026-01-02", "ticker_fingerprint": "a" * 64,
            "vnindex_fingerprint": "b" * 64, "observed_sessions": 3700,
            "expected_sessions": 3700, "coverage_ratio": 1.0, "max_gap_sessions": 0,
        },
        "requested_date_range": {"start": "2011-01-03", "end": "2026-01-02", "reason": None},
        "effective_data_range": {"start": "2011-01-03", "end": "2026-01-02", "reason": None},
        "split": {
            "method": "calendar_10y_5y",
            "train": {"start": "2011-01-03", "end": "2021-01-01"},
            "test": {"start": "2021-01-04", "end": "2026-01-02"},
        },
        "candidates": candidates,
        "top_rulebook_ids": [candidate["rulebook_id"] for candidate in candidates[:3]],
    }


def _single_candidate_document():
    document = _success_document()
    document["candidates"] = document["candidates"][:1]
    document["top_rulebook_ids"] = [document["candidates"][0]["rulebook_id"]]
    return document


class SignalRemovalTests(unittest.TestCase):
    def setUp(self):
        self._temporary = TemporaryDirectory()
        root = Path(self._temporary.name)
        self.signals = str(root / "signals")
        self.positions = str(root / "positions")

    def tearDown(self):
        self._temporary.cleanup()

    def _save(self, ticker="VCB", document=None):
        return save_rulebook_result(ticker, document or _success_document(), self.signals)

    def _read(self, ticker="VCB"):
        return load_rulebook_result(signal_artifact_path(ticker, "swing", self.signals))

    def test_removal_preserves_unselected_candidates_and_promotes_ranked_fourth(self):
        self._save()
        selected = SignalCandidateKey("VCB", "swing", self._read()["candidates"][0]["rulebook_id"])

        result = remove_saved_signal_candidates(
            [selected], signal_dir=self.signals, positions_dir=self.positions,
        )

        document = self._read()
        self.assertEqual(result.removed, (selected,))
        self.assertEqual(len(document["candidates"]), 3)
        self.assertEqual(
            document["top_rulebook_ids"],
            [candidate["rulebook_id"] for candidate in document["candidates"]],
        )

    def test_validated_administrative_replacement_is_part_of_persistence_public_api(self):
        persistence = importlib.import_module("backtest_engine.persistence")

        self.assertIn("replace_validated_rulebook_result", persistence.__all__)

    def test_removal_of_last_candidate_writes_valid_regeneratable_empty_document(self):
        self._save(document=_single_candidate_document())
        selected = SignalCandidateKey("VCB", "swing", self._read()["candidates"][0]["rulebook_id"])

        remove_saved_signal_candidates([selected], signal_dir=self.signals, positions_dir=self.positions)

        document = self._read()
        self.assertEqual(
            (document["terminal_state"], document["empty"], document["candidates"],
             document["top_rulebook_ids"], document["rejection_reason"]),
            ("empty", True, [], [], "All saved candidates were removed by user."),
        )
        self.assertTrue(validate_rulebook_document(document))

    def test_stale_selection_writes_nothing(self):
        self._save()
        before = self._read()

        with self.assertRaisesRegex(ValueError, "is not present"):
            remove_saved_signal_candidates(
                [SignalCandidateKey("VCB", "swing", "missing")],
                signal_dir=self.signals, positions_dir=self.positions,
            )

        self.assertEqual(self._read(), before)

    def test_open_or_closed_position_reference_blocks_every_selected_artifact(self):
        self._save("VCB")
        self._save("FPT")
        vcb = self._read("VCB")["candidates"][0]
        reference = {
            "schema_version": 5,
            "contract_version": "backtest_schema5_v1",
            "ticker": "VCB",
            "horizon": "swing",
            "rulebook_id": vcb["rulebook_id"],
            "preferred_variant": vcb["preferred_variant"],
            "evidence_eligibility": self._read("VCB")["evidence_eligibility"],
            "exploratory_candidate": vcb,
        }
        create_manual_position(
            "VCB", 100, "2026-01-02", actual_sell_price=110, sell_date="2026-01-05",
            signal_reference=reference, entry_context={"match_level": 0.0, "current_price": 100},
            risk_snapshot=build_v5_risk_snapshot("swing", 2, 100), positions_dir=self.positions,
        )
        before_vcb, before_fpt = self._read("VCB"), self._read("FPT")
        fpt_id = self._read("FPT")["candidates"][0]["rulebook_id"]

        with self.assertRaises(SignalRemovalBlockedError) as caught:
            remove_saved_signal_candidates(
                [SignalCandidateKey("VCB", "swing", vcb["rulebook_id"]),
                 SignalCandidateKey("FPT", "swing", fpt_id)],
                signal_dir=self.signals, positions_dir=self.positions,
            )

        self.assertEqual(caught.exception.protected, (SignalCandidateKey("VCB", "swing", vcb["rulebook_id"]),))
        self.assertEqual((self._read("VCB"), self._read("FPT")), (before_vcb, before_fpt))

    def test_write_failure_leaves_recoverable_journal_and_next_recovery_restores_every_artifact(self):
        self._save("VCB", _single_candidate_document())
        self._save("FPT", _single_candidate_document())
        before_vcb, before_fpt = self._read("VCB"), self._read("FPT")
        selections = [
            SignalCandidateKey("VCB", "swing", before_vcb["candidates"][0]["rulebook_id"]),
            SignalCandidateKey("FPT", "swing", before_fpt["candidates"][0]["rulebook_id"]),
        ]
        calls = 0

        def fail_second_write(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            return replace_validated_rulebook_result(*args)

        with patch("backtest_engine.signal_removal.replace_validated_rulebook_result", side_effect=fail_second_write):
            with self.assertRaisesRegex(OSError, "simulated disk failure"):
                remove_saved_signal_candidates(selections, signal_dir=self.signals, positions_dir=self.positions)

        self.assertTrue((Path(self.signals) / ".backtest-signal-removal-transaction.json").exists())
        recover_pending_signal_removal(self.signals)
        self.assertEqual((self._read("VCB"), self._read("FPT")), (before_vcb, before_fpt))


class SignalRemovalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self._temporary = TemporaryDirectory()
        self.signals = str(Path(self._temporary.name) / "signals")

    def tearDown(self):
        self._temporary.cleanup()

    def _journal(self):
        return Path(self.signals) / ".backtest-signal-removal-transaction.json"

    def _document(self, ticker):
        return load_rulebook_result(signal_artifact_path(ticker, "swing", self.signals))

    def _write_mixed_journal(self, *, all_after=False):
        before, after = {}, {}
        for ticker in ("VCB", "FPT"):
            save_rulebook_result(ticker, _single_candidate_document(), self.signals)
            before[ticker] = self._document(ticker)
            after[ticker] = copy.deepcopy(before[ticker])
            after[ticker].update({
                "terminal_state": "empty", "empty": True, "failure_reason": None,
                "rejection_reason": "All saved candidates were removed by user.",
                "candidates": [], "top_rulebook_ids": [],
            })
            self.assertTrue(validate_rulebook_document(after[ticker]))
        Path(signal_artifact_path("VCB", "swing", self.signals)).write_text(
            json.dumps(after["VCB"]), encoding="utf-8",
        )
        if all_after:
            Path(signal_artifact_path("FPT", "swing", self.signals)).write_text(
                json.dumps(after["FPT"]), encoding="utf-8",
            )
        self._journal().write_text(json.dumps({
            "schema_version": 1, "operation": "backtest_signal_removal",
            "entries": [
                {"ticker": ticker, "horizon": "swing", "before": before[ticker], "after": after[ticker]}
                for ticker in ("VCB", "FPT")
            ],
        }), encoding="utf-8")
        return before, after

    def test_recovery_rolls_back_mixed_replacement_before_any_reader_uses_it(self):
        before, _after = self._write_mixed_journal()

        recover_pending_signal_removal(self.signals)

        self.assertEqual((self._document("VCB"), self._document("FPT")), (before["VCB"], before["FPT"]))
        self.assertFalse(self._journal().exists())

    def test_recovery_keeps_completed_replacement_and_only_clears_journal(self):
        _before, after = self._write_mixed_journal(all_after=True)

        recover_pending_signal_removal(self.signals)

        self.assertEqual((self._document("VCB"), self._document("FPT")), (after["VCB"], after["FPT"]))
        self.assertFalse(self._journal().exists())

    def test_malformed_journal_never_changes_an_artifact(self):
        save_rulebook_result("VCB", _single_candidate_document(), self.signals)
        before = self._document("VCB")
        self._journal().write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "transaction journal"):
            recover_pending_signal_removal(self.signals)

        self.assertEqual(self._document("VCB"), before)

    def test_catalog_recovers_mixed_replacement_before_listing_current_rows(self):
        before, _after = self._write_mixed_journal()

        catalog = list_current_signal_set_rows(self.signals)

        self.assertEqual(len(catalog["valid"]), 2)
        self.assertEqual((self._document("VCB"), self._document("FPT")), (before["VCB"], before["FPT"]))
        self.assertFalse(self._journal().exists())

    def test_catalog_refuses_to_list_artifacts_when_recovery_journal_is_invalid(self):
        save_rulebook_result("VCB", _single_candidate_document(), self.signals)
        self._journal().write_text("{}", encoding="utf-8")

        catalog = list_current_signal_set_rows(self.signals)

        self.assertEqual((catalog["valid"], catalog["terminal"], catalog["invalid"]), ([], [], []))
        self.assertTrue(catalog["warnings"][0].startswith("Signal removal recovery is required:"))


if __name__ == "__main__":
    unittest.main()
