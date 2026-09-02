"""Read-only isolated fixed-cap benchmark runner tests."""

from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from flexible_rulebook.cap_benchmark import read_cap_benchmark_report, validate_cap_report
from flexible_rulebook.cap_benchmark_runner import (
    CapBenchmarkRuntime,
    main,
    production_cap_runtime,
    run_cap_benchmark,
    run_cap_window,
)
from flexible_rulebook.catalog import catalog_revision_1, feature_profile
from flexible_rulebook.campaigns import create_manifest, transition
from flexible_rulebook.contracts import FeatureBuildContract, FeaturePlan, FeatureResolutionReceipt
from flexible_rulebook.features import FeatureResolution, feature_snapshot_for_history
from flexible_rulebook.history import HistorySnapshot
from flexible_rulebook.storage import resolve_flexible_root


_AS_OF = date(2026, 1, 2)
_SEED = "frb-default-seed-v1"
_CAP = 8


def _history() -> HistorySnapshot:
    dates = [date(2011, 1, 3), date(2020, 12, 31), date(2021, 1, 4), _AS_OF]
    return HistorySnapshot(
        ticker="VCB",
        frame=pd.DataFrame(
            {
                "date": dates,
                "open": [100_000, 101_000, 102_000, 103_000],
                "high": [101_000, 102_000, 103_000, 104_000],
                "low": [99_000, 100_000, 101_000, 102_000],
                "close": [100_500, 101_500, 102_500, 103_500],
                "volume": [1_000, 1_100, 1_200, 1_300],
            }
        ),
        fingerprint="a" * 64,
        quality_state="eligible",
        requested_start=date(2011, 1, 2),
        requested_as_of=_AS_OF,
        first_date=dates[0],
        as_of_date=dates[-1],
        evidence_prefix_fingerprint="a" * 64,
    )


def _completed_manifest(request):
    assignment = request.frontier_assignment
    assert assignment is not None
    manifest = transition(transition(create_manifest(request), "running"), "completed")
    next_slot = assignment.start_slot + assignment.attempt_count
    return replace(
        manifest,
        next_slot=next_slot,
        chain_attempted_count=next_slot,
        unsearched_count=sum(item.size for item in assignment.strata) - next_slot,
    )


