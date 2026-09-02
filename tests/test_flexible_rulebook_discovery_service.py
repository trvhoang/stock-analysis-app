from datetime import date
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from flexible_rulebook.campaigns import CampaignRequest, CampaignItem, SelectionSnapshot, continue_discovery, create_manifest, transition, write_campaign_manifest, write_campaign_selection_snapshot
from flexible_rulebook.catalog import catalog_revision_1
from flexible_rulebook.cap_benchmark import WindowPhaseTiming
from flexible_rulebook.contracts import (
    EvaluationPartition,
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    FeatureSnapshot,
    PartitionMetrics,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
    RulebookEvaluation,
    RuntimeBudget,
    SelectionPolicy,
)
from flexible_rulebook.features import FeatureResolution, build_feature_store
from flexible_rulebook.history import HistorySnapshot
from flexible_rulebook.search import DiscoveryResult, SearchBudget, assign_frontier, candidate_space
from flexible_rulebook.service import DiscoveryService, _chain_evaluations
from flexible_rulebook.execution import CompletedTrade
from flexible_rulebook.storage import read_signal_set, selection_memberships_for_evaluation, write_campaign_selection_membership, write_signal_set


class FlexibleRulebookDiscoveryServiceTests(unittest.TestCase):
    def _fixtures(self):
        source = FeatureSnapshot("VCB", "a" * 64, date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "eligible", "flexible-quality-v1")
        profile = FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),))
        plan = FeaturePlan(source, FeatureBuildContract(), profile)
        assignment = assign_frontier(candidate_space(catalog_revision_1()), frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=SearchBudget(1))
        split = EvaluationSplit("calendar_10y_5y", date(2021, 1, 2), EvaluationPartition("training", date(2011, 1, 3), date(2021, 1, 1), 0, 99, 100), EvaluationPartition("test", date(2021, 1, 4), date(2026, 1, 2), 100, 149, 50))
        request = CampaignRequest("discover", ("VCB",), (source,), catalog_revision_1().catalog_hash, "flexible-engine-v1", (), (plan.build_contract.feature_build_contract_hash,), (plan.feature_plan_hash,), ExecutionContract(), split, RuntimeBudget(), SelectionPolicy(), 1, assignment)
        frame = pd.DataFrame({"date": [date(2011, 1, 3), date(2026, 1, 2)], "open": [100, 110], "high": [101, 111], "low": [99, 109], "close": [100, 110], "volume": [1000, 1000]})
        snapshot = HistorySnapshot("VCB", frame, "a" * 64, "eligible", date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "a" * 64)
        features = FeatureResolution(build_feature_store(snapshot, plan.build_contract, profile), plan, __import__("flexible_rulebook.contracts", fromlist=["FeatureResolutionReceipt"]).FeatureResolutionReceipt(plan, ((plan.primitive_keys[0].primitive_key, "d" * 64),)))
        return request, snapshot, features, candidate_space(catalog_revision_1())

    def test_service_checkpoints_receipt_ledger_item_and_cursor(self):
        request, snapshot, features, space = self._fixtures()
        assignment = request.frontier_assignment
        result = DiscoveryResult("no_qualified_candidate_within_budget", space.size, 1, 1, None, space.size - 1, (next(iter(__import__("flexible_rulebook.search", fromlist=["scheduled_candidates"]).scheduled_candidates(space, assignment)))[2],), (), ((0, "training_threshold"),), ())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = transition(create_manifest(request), "running")
            phases = []
            service = DiscoveryService(root, candidate_space=space, feature_resolver=lambda _source: features, discovery_runner=lambda *args, **kwargs: result, phase_observer=phases.append)
            checkpoint = service.run(manifest, verified_sources=(snapshot,))
            campaign_root = root / "campaigns" / manifest.campaign_id
            self.assertTrue(next((campaign_root / "features").glob("*.json")).is_file())
            self.assertTrue(next((campaign_root / "ledger" / "VCB").glob("*.json")).is_file())
            self.assertTrue((campaign_root / "items" / "0000-VCB.json").is_file())
            self.assertTrue(next((campaign_root / "selections").glob("*.json")).is_file())

        self.assertEqual(checkpoint.state, "completed")
        self.assertEqual(checkpoint.next_slot, 1)
        self.assertEqual(checkpoint.items[0].state, "no_qualified_candidate_within_budget")
        self.assertEqual(checkpoint.feature_receipt_ids, (features.receipt.receipt_id,))
        self.assertIsNotNone(checkpoint.selection_snapshot_id)
        self.assertTrue(all(isinstance(event, WindowPhaseTiming) for event in phases))
        self.assertEqual(
            [event.phase for event in phases],
            ["selection", "write"],
        )
        self.assertTrue(all(event.seconds >= 0.0 for event in phases))

    def test_cancellation_probe_stops_before_feature_or_candidate_work(self):
        request, snapshot, _features, space = self._fixtures()
        called = []
        with tempfile.TemporaryDirectory() as directory:
            manifest = transition(create_manifest(request), "running")
            service = DiscoveryService(
                Path(directory),
                candidate_space=space,
                feature_resolver=lambda _source: called.append("feature"),
                discovery_runner=lambda *args, **kwargs: called.append("discover"),
                cancellation_probe=lambda: True,
            )
            checkpoint = service.run(manifest, verified_sources=(snapshot,))
        self.assertEqual(checkpoint.state, "cancelled")
        self.assertEqual(called, [])

    def test_admission_deadline_keeps_current_slot_uncommitted_and_never_claims_no_result(self):
        request, snapshot, features, space = self._fixtures()
        with tempfile.TemporaryDirectory() as directory:
            manifest = transition(create_manifest(request), "running")
            service = DiscoveryService(
                Path(directory),
                candidate_space=space,
                feature_resolver=lambda _source: features,
                monotonic=lambda: 16_200,
            )
            checkpoint = service.run(manifest, verified_sources=(snapshot,))
        self.assertEqual(checkpoint.state, "completed_with_errors")
        self.assertEqual(checkpoint.items[0].state, "time_budget_exhausted")
        self.assertEqual(checkpoint.uncommitted_slot, checkpoint.next_slot)
        self.assertEqual(checkpoint.next_slot, 0)

    def test_completed_discovery_links_selection_membership_without_mutating_signal_evidence(self):
        request, snapshot, features, space = self._fixtures()
        assignment = request.frontier_assignment
        primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        definition = RulebookDefinition(
            (PredicateSpec("buy", primitive, (("cross", "up"), ("level", 52))),),
        )
        metrics = PartitionMetrics(12, 65.0, 15.0, 15.0, None)
        trades = tuple(
            CompletedTrade(
                f"trade-{index:02d}",
                date(2011, 1, 3), date(2011, 1, 4), date(2011, 1, 5),
                0, 1, 2, 100.0, 115.0, "take_profit", 15.0,
            )
            for index in range(12)
        )
        evaluation = RulebookEvaluation(
            definition, "VCB", features.plan.snapshot, request.catalog_hash,
            request.split, request.execution_contract, features.plan.build_contract,
            features.plan.profile, features.receipt, metrics, metrics,
            training_trades=trades, test_trades=trades,
        )
        canonical = next(iter(__import__("flexible_rulebook.search", fromlist=["scheduled_candidates"]).scheduled_candidates(space, assignment)))[2]
        result = DiscoveryResult(
            "no_qualified_candidate_within_budget", space.size, 1, 1, None,
            space.size - 1, (canonical,), (evaluation.rulebook_id,),
            ((0, "qualified"),), (evaluation,),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = transition(create_manifest(request), "running")
            checkpoint = DiscoveryService(
                root,
                candidate_space=space,
                feature_resolver=lambda _source: features,
                discovery_runner=lambda *args, **kwargs: result,
            ).run(manifest, verified_sources=(snapshot,))
            signal_path = root / "signal-sets" / evaluation.rulebook_id / "VCB" / f"{evaluation.evaluation_id}.json"
            signal = read_signal_set(signal_path)
            memberships = selection_memberships_for_evaluation(root, evaluation.evaluation_id)

        self.assertIsNotNone(checkpoint.selection_snapshot_id)
        self.assertNotIn("selection_provenance", signal)
        self.assertEqual(len(memberships), 1)
        self.assertEqual(memberships[0]["selection_snapshot_id"], checkpoint.selection_snapshot_id)

    def test_continuation_selection_includes_parent_committed_evidence(self):
        request, snapshot, features, space = self._fixtures()
        primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        parent_definition = RulebookDefinition(
            (PredicateSpec("buy", primitive, (("cross", "up"), ("level", 52))),),
        )
        child_definition = RulebookDefinition(
            (PredicateSpec("buy", primitive, (("cross", "up"), ("level", 55))),),
        )
        metrics = PartitionMetrics(12, 65.0, 15.0, 15.0, None)
        parent_trades = tuple(
            CompletedTrade(f"parent-{index:02d}", date(2011, 1, 3), date(2011, 1, 4), date(2011, 1, 5), 0, 1, 2, 100.0, 115.0, "take_profit", 15.0)
            for index in range(12)
        )
        child_trades = tuple(
            CompletedTrade(f"child-{index:02d}", date(2011, 1, 6), date(2011, 1, 7), date(2011, 1, 8), 3, 4, 5, 100.0, 116.0, "take_profit", 16.0)
            for index in range(12)
        )
        parent_evaluation = RulebookEvaluation(
            parent_definition, "VCB", features.plan.snapshot, request.catalog_hash,
            request.split, request.execution_contract, features.plan.build_contract,
            features.plan.profile, features.receipt, metrics, metrics,
            training_trades=parent_trades, test_trades=parent_trades,
        )
        child_evaluation = RulebookEvaluation(
            child_definition, "VCB", features.plan.snapshot, request.catalog_hash,
            request.split, request.execution_contract, features.plan.build_contract,
            features.plan.profile, features.receipt, metrics, metrics,
            training_trades=child_trades, test_trades=child_trades,
        )
        parent_manifest = replace(
            create_manifest(request), state="completed", next_slot=1,
            chain_attempted_count=1, unsearched_count=space.size - 1,
            feature_receipt_ids=(features.receipt.receipt_id,),
        )
        child_request = continue_discovery(
            parent_manifest,
            verified_source=snapshot,
            verified_feature_receipt_ids=(features.receipt.receipt_id,),
        )
        child_assignment = child_request.frontier_assignment
        canonical = next(iter(__import__("flexible_rulebook.search", fromlist=["scheduled_candidates"]).scheduled_candidates(space, child_assignment)))[2]
        result = DiscoveryResult(
            "no_qualified_candidate_within_budget", space.size, 2, 2, None,
            space.size - 2, (canonical,), (child_evaluation.rulebook_id,),
            ((1, "qualified"),), (child_evaluation,),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, parent_manifest)
            parent_snapshot = SelectionSnapshot(
                "complete_assigned_window", "a" * 64, "b" * 64,
                "ticker=VCB", "timing-distinct-top3-v1", "inclusive-two-pointer-v1",
                (parent_evaluation.rulebook_id,), (parent_evaluation.rulebook_id,),
            )
            persisted_parent = write_campaign_selection_snapshot(root, parent_manifest, parent_snapshot)
            write_signal_set(root, parent_evaluation)
            write_campaign_selection_membership(root, persisted_parent.campaign_id, parent_evaluation, persisted_parent.selection_snapshot_id)
            child_manifest = transition(create_manifest(child_request), "running")
            checkpoint = DiscoveryService(
                root,
                candidate_space=space,
                feature_resolver=lambda _source: features,
                discovery_runner=lambda *args, **kwargs: result,
            ).run(child_manifest, verified_sources=(snapshot,))
            selection_payload = __import__("flexible_rulebook.storage", fromlist=["read_selection_snapshot"]).read_selection_snapshot(
                root, checkpoint.campaign_id, checkpoint.selection_snapshot_id,
            )

        self.assertEqual(
            set(selection_payload["selected_rulebook_ids"]),
            {parent_evaluation.rulebook_id, child_evaluation.rulebook_id},
        )

    def test_corrupt_committed_parent_evidence_blocks_selection_recompute(self):
        request, _snapshot, _features, _space = self._fixtures()
        manifest = create_manifest(request)
        evaluation_id = "frev_" + "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "signal-sets" / ("frb_" + "b" * 64) / "VCB" / f"{evaluation_id}.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}", encoding="utf-8")
            with patch(
                "flexible_rulebook.service.selection_memberships_by_evaluation",
                return_value={evaluation_id: [{"campaign_id": manifest.campaign_id}]},
            ), patch(
                "flexible_rulebook.service._evaluation_from_signal_set",
                side_effect=ValueError("bad evidence"),
            ):
                with self.assertRaisesRegex(ValueError, "committed parent evaluation evidence"):
                    _chain_evaluations(root, (manifest,), ())


if __name__ == "__main__":
    unittest.main()
