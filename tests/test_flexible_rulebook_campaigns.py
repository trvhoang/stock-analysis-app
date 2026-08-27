"""Flexible Rulebook durable campaign contract tests."""

from dataclasses import replace
from datetime import date
import unittest

import pandas as pd

from flexible_rulebook.campaigns import CampaignItem, CampaignRequest, continue_discovery, create_manifest, request_hash, transition
from flexible_rulebook.contracts import (
    EvaluationPartition,
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    FeatureSnapshot,
    PrimitiveSpec,
    RuntimeBudget,
    SelectionPolicy,
)
from flexible_rulebook.history import HistorySnapshot
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

    def test_hash_uses_semantic_request_not_submission_or_cache_diagnostics(self) -> None:
        request = self._request()

        self.assertEqual(request_hash(request), request_hash(replace(request, submitted_at="later", cache_choice="rebuild", cache_path="/other", cache_age_seconds=999)))
        self.assertNotEqual(request_hash(request), request_hash(replace(request, per_ticker_budget=9)))

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
        parent = replace(parent, state="completed", next_slot=10, uncommitted_slot=None, chain_attempted_count=10, unsearched_count=90)

        child = continue_discovery(parent, verified_source=self._verified_source())

        self.assertEqual((child.parent_campaign_id, child.frontier_assignment.start_slot), (parent.campaign_id, 10))
        self.assertEqual(request_hash(child) == request_hash(parent.request), False)

    def test_continue_rejects_uncommitted_slot_or_changed_source(self) -> None:
        parent = replace(create_manifest(self._request()), state="completed", next_slot=10, uncommitted_slot=10, chain_attempted_count=10, unsearched_count=90)

        with self.assertRaisesRegex(ValueError, "unresolved"):
            continue_discovery(parent, verified_source=self._verified_source())

        completed = replace(create_manifest(self._request()), state="completed", next_slot=10, chain_attempted_count=10, unsearched_count=90)
        changed = replace(self._verified_source(), fingerprint="b" * 64)
        with self.assertRaisesRegex(ValueError, "changed frozen source"):
            continue_discovery(completed, verified_source=changed)

    def test_manifest_rejects_noncontiguous_discovery_cursor(self) -> None:
        manifest = create_manifest(self._request())

        with self.assertRaisesRegex(ValueError, "contiguous"):
            replace(manifest, next_slot=1, chain_attempted_count=0, unsearched_count=99)

    def test_item_rejects_unknown_historical_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "historical item state"):
            CampaignItem("VCB", "invented")


if __name__ == "__main__":
    unittest.main()
