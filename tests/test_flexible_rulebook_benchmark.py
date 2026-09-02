from dataclasses import replace
from datetime import date
import unittest

from flexible_rulebook.benchmark import (
    BenchmarkRecord,
    BenchmarkSample,
    ProductionBenchmarkReport,
    ScalePolicy,
    benchmark_record_from_report,
    read_production_benchmark_report,
    validate_scale_policy,
    write_production_benchmark_report,
)


def _record(**overrides):
    values = {
        "benchmark_report_hash": "a" * 64,
        "scope": "combined",
        "completed": True,
        "measured_current_scan_ticker_counts": (20, 100, 200),
        "measured_discovery_attempt_caps": (100,),
        "worker_counts": (1, 2),
        "maximal_slot_sample_count": 100,
        "cold_p99_preflight_seconds": 120.0,
        "cold_p99_training_seconds": 20.0,
        "cold_p99_test_seconds": 30.0,
        "cold_p99_selection_seconds": 5.0,
        "cold_p99_write_seconds": 5.0,
        "cold_p99_maximal_slot_seconds": 60.0,
        "cold_p99_total_seconds": 180.0,
        "reference_fast_parity": True,
        "fast_executor_improvement": 0.0,
        "append_prefix_parity": True,
        "append_full_rebuild_parity": True,
        "append_extension_improvement": 0.0,
    }
    values.update(overrides)
    return BenchmarkRecord(**values)


def _sample(
    *,
    ticker="FPT",
    mode="cold",
    slot=0,
    source_fingerprint="c" * 64,
    preflight_seconds=2.0,
    maximal_slot_seconds=5.0,
    terminal_state="completed",
    safe_error_code=None,
    frontier_stratum="fast-first",
    reached_maximal_path=True,
):
    return BenchmarkSample(
        ticker=ticker,
        seed="frb-default-seed-v1",
        global_slot=slot,
        canonical_index=slot,
        mode=mode,
        source_fingerprint=source_fingerprint,
        preflight_seconds=preflight_seconds,
        training_seconds=1.0,
        test_seconds=1.0,
        selection_seconds=0.5,
        write_seconds=0.5,
        maximal_slot_seconds=maximal_slot_seconds,
        terminal_state=terminal_state,
        safe_error_code=safe_error_code,
        frontier_stratum=frontier_stratum,
        reached_maximal_path=reached_maximal_path,
        peak_rss_bytes=1024,
        peak_pool_checkouts=1,
        cache_bytes=512,
        artifact_bytes=256,
    )


def _report(*, tickers=("FPT",), samples=()):
    return ProductionBenchmarkReport(
        as_of=date(2026, 8, 28),
        tickers=tickers,
        seeds=("frb-default-seed-v1",),
        catalog_hash="d" * 64,
        feature_build_contract_hash="frbc_" + "e" * 64,
        candidate_space_hash="f" * 64,
        split_identity='{"method":"calendar_10y_5y"}',
        execution_contract_identity='{"execution_revision":"flexible-execution-v1"}',
        samples=samples,
    )


