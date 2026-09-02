from datetime import date
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from dataclasses import replace
from flexible_rulebook.campaigns import CampaignRequest, create_manifest, write_campaign_manifest
from flexible_rulebook.contracts import (
    EvaluationPartition, EvaluationSplit, ExecutionContract, FeatureBuildContract,
    FeaturePlan, FeatureProfile, FeatureSnapshot, PrimitiveSpec, RuntimeBudget,
    SelectionPolicy, FeatureResolutionReceipt,
)
from flexible_rulebook.runner import (
    FrozenSourceVerificationError,
    WorkerWatchdogError,
    claim_campaign,
    classify_worker_fault,
    read_campaign,
    resume_campaign,
    start_campaign_worker,
    watch_campaign_worker,
)
from flexible_rulebook.history import HistorySnapshot
import pandas as pd
from flexible_rulebook.search import FrontierAssignment, StratumAssignment
from flexible_rulebook.worker import WorkerRequest, read_worker_request, resolve_callable, run_worker_request


class _HungProcess:
    def __init__(self) -> None:
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise subprocess.TimeoutExpired("worker", timeout)
        return 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class FlexibleRulebookWorkerTests(unittest.TestCase):
    def test_worker_request_contract_is_shared_across_module_entrypoints(self):
        """A ``python -m`` worker must not create a second request class identity."""

        from flexible_rulebook.worker_contract import WorkerRequest as SharedWorkerRequest
        from flexible_rulebook.worker import WorkerRequest as WorkerModuleRequest

        self.assertIs(SharedWorkerRequest, WorkerModuleRequest)

    @staticmethod
    def _request() -> CampaignRequest:
        source = FeatureSnapshot("VCB", "a" * 64, date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "eligible", "flexible-quality-v1")
        plan = FeaturePlan(source, FeatureBuildContract(), FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),)))
        assignment = FrontierAssignment("b" * 64, "candidate-space-v1", "frb-default-seed-v1", "VCB", 0, 1, (StratumAssignment("buy=rsi", 1, 1, 1, 0),), 1, 0)
        split = EvaluationSplit("calendar_10y_5y", date(2021, 1, 2), EvaluationPartition("training", date(2011, 1, 3), date(2021, 1, 1), 0, 99, 100), EvaluationPartition("test", date(2021, 1, 4), date(2026, 1, 2), 100, 149, 50))
        return CampaignRequest("discover", ("VCB",), (source,), "c" * 64, "flexible-engine-v1", (), (plan.build_contract.feature_build_contract_hash,), (plan.feature_plan_hash,), ExecutionContract(), split, RuntimeBudget(), SelectionPolicy(), 1, assignment)

    def test_worker_request_round_trip_is_atomic_json_contract(self):
        # Use the host platform's absolute temporary path; the same test runs
        # inside the Linux Docker image where a Windows drive path is relative.
        request = WorkerRequest(
            "fcmp_" + "a" * 64,
            Path(tempfile.gettempdir()) / "flexible",
            "flexible_rulebook.service:DiscoveryService",
            "flexible_rulebook.worker:main",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
            restored = read_worker_request(path.resolve())
        self.assertEqual(restored, request)

    def test_worker_rejects_application_bootstrap_callable(self):
        with self.assertRaisesRegex(ValueError, "not allowed"):
            resolve_callable("app.main:main")

    def test_worker_service_factory_receives_the_full_worker_request(self):
        request = WorkerRequest(
            "fcmp_" + "a" * 64,
            (Path(tempfile.gettempdir()) / "flexible").resolve(),
            "flexible_rulebook.service:DiscoveryService",
            "flexible_rulebook.worker:main",
        )
        factory = MagicMock(return_value=object())
        source_loader = MagicMock(return_value=object())
        with tempfile.TemporaryDirectory() as directory:
            path = (Path(directory) / "request.json").resolve()
            path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
            with (
                patch("flexible_rulebook.worker.resolve_callable", side_effect=(factory, source_loader)) as resolve,
                patch("flexible_rulebook.worker.run_campaign", return_value=object()),
            ):
                run_worker_request(path)

        self.assertEqual(resolve.call_args_list[0].args[0], request.service_ref)
        factory.assert_called_once_with(request)

    def test_watchdog_marks_live_campaign_interrupted_without_forging_terminal_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = create_manifest(self._request())
            write_campaign_manifest(root, manifest)
            running = claim_campaign(manifest.campaign_id, root)
            process = _HungProcess()
            result = watch_campaign_worker(process, running.campaign_id, root, watchdog_seconds=1)
            restored = read_campaign(running.campaign_id, root)
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)
        self.assertEqual(result.state, "interrupted")
        self.assertEqual(restored.state, "interrupted")

    @unittest.skipUnless(os.name == "posix", "process-group signaling is POSIX-only")
    def test_watchdog_terminates_the_requested_worker_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = create_manifest(self._request())
            write_campaign_manifest(root, manifest)
            running = claim_campaign(manifest.campaign_id, root)
            process = _HungProcess()
            process.pid = 4242
            with patch("flexible_rulebook.runner.os.killpg") as killpg:
                watch_campaign_worker(
                    process,
                    running.campaign_id,
                    root,
                    watchdog_seconds=1,
                    terminate_process_group=True,
                )

        killpg.assert_called_once_with(4242, signal.SIGTERM)

    def test_resume_requires_matching_frozen_receipt_before_new_lease(self):
        request = self._request()
        source = HistorySnapshot(
            "VCB",
            pd.DataFrame({"date": [date(2011, 1, 3), date(2026, 1, 2)], "open": [100, 110], "high": [101, 111], "low": [99, 109], "close": [100, 110], "volume": [1000, 1000]}),
            "a" * 64, "eligible", date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "a" * 64,
        )
        plan = FeaturePlan(request.source_snapshots[0], FeatureBuildContract(), FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),)))
        receipt = FeatureResolutionReceipt(plan, ((plan.primitive_keys[0].primitive_key, "d" * 64),))
        interrupted = replace(create_manifest(request), state="interrupted", feature_receipt_ids=(receipt.receipt_id,))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, interrupted)
            with self.assertRaisesRegex(ValueError, "receipt-bound"):
                resume_campaign(interrupted.campaign_id, root)
            resumed = resume_campaign(
                interrupted.campaign_id,
                root,
                source_loader=lambda _snapshot: source,
                receipt_resolver=lambda _source: receipt,
            )
            restored = read_campaign(interrupted.campaign_id, root)
        self.assertEqual(resumed, interrupted.campaign_id)
        self.assertEqual(restored.state, "running")

    def test_resume_rejects_different_receipt_without_claiming_lease(self):
        request = self._request()
        source = HistorySnapshot(
            "VCB",
            pd.DataFrame({"date": [date(2011, 1, 3), date(2026, 1, 2)], "open": [100, 110], "high": [101, 111], "low": [99, 109], "close": [100, 110], "volume": [1000, 1000]}),
            "a" * 64, "eligible", date(2011, 1, 3), date(2026, 1, 2), date(2011, 1, 3), date(2026, 1, 2), "a" * 64,
        )
        plan = FeaturePlan(request.source_snapshots[0], FeatureBuildContract(), FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),)))
        receipt = FeatureResolutionReceipt(plan, ((plan.primitive_keys[0].primitive_key, "d" * 64),))
        different = FeatureResolutionReceipt(plan, ((plan.primitive_keys[0].primitive_key, "e" * 64),))
        interrupted = replace(create_manifest(request), state="interrupted", feature_receipt_ids=(receipt.receipt_id,))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_manifest(root, interrupted)
            with self.assertRaisesRegex(ValueError, "persisted campaign receipt"):
                resume_campaign(
                    interrupted.campaign_id,
                    root,
                    source_loader=lambda _snapshot: source,
                    receipt_resolver=lambda _source: different,
                )
            restored = read_campaign(interrupted.campaign_id, root)
        self.assertEqual(restored.state, "interrupted")
        self.assertFalse((root / "campaigns" / "active-lease.json").exists())

    def test_start_worker_writes_only_serialized_request_and_module_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = create_manifest(self._request())
            write_campaign_manifest(root, manifest)
            claim_campaign(manifest.campaign_id, root)
            with patch("flexible_rulebook.runner.subprocess.Popen") as popen:
                process = start_campaign_worker(
                    manifest.campaign_id,
                    root,
                    service_ref="flexible_rulebook.service:DiscoveryService",
                    source_loader_ref="flexible_rulebook.worker:main",
                )
                command = popen.call_args.args[0]
            request_path = root / "campaigns" / manifest.campaign_id / "worker-request.json"
            payload = json.loads(request_path.read_text(encoding="utf-8"))
        self.assertIs(process, popen.return_value)
        self.assertEqual(command[:3], [sys.executable, "-m", "flexible_rulebook.worker"])
        self.assertEqual(payload["campaign_id"], manifest.campaign_id)

    def test_start_worker_can_isolate_a_process_group_for_cap_benchmarks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = create_manifest(self._request())
            write_campaign_manifest(root, manifest)
            claim_campaign(manifest.campaign_id, root)
            with patch("flexible_rulebook.runner.subprocess.Popen") as popen:
                start_campaign_worker(
                    manifest.campaign_id,
                    root,
                    service_ref="flexible_rulebook.service:DiscoveryService",
                    source_loader_ref="flexible_rulebook.worker:main",
                    process_group=True,
                )

        self.assertEqual(
            popen.call_args.kwargs["start_new_session"],
            os.name == "posix",
        )

    def test_fault_classification_keeps_shared_failure_out_of_item_data_states(self):
        source = classify_worker_fault(FrozenSourceVerificationError("SOURCE.CHANGED"))
        shared = classify_worker_fault(ConnectionError("database"), shared_scope=True)
        item = classify_worker_fault(TimeoutError("temporary"))
        watchdog = classify_worker_fault(WorkerWatchdogError())
        self.assertEqual((source.kind, source.safe_error_code, source.campaign_blocking), ("source", "SOURCE.CHANGED", True))
        self.assertEqual((shared.kind, shared.safe_error_code, shared.retryable), ("shared", "INFRA.SHARED_UNAVAILABLE", False))
        self.assertEqual((item.kind, item.safe_error_code, item.retryable), ("item_transient", "INFRA.ITEM_TRANSIENT", True))
        self.assertEqual((watchdog.kind, watchdog.safe_error_code), ("watchdog", "INFRA.WATCHDOG_TIMEOUT"))


if __name__ == "__main__":
    unittest.main()
