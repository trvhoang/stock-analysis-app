"""Read-only Flexible Rulebook production-benchmark runner tests."""

from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest

import pandas as pd
import pytz

from flexible_rulebook.benchmark_runner import (
    BenchmarkExecution,
    BenchmarkSampleRequest,
    BenchmarkSampleRuntime,
    prepare_warm_sample_cache,
    run_production_benchmark,
    run_benchmark_sample,
    validate_benchmark_output_path,
)
from flexible_rulebook.benchmark import BenchmarkSample, read_production_benchmark_report
from flexible_rulebook.catalog import catalog_revision_1, feature_profile
from flexible_rulebook.campaigns import create_manifest, transition
from flexible_rulebook.features import resolve_feature_store
from flexible_rulebook.history import HistorySnapshot
from flexible_rulebook.storage import resolve_flexible_root


_HCM = pytz.timezone("Asia/Ho_Chi_Minh")


def _history(*, fingerprint="a" * 64) -> HistorySnapshot:
    dates = [date(2011, 1, 3), date(2020, 12, 31), date(2021, 1, 4), date(2026, 1, 2)]
    return HistorySnapshot(
        ticker="VCB",
        frame=pd.DataFrame({
            "date": dates,
            "open": [100_000, 101_000, 102_000, 103_000],
            "high": [101_000, 102_000, 103_000, 104_000],
            "low": [99_000, 100_000, 101_000, 102_000],
            "close": [100_500, 101_500, 102_500, 103_500],
            "volume": [1_000, 1_100, 1_200, 1_300],
        }),
        fingerprint=fingerprint,
        quality_state="eligible",
        requested_start=date(2011, 1, 2),
        requested_as_of=date(2026, 1, 2),
        first_date=dates[0],
        as_of_date=dates[-1],
        evidence_prefix_fingerprint=fingerprint,
    )


