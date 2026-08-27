"""Flexible Rulebook schema-1 storage tests."""

from decimal import Decimal
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from flexible_rulebook.contracts import EvaluationPartition, EvaluationSplit, ExecutionContract, FeatureBuildContract, FeaturePlan, FeatureProfile, FeatureResolutionReceipt, FeatureSnapshot, PartitionMetrics, PredicateSpec, PrimitiveSpec, RulebookDefinition, RulebookEvaluation
from flexible_rulebook.execution import CompletedTrade
from flexible_rulebook.storage import append_ledger_chunk, iter_signal_set_paths, read_signal_set, resolve_flexible_root, write_feature_resolution_receipt, write_rulebook_definition, write_selection_snapshot, write_signal_set


class FlexibleRulebookStorageTests(unittest.TestCase):
    @staticmethod
    def _definition() -> RulebookDefinition:
        rsi = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        return RulebookDefinition(
            buy_predicates=(PredicateSpec("buy", rsi, (("cross", "up"), ("level", Decimal("52")))),),
            max_hold_bars=22,
        )

    def _evaluation(self) -> RulebookEvaluation:
        definition = self._definition()
        snapshot = FeatureSnapshot("VCB", "a" * 64, date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "eligible", "flexible-quality-v1")
        contract = FeatureBuildContract()
        profile = FeatureProfile((definition.buy_predicates[0].primitive,))
        plan = FeaturePlan(snapshot, contract, profile)
        receipt = FeatureResolutionReceipt(plan, ((plan.primitive_keys[0].primitive_key, "b" * 64),))
        split = EvaluationSplit(
            "calendar_10y_5y", date(2021, 1, 2),
            EvaluationPartition("training", date(2011, 1, 3), date(2021, 1, 1), 0, 2, 3),
            EvaluationPartition("test", date(2021, 1, 4), date(2026, 1, 2), 3, 5, 3),
        )
        metrics = PartitionMetrics(1, 100.0, 15.0, 15.0, None)
        training = CompletedTrade("training-1", date(2011, 1, 3), date(2011, 1, 4), date(2011, 1, 5), 0, 1, 2, 100.0, 115.0, "take_profit", 15.0)
        test = CompletedTrade("test-1", date(2021, 1, 4), date(2021, 1, 5), date(2021, 1, 6), 3, 4, 5, 100.0, 115.0, "take_profit", 15.0)
        return RulebookEvaluation(definition, "VCB", snapshot, "c" * 64, split, ExecutionContract(), contract, profile, receipt, metrics, metrics, training_trades=(training,), test_trades=(test,))

    @staticmethod
    def _receipt() -> FeatureResolutionReceipt:
        spec = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        snapshot = FeatureSnapshot("VCB", "a" * 64, date(2025, 1, 2), date(2025, 12, 31), date(2025, 1, 2), date(2025, 12, 31), "eligible", "flexible-history-v1")
        plan = FeaturePlan(snapshot, FeatureBuildContract(), FeatureProfile((spec,)))
        return FeatureResolutionReceipt(plan, ((plan.primitive_keys[0].primitive_key, "b" * 64),))

    @staticmethod
    def _ledger_row(receipt_id: str) -> dict[str, object]:
        return {
            "candidate_space_hash": "a" * 64, "candidate_space_size": 100,
            "candidate_space_algorithm_version": "candidate-space-v1", "canonical_index": 7,
            "global_slot": 0, "stratum_id": "buy=rsi", "stratum_slot": 0,
            "assignment_hash": "b" * 64, "frontier_algorithm_version": "frontier-v1",
            "stratification_revision": "stratified-v1", "stratum_multiplier": 3,
            "stratum_offset": 1, "stratum_quota": 10, "seed_fingerprint": "c" * 64,
            "feature_receipt_id": receipt_id, "outcome": "training_entry_upper_bound", "unsearched_count": 99,
        }

    def test_root_is_absolute_and_definition_is_hash_addressed(self) -> None:
        self.assertTrue(resolve_flexible_root().is_absolute())
        with tempfile.TemporaryDirectory() as directory:
            path = write_rulebook_definition(Path(directory), self._definition())
            self.assertRegex(path.name, r"^frb_[0-9a-f]{64}\.json$")
            self.assertTrue(path.is_file())

    def test_different_existing_document_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = write_rulebook_definition(root, self._definition())
            path.write_text("different", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already differs"):
                write_rulebook_definition(root, self._definition())
            self.assertEqual(path.read_text(encoding="utf-8"), "different")

    def test_reader_rejects_non_signal_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"; path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError): read_signal_set(path)

    def test_feature_receipt_is_immutable(self) -> None:
        receipt = self._receipt()
        with tempfile.TemporaryDirectory() as directory:
            first = write_feature_resolution_receipt(Path(directory), "campaign-1", "VCB", receipt)
            second = write_feature_resolution_receipt(Path(directory), "campaign-1", "VCB", receipt)
            self.assertEqual(first.relative_to(Path(directory)).parts[:3], ("campaigns", "campaign-1", "features"))
        self.assertEqual(first, second)

    def test_rejected_ledger_row_stays_compact(self) -> None:
        receipt = self._receipt(); row = self._ledger_row(receipt.receipt_id)
        with tempfile.TemporaryDirectory() as directory:
            write_feature_resolution_receipt(Path(directory), "campaign-1", "VCB", receipt)
            path = append_ledger_chunk(Path(directory), "campaign-1", "VCB", (row,))
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["rows"], [row])
        self.assertNotIn("completed_trades", payload["rows"][0])

    def test_ledger_rejects_materialized_unsearched_ids(self) -> None:
        receipt = self._receipt(); row = self._ledger_row(receipt.receipt_id) | {"unsearched_candidate_ids": [8, 9]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); write_feature_resolution_receipt(root, "campaign-1", "VCB", receipt)
            with self.assertRaisesRegex(ValueError, "unsearched IDs"):
                append_ledger_chunk(root, "campaign-1", "VCB", (row,))

    def test_ledger_rejects_row_without_assignment_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "provenance"):
                append_ledger_chunk(Path(directory), "campaign-1", "VCB", ({"global_slot": 0, "canonical_index": 7, "outcome": "training_entry_upper_bound"},))

    def test_ledger_requires_prewritten_feature_receipt(self) -> None:
        receipt = self._receipt()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "feature receipt"):
                append_ledger_chunk(Path(directory), "campaign-1", "VCB", (self._ledger_row(receipt.receipt_id),))

    def test_storage_rejects_unsafe_campaign_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "path component"):
                write_selection_snapshot(Path(directory), "../campaign", self._selection_snapshot())

    def test_selection_snapshot_rejects_global_claim_for_partial_window(self) -> None:
        snapshot = self._selection_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            path = write_selection_snapshot(Path(directory), "campaign-1", snapshot)
            self.assertTrue(path.is_file())
            with self.assertRaises(ValueError): write_selection_snapshot(Path(directory), "campaign-2", {**snapshot, "global_exhaustion": True})

    @staticmethod
    def _selection_snapshot() -> dict[str, object]:
        return {
            "searched_window_truth": "partial_window", "input_ledger_digest": "a" * 64,
            "input_evaluation_digest": "b" * 64, "selection_scope": "ticker=VCB",
            "selection_policy_revision": "timing-distinct-top3-v1",
            "pairing_algorithm_revision": "inclusive-two-pointer-v1",
            "ranked_rulebook_ids": ["frb_" + "c" * 64], "selected_rulebook_ids": ["frb_" + "c" * 64],
            "blocker_relations": [],
        }

    def test_selection_snapshot_requires_chain_and_integer_pairing_evidence(self) -> None:
        snapshot = self._selection_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "selection snapshot"):
                write_selection_snapshot(Path(directory), "campaign-1", {"searched_window_truth": "partial_window"})
            invalid = {**snapshot, "blocker_relations": [{"blocked_rulebook_id": "frb_" + "d" * 64, "representative_rulebook_id": "frb_" + "c" * 64, "overlap_numerator": 9.0, "overlap_denominator": 12}]}
            with self.assertRaisesRegex(ValueError, "overlap"):
                write_selection_snapshot(Path(directory), "campaign-1", invalid)

    def test_continue_writes_new_snapshot_without_mutating_verified_parent(self) -> None:
        snapshot = self._selection_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); parent = write_selection_snapshot(root, "campaign-1", snapshot)
            parent_bytes = parent.read_bytes()
            parent_id = json.loads(parent.read_text(encoding="utf-8"))["selection_snapshot_id"]
            child = write_selection_snapshot(root, "campaign-1", {**snapshot, "parent_selection_snapshot_id": parent_id, "searched_window_truth": "complete_assigned_window"})
            self.assertEqual(parent.read_bytes(), parent_bytes)
            with self.assertRaisesRegex(ValueError, "parent"):
                write_selection_snapshot(root, "campaign-1", {**snapshot, "parent_selection_snapshot_id": "d" * 64})
        self.assertNotEqual(parent, child)

    def test_signal_set_traversal_excludes_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "cache").mkdir(); (root / "cache" / "fake.json").write_text("{}", encoding="utf-8")
            self.assertEqual(iter_signal_set_paths(root), ())

    def test_signal_set_is_self_contained_immutable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); evaluation = self._evaluation()
            path = write_signal_set(root, evaluation, explicitly_saved=True)
            payload = read_signal_set(path)
            self.assertEqual(iter_signal_set_paths(root), (path,))
            self.assertEqual(path.relative_to(root).parts[:3], ("signal-sets", evaluation.rulebook_id, "VCB"))
        self.assertEqual((payload["ticker"], payload["catalog_hash"], payload["qualification_revision"], payload["completed_trades"]["training"][0]["trade_id"]), ("VCB", "c" * 64, "both-partitions-12-65-15-v1", "training-1"))

    def test_discovered_signal_set_retains_assignment_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); evaluation = self._evaluation()
            path = write_signal_set(root, evaluation, explicitly_saved=True, discovery_provenance=self._ledger_row(evaluation.feature_receipt_id))
            payload = read_signal_set(path)
        self.assertEqual(payload["discovery_provenance"]["assignment_hash"], "b" * 64)

    def test_unqualified_signal_set_requires_explicit_save(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "qualified or explicitly saved"):
                write_signal_set(Path(directory), self._evaluation())


if __name__ == "__main__":
    unittest.main()
