"""Flexible Rulebook campaign submission lifecycle tests."""

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

import pandas as pd
import pytz

from flexible_rulebook.campaigns import (
    CampaignRequest,
    create_manifest,
    transition,
    write_campaign_manifest,
)
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
from flexible_rulebook.runner import (
    FrozenSourceVerificationError,
    claim_campaign,
    continue_campaign,
    heartbeat_campaign,
    recover_stale_lease,
    read_campaign,
    release_campaign_lease,
    request_cancel,
    resume_campaign,
    run_campaign,
    submit_campaign,
    verify_frozen_source,
)
from flexible_rulebook.history import HistorySnapshot
from flexible_rulebook.search import FrontierAssignment, StratumAssignment
from flexible_rulebook.service import ReceiptCheckpointService


class FlexibleRulebookRunnerTests(unittest.TestCase):
    @staticmethod
    def _request() -> CampaignRequest:
        source = FeatureSnapshot(
            "VCB", "a" * 64, date(2011, 1, 3), date(2026, 1, 2),
            date(2011, 1, 3), date(2026, 1, 2), "eligible", "flexible-quality-v1",
        )
        profile = FeatureProfile((
            PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),
        ))
        plan = FeaturePlan(source, FeatureBuildContract(), profile)
        assignment = FrontierAssignment(
            "b" * 64, "candidate-space-v1", "frb-default-seed-v1", "VCB", 0, 10,
            (StratumAssignment("buy=rsi", 100, 10, 1, 0),), 1, 0,
        )
        split = EvaluationSplit(
            "calendar_10y_5y", date(2021, 1, 2),
            EvaluationPartition("training", date(2011, 1, 3), date(2021, 1, 1), 0, 99, 100),
            EvaluationPartition("test", date(2021, 1, 4), date(2026, 1, 2), 100, 149, 50),
        )
        return CampaignRequest(
            operation="discover", frozen_members=("VCB",), source_snapshots=(source,),
            catalog_hash="c" * 64, engine_revision="flexible-engine-v1", rulebook_ids=(),
            feature_build_contract_hashes=(plan.build_contract.feature_build_contract_hash,),
            feature_plan_hashes=(plan.feature_plan_hash,), execution_contract=ExecutionContract(),
            split=split, runtime_budget=RuntimeBudget(), selection_policy=SelectionPolicy(),
            per_ticker_budget=10, frontier_assignment=assignment,
        )

    @staticmethod
    def _verified_history(fingerprint: str = "a" * 64) -> HistorySnapshot:
        return HistorySnapshot(
            ticker="VCB",
            frame=pd.DataFrame(
                {
                    "date": ["2011-01-03", "2026-01-02"],
                    "open": [10_000, 20_000],
                    "high": [11_000, 21_000],
                    "low": [9_000, 19_000],
                    "close": [10_500, 20_500],
                    "volume": [100, 200],
                }
            ),
            fingerprint=fingerprint,
            quality_state="eligible",
            requested_start=date(2011, 1, 3),
            requested_as_of=date(2026, 1, 2),
            first_date=date(2011, 1, 3),
            as_of_date=date(2026, 1, 2),
            evidence_prefix_fingerprint=fingerprint,
        )

    def test_frozen_source_verifier_returns_exact_fresh_source_before_execution(self) -> None:
        manifest = transition(create_manifest(self._request()), "running")
        fresh_source = self._verified_history()

        verified = verify_frozen_source(
            manifest,
            source_loader=lambda _source: fresh_source,
        )

        self.assertEqual(verified, (fresh_source,))

    def test_frozen_source_verifier_rejects_corrected_history_without_advancing_work(self) -> None:
        manifest = transition(create_manifest(self._request()), "running")

        with self.assertRaises(FrozenSourceVerificationError) as raised:
            verify_frozen_source(
                manifest,
                source_loader=lambda _source: self._verified_history("b" * 64),
            )

        self.assertEqual(raised.exception.safe_error_code, "SOURCE.CHANGED")
        self.assertEqual(manifest.next_slot, 0)

    def test_frozen_source_verifier_rejects_unavailable_feature_revision(self) -> None:
        manifest = transition(create_manifest(self._request()), "running")

        with self.assertRaises(FrozenSourceVerificationError) as raised:
            verify_frozen_source(
                manifest,
                source_loader=lambda _source: self._verified_history(),
                build_contract=FeatureBuildContract(feature_algorithm_revision="unavailable-v2"),
            )

        self.assertEqual(
            raised.exception.safe_error_code,
            "FEATURE.REVISION_UNAVAILABLE",
        )

    def test_receipt_checkpoint_service_persists_frozen_receipt_before_returning_checkpoint(self) -> None:
        manifest = transition(create_manifest(self._request()), "running")
        source = manifest.request.source_snapshots[0]
        profile = FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),))
        plan = FeaturePlan(source, FeatureBuildContract(), profile)
        from flexible_rulebook.contracts import FeatureResolutionReceipt
        receipt = FeatureResolutionReceipt(
            plan,
            ((plan.primitive_keys[0].primitive_key, "d" * 64),),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = ReceiptCheckpointService(
                root,
                receipt_resolver=lambda _source: receipt,
            ).run(manifest, verified_sources=(self._verified_history(),))
            receipt_path = root / "campaigns" / manifest.campaign_id / "features" / f"VCB-{plan.feature_plan_hash}.json"
            receipt_was_persisted = receipt_path.is_file()

        self.assertEqual(checkpoint.feature_receipt_ids, (receipt.receipt_id,))
        self.assertTrue(receipt_was_persisted)


    def test_continue_campaign_creates_a_persisted_linked_window_from_frozen_parent(self) -> None:
        parent = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=("frpr_" + "d" * 64,),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, parent)
            child_campaign_id = continue_campaign(
                parent.campaign_id,
                root,
                source_loader=lambda _source: self._verified_history(),
            )
            child = read_campaign(child_campaign_id, root)

        self.assertEqual(child.request.parent_campaign_id, parent.campaign_id)
        self.assertEqual(child.request.frontier_assignment.start_slot, 10)
        self.assertEqual(child.state, "queued")

    def test_continue_campaign_rejects_changed_source_without_creating_child(self) -> None:
        parent = replace(
            create_manifest(self._request()),
            state="completed",
            next_slot=10,
            chain_attempted_count=10,
            unsearched_count=90,
            feature_receipt_ids=("frpr_" + "d" * 64,),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, parent)
            with self.assertRaises(FrozenSourceVerificationError) as raised:
                continue_campaign(
                    parent.campaign_id,
                    root,
                    source_loader=lambda _source: self._verified_history("b" * 64),
                )
            restored_parent = read_campaign(parent.campaign_id, root)

        self.assertEqual(raised.exception.safe_error_code, "SOURCE.CHANGED")
        self.assertEqual(restored_parent, parent)

    def test_duplicate_submission_attaches_to_existing_campaign(self) -> None:
        request = self._request()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_campaign_id = submit_campaign(request, root)
            second_campaign_id = submit_campaign(request, root)
            manifest = read_campaign(first_campaign_id, root)

        self.assertEqual(second_campaign_id, first_campaign_id)
        self.assertEqual(manifest.state, "queued")
        self.assertEqual(manifest.lease_epoch, 0)

    def test_cancelled_queued_campaign_becomes_terminal_before_worker_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_id = submit_campaign(self._request(), root)
            request_cancel(campaign_id, root)
            manifest = read_campaign(campaign_id, root)

        self.assertEqual(manifest.state, "cancelled")
        self.assertEqual(manifest.lease_epoch, 0)

    def test_one_worker_lease_blocks_a_different_campaign(self) -> None:
        first_request = self._request()
        second_request = replace(first_request, per_ticker_budget=9)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_campaign_id = submit_campaign(first_request, root)
            second_campaign_id = submit_campaign(second_request, root)
            claimed = claim_campaign(first_campaign_id, root)

            with self.assertRaisesRegex(ValueError, "active campaign lease"):
                claim_campaign(second_campaign_id, root)

        self.assertEqual(claimed.state, "running")
        self.assertEqual(claimed.lease_epoch, 1)

    def test_releasing_matching_worker_lease_allows_next_campaign_claim(self) -> None:
        first_request = self._request()
        second_request = replace(first_request, per_ticker_budget=9)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_campaign_id = submit_campaign(first_request, root)
            second_campaign_id = submit_campaign(second_request, root)
            claim_campaign(first_campaign_id, root)
            release_campaign_lease(first_campaign_id, root)
            claimed_second = claim_campaign(second_campaign_id, root)

        self.assertEqual(claimed_second.state, "running")
        self.assertEqual(claimed_second.lease_epoch, 1)

    def test_stale_lease_marks_running_campaign_interrupted_and_releases_worker(self) -> None:
        now = pytz.timezone("Asia/Ho_Chi_Minh").localize(
            datetime(2026, 8, 27, 9, 0)
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_id = submit_campaign(self._request(), root)
            next_campaign_id = submit_campaign(
                replace(self._request(), per_ticker_budget=9), root
            )
            claim_campaign(campaign_id, root, now=now)
            recovered = recover_stale_lease(
                root,
                now=now + timedelta(seconds=61),
                stale_after_seconds=60,
            )
            claimed_next = claim_campaign(
                next_campaign_id, root, now=now + timedelta(seconds=62)
            )

        self.assertEqual(recovered.state, "interrupted")
        self.assertEqual(claimed_next.lease_epoch, 1)

    def test_heartbeat_prevents_premature_stale_recovery(self) -> None:
        now = pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9, 0))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_id = submit_campaign(self._request(), root)
            claim_campaign(campaign_id, root, now=now)
            heartbeat_campaign(campaign_id, root, now=now + timedelta(seconds=50))
            recovered = recover_stale_lease(
                root,
                now=now + timedelta(seconds=80),
                stale_after_seconds=60,
            )
            manifest = read_campaign(campaign_id, root)

        self.assertIsNone(recovered)
        self.assertEqual(manifest.state, "running")

    def test_resume_reuses_persisted_assignment_under_new_lease_epoch(self) -> None:
        now = pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9, 0))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_id = submit_campaign(self._request(), root)
            claimed = claim_campaign(campaign_id, root, now=now)
            recover_stale_lease(
                root,
                now=now + timedelta(seconds=61),
                stale_after_seconds=60,
            )
            resumed_campaign_id = resume_campaign(
                campaign_id, root, now=now + timedelta(seconds=62)
            )
            resumed = read_campaign(campaign_id, root)

        self.assertEqual(resumed_campaign_id, campaign_id)
        self.assertEqual(resumed.state, "running")
        self.assertEqual(resumed.lease_epoch, claimed.lease_epoch + 1)
        self.assertEqual(
            resumed.request.frontier_assignment,
            claimed.request.frontier_assignment,
        )

    def test_runner_persists_terminal_service_checkpoint_and_releases_lease(self) -> None:
        class CompletingService:
            def __init__(self) -> None:
                self.seen_campaign_id: str | None = None

            def run(self, manifest: object, *, verified_sources: tuple[HistorySnapshot, ...]) -> object:
                self.seen_campaign_id = getattr(manifest, "campaign_id")
                return transition(manifest, "completed")

        service = CompletingService()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_id = submit_campaign(self._request(), root)
            claim_campaign(campaign_id, root)
            completed = run_campaign(
                campaign_id,
                root,
                service,
                source_loader=lambda _source: self._verified_history(),
            )
            next_campaign_id = submit_campaign(
                replace(self._request(), per_ticker_budget=9), root
            )
            claimed_next = claim_campaign(next_campaign_id, root)

        self.assertEqual(service.seen_campaign_id, campaign_id)
        self.assertEqual(completed.state, "completed")
        self.assertEqual(claimed_next.state, "running")

    def test_runner_blocks_changed_source_before_service_and_releases_lease(self) -> None:
        class MustNotRunService:
            called = False

            def run(self, manifest: object, *, verified_sources: tuple[HistorySnapshot, ...]) -> object:
                self.called = True
                return transition(manifest, "completed")

        service = MustNotRunService()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign_id = submit_campaign(self._request(), root)
            claim_campaign(campaign_id, root)
            blocked = run_campaign(
                campaign_id,
                root,
                service,
                source_loader=lambda _source: self._verified_history("b" * 64),
            )
            next_campaign_id = submit_campaign(
                replace(self._request(), per_ticker_budget=9), root
            )
            claimed_next = claim_campaign(next_campaign_id, root)

        self.assertFalse(service.called)
        self.assertEqual(blocked.state, "blocked")
        self.assertEqual(blocked.safe_error_code, "SOURCE.CHANGED")
        self.assertEqual(blocked.next_slot, 0)
        self.assertEqual(claimed_next.state, "running")


if __name__ == "__main__":
    unittest.main()