class FlexibleRulebookBenchmarkTests(unittest.TestCase):
    def test_safe_default_policy_is_valid_without_measurement(self):
        validate_scale_policy(ScalePolicy(), None)

    def test_measured_discovery_cap_can_pass_when_all_headroom_rules_hold(self):
        policy = ScalePolicy(max_discovery_attempt_count=100, benchmark_report_hash="a" * 64)
        validate_scale_policy(
            policy,
            _record(scope="discovery", measured_discovery_attempt_caps=(100,)),
        )

    def test_default_policy_rejects_group_larger_than_fifteen(self):
        policy = ScalePolicy(max_current_scan_tickers=16)
        with self.assertRaisesRegex(ValueError, "15"):
            validate_scale_policy(policy, None)

    def test_policy_requires_matching_completed_benchmark_hash_for_two_workers(self):
        policy = ScalePolicy(worker_count=2, benchmark_report_hash="b" * 64)
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_scale_policy(policy, _record(benchmark_report_hash="a" * 64))
        with self.assertRaisesRegex(ValueError, "completed"):
            validate_scale_policy(policy, _record(benchmark_report_hash="b" * 64, completed=False))

    def test_discovery_policy_never_allows_more_than_fifteen_without_separate_record(self):
        policy = ScalePolicy(max_discovery_attempt_count=16, benchmark_report_hash="a" * 64)
        with self.assertRaisesRegex(ValueError, "discovery"):
            validate_scale_policy(policy, _record(scope="current_scan"))

    def test_discovery_policy_requires_cold_p99_proof_for_fixed_attempt_cap(self):
        policy = ScalePolicy(max_discovery_attempt_count=10, benchmark_report_hash="a" * 64)
        with self.assertRaisesRegex(ValueError, "p99"):
            validate_scale_policy(policy, _record(maximal_slot_sample_count=99, cold_p99_maximal_slot_seconds=None))

    def test_discovery_cap_uses_maximal_train_test_write_slot_not_training_only_mean(self):
        policy = ScalePolicy(max_discovery_attempt_count=200, benchmark_report_hash="a" * 64)
        with self.assertRaisesRegex(ValueError, "maximal"):
            validate_scale_policy(policy, _record(cold_p99_maximal_slot_seconds=10.0, cold_p99_training_seconds=20.0))

    def test_discovery_cap_subtracts_cold_preflight_and_requires_one_hundred_maximal_slots(self):
        policy = ScalePolicy(max_discovery_attempt_count=300, benchmark_report_hash="a" * 64)
        with self.assertRaisesRegex(ValueError, "100"):
            validate_scale_policy(policy, _record(maximal_slot_sample_count=99, cold_p99_preflight_seconds=16_100, cold_p99_maximal_slot_seconds=100.0))

    def test_policy_rejects_if_p99_cannot_finish_before_admission_and_terminal_deadlines(self):
        policy = ScalePolicy(max_discovery_attempt_count=1, benchmark_report_hash="a" * 64)
        with self.assertRaisesRegex(ValueError, "deadline"):
            validate_scale_policy(policy, _record(cold_p99_preflight_seconds=16_190, cold_p99_test_seconds=10.0, cold_p99_maximal_slot_seconds=20.0))

    def test_fast_executor_cannot_enable_without_reference_parity_record(self):
        policy = ScalePolicy(enable_fast_executor=True, benchmark_report_hash="a" * 64)
        with self.assertRaisesRegex(ValueError, "parity"):
            validate_scale_policy(policy, _record(reference_fast_parity=False))

    def test_append_extension_cannot_enable_without_prefix_and_full_rebuild_parity_record(self):
        policy = ScalePolicy(enable_append_extension=True, benchmark_report_hash="a" * 64)
        with self.assertRaisesRegex(ValueError, "append"):
            validate_scale_policy(policy, _record(append_prefix_parity=False, append_full_rebuild_parity=False))

    def test_production_report_round_trips_only_when_digest_matches(self):
        samples = tuple(_sample(slot=slot) for slot in range(100))
        report = _report(samples=samples)
        with self.subTest("round trip"):
            from tempfile import TemporaryDirectory
            from pathlib import Path

            with TemporaryDirectory() as directory:
                path = Path(directory) / "report.json"
                write_production_benchmark_report(path, report)
                self.assertEqual(read_production_benchmark_report(path), report)
                path.write_text(path.read_text(encoding="utf-8").replace("FPT", "VCB", 1), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "digest"):
                    read_production_benchmark_report(path)

    def test_report_with_one_failed_cold_sample_is_ineligible(self):
        samples = tuple(_sample(slot=slot) for slot in range(100)) + (
            _sample(slot=100, terminal_state="failed", safe_error_code="INFRA.WORKER_CONTRACT"),
        )
        report = _report(samples=samples)
        self.assertFalse(report.is_discovery_eligible)
        with self.assertRaisesRegex(ValueError, "ineligible"):
            benchmark_record_from_report(report)

    def test_report_requires_one_hundred_completed_cold_samples_per_ticker(self):
        report = _report(samples=tuple(_sample(slot=slot) for slot in range(99)))
        self.assertFalse(report.is_discovery_eligible)
        with self.assertRaisesRegex(ValueError, "100"):
            benchmark_record_from_report(report)

    def test_report_summary_uses_worst_ticker_cold_p99(self):
        samples = (
            *( _sample(ticker="FPT", slot=slot, preflight_seconds=1.0, maximal_slot_seconds=3.0) for slot in range(100) ),
            *( _sample(ticker="VCB", slot=slot, preflight_seconds=2.0, maximal_slot_seconds=7.0) for slot in range(100) ),
        )
        record = benchmark_record_from_report(_report(tickers=("FPT", "VCB"), samples=samples))
        self.assertEqual(record.scope, "discovery")
        self.assertEqual(record.cold_p99_preflight_seconds, 2.0)
        self.assertEqual(record.cold_p99_maximal_slot_seconds, 7.0)
        self.assertEqual(record.measured_discovery_attempt_caps, ())

    def test_one_slot_report_summary_cannot_authorize_a_discovery_cap(self):
        report = _report(samples=tuple(_sample(slot=slot) for slot in range(100)))
        record = benchmark_record_from_report(report)
        policy = ScalePolicy(
            max_discovery_attempt_count=1,
            benchmark_report_hash=record.benchmark_report_hash,
        )
        with self.assertRaisesRegex(ValueError, "matching measured"):
            validate_scale_policy(policy, record)

    def test_report_rejects_noncanonical_execution_identity(self):
        with self.assertRaisesRegex(ValueError, "canonical JSON"):
            ProductionBenchmarkReport(
                as_of=date(2026, 8, 28),
                tickers=("FPT",),
                seeds=("frb-default-seed-v1",),
                catalog_hash="d" * 64,
                feature_build_contract_hash="frbc_" + "e" * 64,
                candidate_space_hash="f" * 64,
                split_identity='{ "method": "calendar_10y_5y" }',
                execution_contract_identity='{"execution_revision":"flexible-execution-v1"}',
                samples=(),
            )

    def test_source_fingerprint_change_makes_report_ineligible(self):
        samples = tuple(_sample(slot=slot) for slot in range(100)) + (
            _sample(slot=100, source_fingerprint="a" * 64),
        )
        self.assertFalse(_report(samples=samples).is_discovery_eligible)

    def test_report_reader_does_not_create_missing_parent_directory(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "does-not-exist" / "report.json"
            with self.assertRaisesRegex(ValueError, "unreadable"):
                read_production_benchmark_report(path)
            self.assertFalse(path.parent.exists())

    def test_early_training_only_slot_is_not_maximal_proof(self):
        samples = tuple(_sample(slot=slot) for slot in range(99)) + (
            _sample(slot=99, reached_maximal_path=False),
        )
        self.assertFalse(_report(samples=samples).is_discovery_eligible)

    def test_duplicate_sample_slot_cannot_inflate_proof(self):
        samples = tuple(_sample(slot=0) for _ in range(100))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            _report(samples=samples)


if __name__ == "__main__":
    unittest.main()