class FlexibleRulebookBenchmarkRunnerTests(unittest.TestCase):
    def _runtime(self, *, events, worker_fingerprint=None):
        catalog = catalog_revision_1()

        def load_history(ticker, as_of):
            events.append(("load", ticker, as_of))
            return _history()

        def resolve(snapshot, contract, profile, root, choice):
            events.append(("resolve", choice))
            return resolve_feature_store(
                snapshot,
                contract,
                profile,
                root,
                choice="rebuild",
                now=datetime.now(_HCM),
            )

        def execute(request, root):
            events.append(("worker", request.frontier_assignment.start_slot))
            manifest = transition(transition(create_manifest(request), "running"), "completed")
            return BenchmarkExecution(
                manifest=manifest,
                training_seconds=0.0,
                test_seconds=0.0,
                selection_seconds=0.0,
                write_seconds=0.0,
                reached_maximal_path=True,
                worker_source_fingerprint=worker_fingerprint or request.source_snapshots[0].raw_history_fingerprint,
            )

        return BenchmarkSampleRuntime(
            catalog=catalog,
            history_loader=load_history,
            feature_resolver=resolve,
            campaign_executor=execute,
            cache_is_complete=lambda *_args: True,
            monotonic=lambda: 1.0,
            rss_probe=lambda: 1024,
            pool_checkout_probe=lambda: 1,
        )

    def test_runner_rejects_relative_or_production_root_output_path(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            validate_benchmark_output_path(Path("report.json"))

        production = resolve_flexible_root() / "report.json"
        with self.assertRaisesRegex(ValueError, "Flexible Rulebook evidence root"):
            validate_benchmark_output_path(production)

    def test_cold_sample_uses_rebuild_and_never_uses_production_root(self):
        events = []
        runtime = self._runtime(events=events)
        request = BenchmarkSampleRequest("VCB", date(2026, 1, 2), "frb-default-seed-v1", 0, "cold")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            sample = run_benchmark_sample(request, root, runtime=runtime)

        self.assertEqual(sample.mode, "cold")
        self.assertEqual(sample.terminal_state, "completed")
        self.assertEqual(events[:3], [("load", "VCB", date(2026, 1, 2)), ("resolve", "rebuild"), ("worker", 0)])
        self.assertNotIn("Flexible-Rulebook", str(root))

    def test_warm_prepopulation_is_unmeasured_then_fresh_load_uses_reuse(self):
        events = []
        runtime = self._runtime(events=events)
        request = BenchmarkSampleRequest("VCB", date(2026, 1, 2), "frb-default-seed-v1", 0, "warm")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            prepare_warm_sample_cache(request, root, runtime=runtime)
            events.clear()
            sample = run_benchmark_sample(request, root, runtime=runtime)

        self.assertEqual(sample.mode, "warm")
        self.assertEqual(events[:3], [("load", "VCB", date(2026, 1, 2)), ("resolve", "reuse"), ("worker", 0)])

    def test_warm_source_change_after_unmeasured_prepopulation_is_not_reused(self):
        events = []
        runtime = self._runtime(events=events)
        snapshots = iter((_history(fingerprint="a" * 64), _history(fingerprint="b" * 64)))
        runtime = replace(runtime, history_loader=lambda _ticker, _as_of: next(snapshots))
        request = BenchmarkSampleRequest("VCB", date(2026, 1, 2), "frb-default-seed-v1", 0, "warm")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            prepare_warm_sample_cache(request, root, runtime=runtime)
            sample = run_benchmark_sample(request, root, runtime=runtime)

        self.assertFalse(sample.is_complete)
        self.assertEqual(sample.safe_error_code, "SOURCE.CHANGED")

    def test_worker_source_change_is_recorded_as_incomplete_not_success(self):
        events = []
        runtime = self._runtime(events=events, worker_fingerprint="b" * 64)
        request = BenchmarkSampleRequest("VCB", date(2026, 1, 2), "frb-default-seed-v1", 0, "cold")
        with tempfile.TemporaryDirectory() as directory:
            sample = run_benchmark_sample(request, Path(directory).resolve(), runtime=runtime)

        self.assertFalse(sample.is_complete)
        self.assertEqual(sample.safe_error_code, "SOURCE.CHANGED")

    def test_interrupted_worker_keeps_missing_phase_times_as_none_not_zero(self):
        events = []
        runtime = self._runtime(events=events)

        def interrupted(request, _root):
            manifest = transition(transition(create_manifest(request), "running"), "interrupted")
            return BenchmarkExecution(
                manifest=manifest,
                training_seconds=None,
                test_seconds=None,
                selection_seconds=None,
                write_seconds=None,
                reached_maximal_path=False,
                worker_source_fingerprint=None,
            )

        runtime = replace(runtime, campaign_executor=interrupted)
        request = BenchmarkSampleRequest("VCB", date(2026, 1, 2), "frb-default-seed-v1", 0, "cold")
        with tempfile.TemporaryDirectory() as directory:
            sample = run_benchmark_sample(request, Path(directory).resolve(), runtime=runtime)

        self.assertEqual(sample.terminal_state, "interrupted")
        self.assertIsNone(sample.training_seconds)
        self.assertIsNone(sample.test_seconds)
        self.assertFalse(sample.is_complete)

    def test_batch_writes_ineligible_evidence_without_authorizing_discovery(self):
        def sample_runner(request):
            return BenchmarkSample(
                ticker=request.ticker,
                seed=request.seed,
                global_slot=request.global_slot,
                canonical_index=request.global_slot,
                frontier_stratum="fast-first",
                split_identity="{}",
                mode=request.mode,
                source_fingerprint="a" * 64,
                preflight_seconds=1.0,
                training_seconds=1.0,
                test_seconds=1.0,
                selection_seconds=1.0,
                write_seconds=1.0,
                maximal_slot_seconds=4.0,
                terminal_state="completed",
                safe_error_code=None,
                reached_maximal_path=True,
                peak_rss_bytes=1024,
                peak_pool_checkouts=1,
                cache_bytes=512,
                artifact_bytes=256,
            )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / "report.json"
            report = run_production_benchmark(
                tickers=("VCB",),
                as_of=date(2026, 1, 2),
                seeds=("frb-default-seed-v1",),
                cold_samples=1,
                warm_samples=0,
                output=output,
                sample_runner=sample_runner,
            )

            self.assertFalse(report.is_discovery_eligible)
            self.assertEqual(read_production_benchmark_report(output), report)

    def test_ticker_budget_marks_unstarted_slots_incomplete_before_five_hours(self):
        calls = []
        clock_values = iter((0.0, 0.0, 17_701.0))

        def sample_runner(request):
            calls.append(request.global_slot)
            return BenchmarkSample(
                ticker=request.ticker,
                seed=request.seed,
                global_slot=request.global_slot,
                canonical_index=request.global_slot,
                frontier_stratum="fast-first",
                split_identity="{}",
                mode=request.mode,
                source_fingerprint="a" * 64,
                preflight_seconds=1.0,
                training_seconds=1.0,
                test_seconds=1.0,
                selection_seconds=1.0,
                write_seconds=1.0,
                maximal_slot_seconds=4.0,
                terminal_state="completed",
                safe_error_code=None,
                reached_maximal_path=True,
                peak_rss_bytes=1024,
                peak_pool_checkouts=1,
                cache_bytes=512,
                artifact_bytes=256,
            )

        with tempfile.TemporaryDirectory() as directory:
            report = run_production_benchmark(
                tickers=("VCB",),
                as_of=date(2026, 1, 2),
                seeds=("frb-default-seed-v1",),
                cold_samples=2,
                warm_samples=0,
                output=Path(directory).resolve() / "report.json",
                sample_runner=sample_runner,
                monotonic=lambda: next(clock_values),
            )

        self.assertEqual(calls, [0])
        self.assertEqual(report.samples[1].safe_error_code, "BENCHMARK.TICKER_BUDGET_EXHAUSTED")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