class FlexibleRulebookCapBenchmarkRunnerTests(unittest.TestCase):
    def _runtime(self, events):
        catalog = catalog_revision_1()
        contract = FeatureBuildContract()
        snapshot = _history()
        profile = feature_profile(catalog)
        plan = FeaturePlan(feature_snapshot_for_history(snapshot), contract, profile)
        resolution = FeatureResolution(
            store=object(),
            plan=plan,
            receipt=FeatureResolutionReceipt(
                plan,
                tuple((key.primitive_key, "b" * 64) for key in plan.primitive_keys),
            ),
        )

        def history_loader(ticker, as_of):
            events.append(("load", ticker, as_of))
            return snapshot

        def feature_resolver(_snapshot, _contract, _profile, root, choice):
            events.append(("features", choice, root))
            return resolution

        def campaign_executor(request, root):
            events.append(
                (
                    "worker",
                    request.frontier_assignment.start_slot,
                    request.frontier_assignment.attempt_count,
                    request.per_ticker_budget,
                    root,
                )
            )
            return _completed_manifest(request)

        return CapBenchmarkRuntime(
            catalog=catalog,
            history_loader=history_loader,
            feature_resolver=feature_resolver,
            campaign_executor=campaign_executor,
            cache_is_complete=lambda *_args: True,
            monotonic=lambda: 0.0,
            rss_probe=lambda: 1024,
            pool_checkout_probe=lambda: 1,
            build_contract=contract,
        )

    def test_cold_samples_cover_disjoint_deterministic_cap_windows(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / "cap-report.json"
            report = run_cap_benchmark(
                tickers=("VCB",),
                as_of=_AS_OF,
                seeds=(_SEED,),
                cap_attempts=_CAP,
                cold_samples=100,
                output=output,
                runtime=self._runtime(events),
            )

            self.assertEqual(read_cap_benchmark_report(output), report)

        cold = report.cold_samples("VCB", _SEED)
        self.assertEqual([sample.start_slot for sample in cold], [index * _CAP for index in range(100)])
        self.assertTrue(all(sample.is_complete_cold_window for sample in cold))
        self.assertEqual(
            [event[1] for event in events if event[0] == "worker"],
            [index * _CAP for index in range(100)],
        )

    def test_progress_callback_reports_monotonic_window_completion(self):
        events = []
        progress = []
        with tempfile.TemporaryDirectory() as directory:
            run_cap_benchmark(
                tickers=("VCB",),
                as_of=_AS_OF,
                seeds=(_SEED,),
                cap_attempts=_CAP,
                cold_samples=100,
                output=Path(directory).resolve() / "cap-report.json",
                runtime=self._runtime(events),
                progress_fn=progress.append,
            )

        self.assertEqual(len(progress), 100)
        self.assertEqual([event.completed for event in progress], list(range(1, 101)))
        self.assertTrue(all(event.total == 100 for event in progress))
        self.assertTrue(all(event.phase == "benchmark" for event in progress))

    def test_each_cold_sample_uses_one_exact_cap_campaign_in_a_fresh_isolated_root(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            run_cap_benchmark(
                tickers=("VCB",),
                as_of=_AS_OF,
                seeds=(_SEED,),
                cap_attempts=_CAP,
                cold_samples=100,
                output=Path(directory).resolve() / "cap-report.json",
                runtime=self._runtime(events),
            )

        worker_events = [event for event in events if event[0] == "worker"]
        roots = [event[4] for event in worker_events]
        self.assertTrue(all(event[2:4] == (_CAP, _CAP) for event in worker_events))
        self.assertEqual(len({str(root) for root in roots}), 100)
        self.assertTrue(
            all(resolve_flexible_root().resolve() not in root.resolve().parents for root in roots)
        )

    def test_ticker_budget_records_truthful_unstarted_windows_and_writes_report(self):
        events = []

        def coordinator_clock():
            return 0.0 if not any(event[0] == "worker" for event in events) else 2.0

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / "cap-report.json"
            report = run_cap_benchmark(
                tickers=("VCB",),
                as_of=_AS_OF,
                seeds=(_SEED,),
                cap_attempts=_CAP,
                cold_samples=100,
                output=output,
                ticker_budget_seconds=1,
                runtime=self._runtime(events),
                monotonic=coordinator_clock,
            )

            self.assertEqual(read_cap_benchmark_report(output), report)

        self.assertEqual(len([event for event in events if event[0] == "worker"]), 1)
        self.assertEqual(
            [sample.safe_error_code for sample in report.cold_samples("VCB", _SEED)[1:]],
            ["BENCHMARK.TICKER_BUDGET_EXHAUSTED"] * 99,
        )
        with self.assertRaisesRegex(ValueError, "exactly complete"):
            validate_cap_report(report)

    def test_warm_window_prepopulates_then_fresh_reuses_its_isolated_cache(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            sample = run_cap_window(
                ticker="VCB",
                as_of=_AS_OF,
                seed=_SEED,
                mode="warm",
                sample_index=0,
                cap_attempts=_CAP,
                root=Path(directory).resolve(),
                runtime=self._runtime(events),
            )

        self.assertEqual(sample.mode, "warm")
        self.assertEqual(sample.terminal_state, "completed")
        self.assertEqual(
            [event[1] for event in events if event[0] == "features"],
            ["rebuild", "reuse"],
        )
        self.assertEqual(
            len([event for event in events if event[0] == "load"]),
            2,
        )

    def test_warm_source_change_is_blocked_without_reusing_the_prepopulated_cache(self):
        events = []
        runtime = self._runtime(events)
        first, changed = _history(), _history()
        changed = HistorySnapshot(
            ticker=changed.ticker,
            frame=changed.frame,
            fingerprint="c" * 64,
            quality_state=changed.quality_state,
            requested_start=changed.requested_start,
            requested_as_of=changed.requested_as_of,
            first_date=changed.first_date,
            as_of_date=changed.as_of_date,
            evidence_prefix_fingerprint="c" * 64,
        )
        snapshots = iter((first, changed))
        runtime = replace(runtime, history_loader=lambda _ticker, _as_of: next(snapshots))

        with tempfile.TemporaryDirectory() as directory:
            sample = run_cap_window(
                ticker="VCB",
                as_of=_AS_OF,
                seed=_SEED,
                mode="warm",
                sample_index=0,
                cap_attempts=_CAP,
                root=Path(directory).resolve(),
                runtime=runtime,
            )

        self.assertEqual(
            (sample.terminal_state, sample.safe_error_code),
            ("blocked", "SOURCE.CHANGED"),
        )
        self.assertEqual(
            [event[1] for event in events if event[0] == "features"],
            ["rebuild"],
        )

    def test_partial_window_keeps_completed_count_and_uncommitted_slot_truthful(self):
        events = []
        runtime = self._runtime(events)

        def interrupted(request, _root):
            assignment = request.frontier_assignment
            assert assignment is not None
            manifest = transition(transition(create_manifest(request), "running"), "interrupted")
            next_slot = assignment.start_slot + 1
            return replace(
                manifest,
                next_slot=next_slot,
                chain_attempted_count=next_slot,
                uncommitted_slot=next_slot,
                unsearched_count=sum(item.size for item in assignment.strata) - next_slot,
            )

        with tempfile.TemporaryDirectory() as directory:
            sample = run_cap_window(
                ticker="VCB",
                as_of=_AS_OF,
                seed=_SEED,
                mode="cold",
                sample_index=1,
                cap_attempts=_CAP,
                root=Path(directory).resolve(),
                runtime=replace(runtime, campaign_executor=interrupted),
            )

        self.assertEqual(
            (sample.terminal_state, sample.attempted_count, sample.committed_count, sample.next_slot, sample.uncommitted_slot),
            ("interrupted", 1, 1, _CAP + 1, _CAP + 1),
        )
        self.assertFalse(sample.is_complete_cold_window)

    def test_source_preflight_failure_records_no_fabricated_anchor(self):
        events = []
        runtime = replace(
            self._runtime(events),
            history_loader=lambda _ticker, _as_of: (_ for _ in ()).throw(ConnectionError("offline")),
        )
        with tempfile.TemporaryDirectory() as directory:
            sample = run_cap_window(
                ticker="VCB",
                as_of=_AS_OF,
                seed=_SEED,
                mode="cold",
                sample_index=0,
                cap_attempts=_CAP,
                root=Path(directory).resolve(),
                runtime=runtime,
            )

        self.assertEqual(
            (sample.terminal_state, sample.safe_error_code, sample.source_identity, sample.split_identity),
            ("blocked", "SOURCE.UNAVAILABLE", None, None),
        )

    def test_window_reads_only_worker_persisted_slot_and_window_timings(self):
        events = []
        runtime = self._runtime(events)

        def timed(request, root):
            (root / ".flexible-cap-benchmark-phases-v1.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "flexible_rulebook_cap_benchmark_phases",
                        "slot_timings": [
                            {"global_slot": 0, "phase": "entry_mask", "seconds": 0.1},
                            {"global_slot": 0, "phase": "training", "seconds": 0.2},
                        ],
                        "window_timings": [
                            {"phase": "selection", "seconds": 0.3},
                            {"phase": "write", "seconds": 0.4},
                        ],
                        "peak_rss_bytes": 2048,
                    }
                ),
                encoding="utf-8",
            )
            return _completed_manifest(request)

        with tempfile.TemporaryDirectory() as directory:
            sample = run_cap_window(
                ticker="VCB",
                as_of=_AS_OF,
                seed=_SEED,
                mode="cold",
                sample_index=0,
                cap_attempts=_CAP,
                root=Path(directory).resolve(),
                runtime=replace(runtime, campaign_executor=timed),
            )

        self.assertEqual(
            [(event.global_slot, event.phase, event.seconds) for event in sample.slot_timings],
            [(0, "entry_mask", 0.1), (0, "training", 0.2)],
        )
        self.assertEqual((sample.selection_seconds, sample.write_seconds), (0.3, 0.4))
        self.assertEqual(sample.peak_rss_bytes, 2048)

    def test_window_hands_the_serial_remaining_deadline_to_the_worker(self):
        events = []
        runtime = self._runtime(events)
        received_deadlines = []

        def execute(request, root):
            payload = json.loads(
                (root / ".flexible-cap-benchmark-deadline-v1.json").read_text(
                    encoding="utf-8"
                )
            )
            received_deadlines.append(payload["remaining_seconds"])
            return _completed_manifest(request)

        with tempfile.TemporaryDirectory() as directory:
            run_cap_window(
                ticker="VCB",
                as_of=_AS_OF,
                seed=_SEED,
                mode="cold",
                sample_index=0,
                cap_attempts=_CAP,
                root=Path(directory).resolve(),
                runtime=replace(runtime, campaign_executor=execute),
                remaining_seconds=lambda: 37,
            )

        self.assertEqual(received_deadlines, [37])

    def test_production_window_uses_the_real_fresh_source_loader_and_group_watchdog(self):
        events = []
        base_runtime = self._runtime(events)
        seen_requests = []
        with patch(
            "flexible_rulebook.cap_benchmark_runner.production_sample_runtime",
            return_value=base_runtime,
        ), patch(
            "flexible_rulebook.runner.submit_campaign",
            side_effect=lambda request, _root: seen_requests.append(request) or "fcmp_" + "a" * 64,
        ), patch(
            "flexible_rulebook.runner.claim_campaign",
        ), patch(
            "flexible_rulebook.runner.start_campaign_worker",
            return_value=Mock(),
        ) as start_worker, patch(
            "flexible_rulebook.runner.watch_campaign_worker",
            side_effect=lambda *_args, **_kwargs: _completed_manifest(seen_requests[0]),
        ) as watch_worker:
            runtime = production_cap_runtime()
            with tempfile.TemporaryDirectory() as directory:
                sample = run_cap_window(
                    ticker="VCB",
                    as_of=_AS_OF,
                    seed=_SEED,
                    mode="cold",
                    sample_index=0,
                    cap_attempts=_CAP,
                    root=Path(directory).resolve(),
                    runtime=runtime,
                    remaining_seconds=lambda: 37,
                )

        self.assertEqual(sample.terminal_state, "completed")
        self.assertEqual(
            start_worker.call_args.kwargs["source_loader_ref"],
            "flexible_rulebook.benchmark_runner:benchmark_source_loader",
        )
        self.assertTrue(start_worker.call_args.kwargs["process_group"])
        self.assertTrue(watch_worker.call_args.kwargs["terminate_process_group"])
        self.assertEqual(watch_worker.call_args.kwargs["watchdog_seconds"], 37)

    def test_cli_returns_two_after_writing_truthful_ineligible_evidence(self):
        with patch(
            "flexible_rulebook.cap_benchmark_runner.run_cap_benchmark",
            return_value=Mock(is_eligible=False),
        ):
            result = main(
                [
                    "--tickers",
                    "VCB",
                    "--as-of",
                    _AS_OF.isoformat(),
                    "--seed",
                    _SEED,
                    "--cap-attempts",
                    str(_CAP),
                    "--cold-samples",
                    "100",
                    "--output",
                    "/tmp/cap-report.json",
                ]
            )

        self.assertEqual(result, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
