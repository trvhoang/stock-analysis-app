"""Flexible Rulebook durable campaign contract tests."""

from dataclasses import dataclass, replace
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from flexible_rulebook.campaigns import (
    CampaignItem,
    CampaignRequest,
    build_campaign_selection_snapshot,
    SelectionSnapshot,
    continue_discovery,
    create_manifest,
    read_campaign_chain,
    read_campaign_manifest,
    reconcile_campaign_manifest,
    request_hash,
    write_campaign_item,
    write_campaign_manifest,
    write_campaign_selection_snapshot,
    transition,
)
from flexible_rulebook.service import checkpoint_campaign_item
from flexible_rulebook.contracts import (
    EvaluationPartition,
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    FeatureSnapshot,
    PartitionMetrics,
    PrimitiveSpec,
    RuntimeBudget,
    SelectionPolicy,
    canonical_json,
)
from flexible_rulebook.history import HistorySnapshot
from flexible_rulebook.execution import CompletedTrade
from flexible_rulebook.search import FrontierAssignment, StratumAssignment


class FlexibleRulebookCampaignTests(unittest.TestCase):
    @staticmethod
    def _source() -> FeatureSnapshot:
        return FeatureSnapshot("VCB", "a" * 64, date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "eligible", "flexible-quality-v1")

    def _request(self) -> CampaignRequest:
        source = self._source()
        profile = FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),))
        plan = FeaturePlan(source, FeatureBuildContract(), profile)
        assignment = FrontierAssignment("b" * 64, "candidate-space-v1", "frb-default-seed-v1", "VCB", 0, 10, (StratumAssignment("buy=rsi", 100, 10, 1, 0),), 1, 0)
        split = EvaluationSplit("calendar_10y_5y", date(2021, 1, 2), EvaluationPartition("training", date(2011, 1, 3), date(2021, 1, 1), 0, 99, 100), EvaluationPartition("test", date(2021, 1, 4), date(2026, 1, 2), 100, 149, 50))
        return CampaignRequest(
            operation="discover", frozen_members=("VCB",), source_snapshots=(source,), catalog_hash="c" * 64,
            engine_revision="flexible-engine-v1", rulebook_ids=(), feature_build_contract_hashes=(plan.build_contract.feature_build_contract_hash,),
            feature_plan_hashes=(plan.feature_plan_hash,), execution_contract=ExecutionContract(), split=split,
            runtime_budget=RuntimeBudget(), selection_policy=SelectionPolicy(), per_ticker_budget=10,
            frontier_assignment=assignment, submitted_at="first", cache_choice="reuse", cache_path="/tmp/cache", cache_age_seconds=20,
        )

    def _verified_source(self) -> HistorySnapshot:
        frame = pd.DataFrame({"date": [date(2011, 1, 3), date(2026, 1, 2)], "open": [100, 110], "high": [101, 111], "low": [99, 109], "close": [100, 110], "volume": [1000, 1000]})
        return HistorySnapshot("VCB", frame, "a" * 64, "eligible", date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "a" * 64)

    @staticmethod
    def _selection_evaluation(
        rulebook_id: str,
        win_rate: float,
        ticker: str = "VCB",
        source_fingerprint: str = "a" * 64,
    ) -> object:
        @dataclass(frozen=True)
        class Evaluation:
            rulebook_id: str
            training_metrics: PartitionMetrics
            test_metrics: PartitionMetrics
            ticker: str
            source_fingerprint: str
            training_trades: tuple[CompletedTrade, ...] = ()
            test_trades: tuple[CompletedTrade, ...] = ()
            split: str = "calendar_10y_5y"
            execution_revision: str = "flexible-execution-v1"

        metrics = PartitionMetrics(12, win_rate, 180.0, 15.0, 1.0)
        return Evaluation(rulebook_id, metrics, metrics, ticker, source_fingerprint)

    def test_hash_uses_semantic_request_not_submission_or_cache_diagnostics(self) -> None:
        request = self._request()

        self.assertEqual(request_hash(request), request_hash(replace(request, submitted_at="later", cache_choice="rebuild", cache_path="/other", cache_age_seconds=999)))
        self.assertNotEqual(request_hash(request), request_hash(replace(request, per_ticker_budget=9)))

    def test_policy_bound_digest_is_frozen_identity_while_legacy_stays_readable(self) -> None:
        legacy = self._request()
        policy_bound = replace(legacy, activation_policy_digest="f" * 64)

        self.assertIsNone(legacy.activation_policy_digest)
        self.assertNotEqual(request_hash(legacy), request_hash(policy_bound))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = create_manifest(policy_bound)
            write_campaign_manifest(root, manifest)
            restored = read_campaign_manifest(root, manifest.campaign_id)

        self.assertEqual(restored.request.activation_policy_digest, "f" * 64)

    def test_pre_activation_manifest_without_policy_field_remains_readable(self) -> None:
        manifest = create_manifest(self._request())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_campaign_manifest(root, manifest)
            payload = json.loads(path.read_text(encoding="utf-8"))
            identity = payload["manifest"]["request"]["identity"]
            identity.pop("activation_policy_digest", None)
            legacy_campaign_id = "fcmp_" + hashlib.sha256(
                canonical_json(identity).encode("utf-8")
            ).hexdigest()
            payload["manifest"]["campaign_id"] = legacy_campaign_id
            legacy_path = root / "campaigns" / legacy_campaign_id / "manifest.json"
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_text(json.dumps(payload), encoding="utf-8")
            restored = read_campaign_manifest(root, legacy_campaign_id)

        self.assertIsNone(restored.request.activation_policy_digest)
        self.assertEqual(restored.campaign_id, legacy_campaign_id)

    def test_policy_bound_continuation_preserves_its_explicit_cache_choice(self) -> None:
        request = replace(self._request(), activation_policy_digest="f" * 64)
        receipt_ids = ("frpr_" + "d" * 64,)
        parent = replace(
            create_manifest(request),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=receipt_ids,
        )

        child = continue_discovery(
            parent,
            verified_source=self._verified_source(),
            verified_feature_receipt_ids=receipt_ids,
        )

        self.assertEqual(child.activation_policy_digest, request.activation_policy_digest)
        self.assertEqual((child.cache_choice, child.cache_path), ("reuse", "/tmp/cache"))

    def test_discovery_hash_changes_for_frozen_frontier_fields(self) -> None:
        request = self._request()

        self.assertNotEqual(request_hash(request), request_hash(replace(request, frontier_assignment=replace(request.frontier_assignment, frontier_seed="new-sample"))))
        self.assertNotEqual(request_hash(request), request_hash(replace(request, frontier_assignment=replace(request.frontier_assignment, start_slot=1))))
        self.assertNotEqual(request_hash(request), request_hash(replace(request, frontier_assignment=replace(request.frontier_assignment, candidate_space_algorithm_version="candidate-space-v2"))))

    def test_non_discovery_rejects_frontier_assignment(self) -> None:
        request = self._request()

        with self.assertRaisesRegex(ValueError, "frontier"):
            replace(request, operation="qualify")

    def test_manifest_rejects_invalid_terminal_transition(self) -> None:
        with self.assertRaisesRegex(ValueError, "transition"):
            transition(create_manifest(self._request()), "completed")

    def test_continuation_links_parent_and_uses_persisted_next_slot(self) -> None:
        parent = transition(create_manifest(self._request()), "running")
        receipt_ids = ("frpr_" + "d" * 64,)
        parent = replace(parent, state="completed", next_slot=10, uncommitted_slot=None, chain_attempted_count=10, unsearched_count=90, feature_receipt_ids=receipt_ids)

        child = continue_discovery(
            parent,
            verified_source=self._verified_source(),
            verified_feature_receipt_ids=receipt_ids,
        )

        self.assertEqual((child.parent_campaign_id, child.frontier_assignment.start_slot), (parent.campaign_id, 10))
        self.assertEqual(request_hash(child) == request_hash(parent.request), False)

    def test_continue_rejects_mismatched_feature_receipt_without_cursor_advance(self) -> None:
        parent = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=("frpr_" + "d" * 64,),
        )

        with self.assertRaisesRegex(ValueError, "feature receipt"):
            continue_discovery(
                parent,
                verified_source=self._verified_source(),
                verified_feature_receipt_ids=("frpr_" + "e" * 64,),
            )

        self.assertEqual(parent.next_slot, 10)

    def test_continue_rejects_uncommitted_slot_or_changed_source(self) -> None:
        receipt_ids = ("frpr_" + "d" * 64,)
        parent = replace(create_manifest(self._request()), state="completed", next_slot=10, uncommitted_slot=10, chain_attempted_count=10, unsearched_count=90, feature_receipt_ids=receipt_ids)

        with self.assertRaisesRegex(ValueError, "unresolved"):
            continue_discovery(
                parent,
                verified_source=self._verified_source(),
                verified_feature_receipt_ids=receipt_ids,
            )

        completed = replace(create_manifest(self._request()), state="completed", next_slot=10, chain_attempted_count=10, unsearched_count=90, feature_receipt_ids=receipt_ids)
        changed = replace(self._verified_source(), fingerprint="b" * 64)
        with self.assertRaisesRegex(ValueError, "changed frozen source"):
            continue_discovery(
                completed,
                verified_source=changed,
                verified_feature_receipt_ids=receipt_ids,
            )

    def test_manifest_rejects_noncontiguous_discovery_cursor(self) -> None:
        manifest = create_manifest(self._request())

        with self.assertRaisesRegex(ValueError, "contiguous"):
            replace(manifest, next_slot=1, chain_attempted_count=0, unsearched_count=99)

    def test_item_rejects_unknown_historical_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "historical item state"):
            CampaignItem("VCB", "invented")

    def test_campaign_manifest_round_trip_preserves_frozen_identity(self) -> None:
        manifest = create_manifest(self._request())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, manifest)
            restored = read_campaign_manifest(root, manifest.campaign_id)

        self.assertEqual(restored, manifest)
        self.assertEqual(request_hash(restored.request), request_hash(manifest.request))

    def test_orphan_verified_item_is_adopted_after_manifest_checkpoint_gap(self) -> None:
        manifest = transition(create_manifest(self._request()), "running")
        orphan = CampaignItem("VCB", "qualified", "evidence-1")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, manifest)
            write_campaign_item(root, manifest, orphan)
            reconciled = reconcile_campaign_manifest(root, manifest.campaign_id)

        self.assertEqual(reconciled.items, (orphan,))

    def test_service_item_checkpoint_writes_artifact_before_returning_manifest_update(self) -> None:
        manifest = transition(create_manifest(self._request()), "running")
        item = CampaignItem("VCB", "qualified", "evidence-1")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = checkpoint_campaign_item(root, manifest, item)
            artifact = root / "campaigns" / manifest.campaign_id / "items" / "0000-VCB.json"
            exists = artifact.is_file()
        self.assertEqual(checkpoint.items, (item,))
        self.assertTrue(exists)

    def test_manifest_claiming_missing_item_becomes_item_failure_not_success(self) -> None:
        manifest = replace(
            transition(create_manifest(self._request()), "running"),
            items=(CampaignItem("VCB", "qualified", "missing-evidence"),),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, manifest)
            reconciled = reconcile_campaign_manifest(root, manifest.campaign_id)

        self.assertEqual(reconciled.items[0].state, "failed")
        self.assertIsNone(reconciled.items[0].artifact_id)

    def test_corrupt_claimed_item_becomes_item_failure_not_success(self) -> None:
        manifest = replace(
            transition(create_manifest(self._request()), "running"),
            items=(CampaignItem("VCB", "qualified", "corrupt-evidence"),),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, manifest)
            item_path = write_campaign_item(root, manifest, manifest.items[0])
            item_path.write_text("{}", encoding="utf-8")
            reconciled = reconcile_campaign_manifest(root, manifest.campaign_id)

        self.assertEqual(reconciled.items[0], CampaignItem("VCB", "failed"))

    def test_manifest_claiming_missing_selection_snapshot_becomes_campaign_failure(self) -> None:
        manifest = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            selection_snapshot_id="f" * 64,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, manifest)
            reconciled = reconcile_campaign_manifest(root, manifest.campaign_id)

        self.assertEqual(reconciled.state, "failed")
        self.assertEqual(reconciled.safe_error_code, "ARTIFACT.SELECTION_SNAPSHOT_UNAVAILABLE")

    def test_terminal_discovery_checkpoint_writes_immutable_selection_snapshot_first(self) -> None:
        manifest = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
        )
        snapshot = SelectionSnapshot(
            "complete_assigned_window",
            "a" * 64,
            "b" * 64,
            "ticker=VCB",
            "timing-distinct-top3-v1",
            "inclusive-two-pointer-v1",
            ("frb_" + "c" * 64,),
            ("frb_" + "c" * 64,),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            updated = write_campaign_selection_snapshot(root, manifest, snapshot)
            restored = read_campaign_manifest(root, manifest.campaign_id)

            self.assertTrue(
                (root / "campaigns" / manifest.campaign_id / "selections" / f"{updated.selection_snapshot_id}.json").is_file()
            )

        self.assertEqual(updated.selection_snapshot_id, restored.selection_snapshot_id)

    def test_selection_snapshot_checkpoint_rejects_nonterminal_discovery(self) -> None:
        snapshot = SelectionSnapshot(
            "partial_window",
            "a" * 64,
            "b" * 64,
            "ticker=VCB",
            "timing-distinct-top3-v1",
            "inclusive-two-pointer-v1",
            (),
            (),
        )

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "terminal discovery"):
                write_campaign_selection_snapshot(
                    Path(directory),
                    create_manifest(self._request()),
                    snapshot,
                )

    def test_higher_rank_selection_can_only_write_linked_successor_snapshot(self) -> None:
        receipt_ids = ("frpr_" + "d" * 64,)
        parent = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=receipt_ids,
        )
        parent_snapshot = SelectionSnapshot(
            "complete_assigned_window",
            "a" * 64,
            "b" * 64,
            "ticker=VCB",
            "timing-distinct-top3-v1",
            "inclusive-two-pointer-v1",
            ("frb_" + "c" * 64,),
            ("frb_" + "c" * 64,),
        )
        successor_snapshot = SelectionSnapshot(
            "complete_assigned_window",
            "e" * 64,
            "f" * 64,
            "ticker=VCB",
            "timing-distinct-top3-v1",
            "inclusive-two-pointer-v1",
            ("frb_" + "e" * 64,),
            ("frb_" + "e" * 64,),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            persisted_parent = write_campaign_selection_snapshot(
                root, parent, parent_snapshot
            )
            child_request = continue_discovery(
                persisted_parent,
                verified_source=self._verified_source(),
                verified_feature_receipt_ids=receipt_ids,
            )
            child = replace(
                create_manifest(child_request),
                state="completed",
                next_slot=20,
                chain_attempted_count=20,
                unsearched_count=80,
            )
            persisted_child = write_campaign_selection_snapshot(
                root, child, successor_snapshot
            )

            with self.assertRaisesRegex(ValueError, "already has a selection snapshot"):
                write_campaign_selection_snapshot(root, persisted_parent, successor_snapshot)

            restored_parent = read_campaign_manifest(root, persisted_parent.campaign_id)

        self.assertEqual(restored_parent.selection_snapshot_id, persisted_parent.selection_snapshot_id)
        self.assertNotEqual(persisted_child.selection_snapshot_id, persisted_parent.selection_snapshot_id)
        self.assertEqual(persisted_child.request.parent_campaign_id, persisted_parent.campaign_id)

    def test_linked_campaign_reads_only_verified_terminal_parent_chain(self) -> None:
        receipt_ids = ("frpr_" + "d" * 64,)
        parent = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=receipt_ids,
        )
        snapshot = SelectionSnapshot(
            "complete_assigned_window",
            "a" * 64,
            "b" * 64,
            "ticker=VCB",
            "timing-distinct-top3-v1",
            "inclusive-two-pointer-v1",
            ("frb_" + "c" * 64,),
            ("frb_" + "c" * 64,),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            persisted_parent = write_campaign_selection_snapshot(root, parent, snapshot)
            child = create_manifest(continue_discovery(
                persisted_parent,
                verified_source=self._verified_source(),
                verified_feature_receipt_ids=receipt_ids,
            ))
            write_campaign_manifest(root, child)
            chain = read_campaign_chain(root, child.campaign_id)

        self.assertEqual(
            tuple(manifest.campaign_id for manifest in chain),
            (persisted_parent.campaign_id, child.campaign_id),
        )

    def test_linked_campaign_rejects_parent_missing_terminal_selection_snapshot(self) -> None:
        receipt_ids = ("frpr_" + "d" * 64,)
        parent = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=receipt_ids,
            selection_snapshot_id="f" * 64,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, parent)
            child = create_manifest(continue_discovery(
                parent,
                verified_source=self._verified_source(),
                verified_feature_receipt_ids=receipt_ids,
            ))
            write_campaign_manifest(root, child)

            with self.assertRaisesRegex(ValueError, "parent selection snapshot"):
                read_campaign_chain(root, child.campaign_id)

    def test_terminal_child_recomputes_selection_from_verified_parent_chain(self) -> None:
        receipt_ids = ("frpr_" + "d" * 64,)
        parent = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=receipt_ids,
        )
        parent_snapshot = SelectionSnapshot(
            "complete_assigned_window",
            "a" * 64,
            "b" * 64,
            "ticker=VCB",
            "timing-distinct-top3-v1",
            "inclusive-two-pointer-v1",
            (),
            (),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            persisted_parent = write_campaign_selection_snapshot(
                root, parent, parent_snapshot
            )
            child = replace(
                create_manifest(continue_discovery(
                    persisted_parent,
                    verified_source=self._verified_source(),
                    verified_feature_receipt_ids=receipt_ids,
                )),
                state="completed",
                next_slot=20,
                chain_attempted_count=20,
                unsearched_count=80,
            )
            write_campaign_manifest(root, child)
            snapshot = build_campaign_selection_snapshot(
                read_campaign_chain(root, child.campaign_id),
                (
                    self._selection_evaluation("frb_" + "b" * 64, 65.0),
                    self._selection_evaluation("frb_" + "a" * 64, 70.0),
                ),
                ledger_digest="c" * 64,
                evaluation_digest="d" * 64,
            )

        self.assertEqual(snapshot.ranked_rulebook_ids, ("frb_" + "a" * 64, "frb_" + "b" * 64))
        self.assertEqual(snapshot.selected_rulebook_ids, snapshot.ranked_rulebook_ids)
        self.assertEqual(snapshot.searched_window_truth, "complete_assigned_window")

    def test_selection_recomputation_rejects_evidence_outside_frozen_ticker_scope(self) -> None:
        terminal = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
        )

        with self.assertRaisesRegex(ValueError, "frozen campaign scope"):
            build_campaign_selection_snapshot(
                (terminal,),
                (self._selection_evaluation("frb_" + "a" * 64, 70.0, "FPT"),),
                ledger_digest="c" * 64,
                evaluation_digest="d" * 64,
            )

    def test_selection_recomputation_rejects_evidence_from_changed_frozen_source(self) -> None:
        terminal = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
        )

        with self.assertRaisesRegex(ValueError, "frozen campaign scope"):
            build_campaign_selection_snapshot(
                (terminal,),
                (self._selection_evaluation("frb_" + "a" * 64, 70.0, source_fingerprint="b" * 64),),
                ledger_digest="c" * 64,
                evaluation_digest="d" * 64,
            )

    def test_manifest_rejects_request_that_does_not_match_its_campaign_id(self) -> None:
        manifest = create_manifest(self._request())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_campaign_manifest(root, manifest)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["manifest"]["request"]["identity"]["per_ticker_budget"] = 9
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "campaign_id"):
                read_campaign_manifest(root, manifest.campaign_id)


if __name__ == "__main__":
    unittest.main()
