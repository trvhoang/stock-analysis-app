from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from flexible_rulebook.benchmark import ScalePolicy, validate_scale_policy
from flexible_rulebook.cap_benchmark import (
    DiscoveryCapBenchmarkReport,
    DiscoveryCapSample,
    benchmark_record_from_cap_report,
    read_cap_benchmark_report,
    validate_cap_report,
    write_cap_benchmark_report,
)
from flexible_rulebook.contracts import canonical_json


_AS_OF = date(2026, 8, 28)
_SEED = "frb-default-seed-v1"
_CAP = 8
_RUNTIME_CONTRACT = canonical_json(
    {
        "catalog_hash": "c" * 64,
        "candidate_space_hash": "d" * 64,
        "execution_revision": "flexible-execution-v1",
    }
)


def _sample(index: int, *, completed: bool = True) -> DiscoveryCapSample:
    start_slot = index * _CAP
    return DiscoveryCapSample(
        ticker="VCB",
        seed=_SEED,
        mode="cold",
        sample_index=index,
        benchmark_as_of=_AS_OF,
        cap_attempts=_CAP,
        start_slot=start_slot,
        assignment_hash=f"{index:064x}",
        source_identity=canonical_json(
            {
                "ticker": "VCB",
                "raw_history_fingerprint": "a" * 64,
                "requested_start": "2011-08-28",
                "requested_as_of": "2026-08-28",
                "first_date": "2011-08-29",
                "as_of_date": "2026-08-28",
                "quality_state": "eligible",
                "quality_revision": "flexible-history-v1",
            }
        ),
        split_identity=canonical_json({"method": "calendar_10y_5y"}),
        attempted_count=_CAP if completed else _CAP - 1,
        committed_count=_CAP if completed else _CAP - 1,
        next_slot=start_slot + _CAP if completed else start_slot + _CAP - 1,
        uncommitted_slot=None if completed else start_slot + _CAP - 1,
        preflight_seconds=1.0,
        cap_window_seconds=2.0,
        total_seconds=3.0,
        slot_timings=(),
        selection_seconds=0.1,
        write_seconds=0.1,
        terminal_state="completed" if completed else "completed_with_errors",
        safe_error_code=None,
        peak_rss_bytes=1024,
        peak_pool_checkouts=1,
        cache_bytes=512,
        artifact_bytes=256,
    )


def _report(*, sample_count: int = 100, completed: bool = True) -> DiscoveryCapBenchmarkReport:
    return DiscoveryCapBenchmarkReport(
        benchmark_as_of=_AS_OF,
        tickers=("VCB",),
        seeds=(_SEED,),
        cap_attempts=_CAP,
        runtime_contract_identity=_RUNTIME_CONTRACT,
        samples=tuple(_sample(index, completed=completed) for index in range(sample_count)),
        ticker_elapsed_seconds_by_ticker=(("VCB", float(sample_count * 3)),),
    )


class FlexibleRulebookCapBenchmarkTests(unittest.TestCase):
    def test_complete_cap_anchor_requires_the_full_feature_snapshot_identity(self):
        incomplete_anchor = json.loads(_sample(0).source_identity)
        incomplete_anchor.pop("quality_revision")

        with self.assertRaisesRegex(ValueError, "source_identity is incomplete"):
            replace(_sample(0), source_identity=canonical_json(incomplete_anchor))

    def test_direct_cap_record_requires_the_exact_measured_cap(self):
        record = benchmark_record_from_cap_report(_report())

        validate_scale_policy(
            ScalePolicy(
                max_discovery_attempt_count=_CAP,
                worker_count=1,
                benchmark_report_hash=record.benchmark_report_hash,
            ),
            record,
        )

        with self.assertRaisesRegex(ValueError, "exactly equal"):
            validate_scale_policy(
                ScalePolicy(
                    max_discovery_attempt_count=_CAP - 1,
                    worker_count=1,
                    benchmark_report_hash=record.benchmark_report_hash,
                ),
                record,
            )

    def test_direct_cap_record_uses_conservative_total_when_p99_components_diverge(self):
        samples = list(_report().samples)
        for index in (96, 97):
            samples[index] = replace(
                samples[index],
                preflight_seconds=10.0,
                cap_window_seconds=2.0,
                total_seconds=12.0,
            )
        for index in (98, 99):
            samples[index] = replace(
                samples[index],
                preflight_seconds=1.0,
                cap_window_seconds=10.0,
                total_seconds=11.0,
            )
        report = replace(
            _report(),
            samples=tuple(samples),
            ticker_elapsed_seconds_by_ticker=(("VCB", 340.0),),
        )

        record = benchmark_record_from_cap_report(report)

        self.assertGreaterEqual(
            record.cold_p99_total_seconds,
            record.cold_p99_preflight_seconds + record.cold_p99_cap_window_seconds,
        )

    def test_cap_report_rejects_ninety_nine_complete_cold_windows(self):
        with self.assertRaisesRegex(ValueError, "100 completed cold"):
            validate_cap_report(_report(sample_count=99))

    def test_cap_report_rejects_an_incomplete_window(self):
        with self.assertRaisesRegex(ValueError, "exactly"):
            validate_cap_report(_report(completed=False))

    def test_diagnostic_failure_can_truthfully_omit_an_unknown_source_anchor(self):
        failed = replace(
            _sample(0),
            source_identity=None,
            split_identity=None,
            attempted_count=0,
            committed_count=0,
            next_slot=0,
            uncommitted_slot=0,
            terminal_state="blocked",
            safe_error_code="SOURCE.UNAVAILABLE",
        )
        report = replace(
            _report(),
            samples=(failed, *_report().samples[1:]),
            ticker_elapsed_seconds_by_ticker=(("VCB", 300.0),),
        )

        self.assertIsNone(failed.source_identity)
        self.assertIsNone(failed.split_identity)
        with self.assertRaisesRegex(ValueError, "exactly complete"):
            validate_cap_report(report)

    def test_direct_cap_policy_requires_one_measured_worker(self):
        record = replace(
            benchmark_record_from_cap_report(_report()),
            worker_counts=(1, 2),
        )

        with self.assertRaisesRegex(ValueError, "one worker"):
            validate_scale_policy(
                ScalePolicy(
                    max_discovery_attempt_count=_CAP,
                    worker_count=1,
                    benchmark_report_hash=record.benchmark_report_hash,
                ),
                record,
            )

    def test_report_rejects_duplicate_identity_and_overlapping_window(self):
        samples = _report().samples
        with self.assertRaisesRegex(ValueError, "duplicate sample identity"):
            DiscoveryCapBenchmarkReport(
                benchmark_as_of=_AS_OF,
                tickers=("VCB",),
                seeds=(_SEED,),
                cap_attempts=_CAP,
                runtime_contract_identity=_RUNTIME_CONTRACT,
                samples=(samples[0], *samples[1:], samples[0]),
                ticker_elapsed_seconds_by_ticker=(("VCB", 303.0),),
            )
        with self.assertRaisesRegex(ValueError, "start_slot"):
            replace(samples[1], start_slot=samples[1].start_slot - 1)

    def test_report_rejects_source_and_split_disagreement(self):
        samples = list(_report().samples)
        changed_source = json.loads(samples[-1].source_identity)
        changed_source["raw_history_fingerprint"] = "b" * 64
        samples[-1] = replace(
            samples[-1],
            source_identity=canonical_json(changed_source),
        )
        report = replace(
            _report(),
            samples=tuple(samples),
            ticker_elapsed_seconds_by_ticker=(("VCB", 300.0),),
        )
        with self.assertRaisesRegex(ValueError, "source identity changed"):
            validate_cap_report(report)

        samples = list(_report().samples)
        samples[-1] = replace(
            samples[-1],
            split_identity=canonical_json({"method": "ratio_65_35"}),
        )
        report = replace(
            _report(),
            samples=tuple(samples),
            ticker_elapsed_seconds_by_ticker=(("VCB", 300.0),),
        )
        with self.assertRaisesRegex(ValueError, "split identity changed"):
            validate_cap_report(report)

    def test_report_rejects_ticker_anchor_disagreement_across_allowed_seeds(self):
        alternate_seed = "frb-alternate-seed-v1"
        alternate = []
        for sample in _report().samples:
            changed_source = json.loads(sample.source_identity)
            changed_source["raw_history_fingerprint"] = "c" * 64
            alternate.append(
                replace(
                    sample,
                    seed=alternate_seed,
                    source_identity=canonical_json(changed_source),
                )
            )
        report = DiscoveryCapBenchmarkReport(
            benchmark_as_of=_AS_OF,
            tickers=("VCB",),
            seeds=(_SEED, alternate_seed),
            cap_attempts=_CAP,
            runtime_contract_identity=_RUNTIME_CONTRACT,
            samples=(*_report().samples, *alternate),
            ticker_elapsed_seconds_by_ticker=(("VCB", 600.0),),
        )

        with self.assertRaisesRegex(ValueError, "across seeds"):
            validate_cap_report(report)

    def test_report_rejects_direct_window_and_ticker_budget_deadlines(self):
        samples = list(_report().samples)
        for index in (-2, -1):
            samples[index] = replace(
                samples[index],
                cap_window_seconds=16_200.0,
                total_seconds=16_201.0,
            )
        total_seconds = sum(sample.total_seconds for sample in samples)
        report = replace(
            _report(),
            samples=tuple(samples),
            ticker_elapsed_seconds_by_ticker=(("VCB", total_seconds),),
        )
        with self.assertRaisesRegex(ValueError, "admission deadline"):
            validate_cap_report(report)

        report = replace(
            _report(),
            ticker_elapsed_seconds_by_ticker=(("VCB", 17_700.1),),
        )
        with self.assertRaisesRegex(ValueError, "serial ticker budget"):
            validate_cap_report(report)

    def test_cap_report_round_trip_rejects_noncanonical_and_tampered_documents(self):
        report = _report()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cap-report.json"
            write_cap_benchmark_report(path, report)
            self.assertEqual(read_cap_benchmark_report(path), report)

            path.write_text(
                canonical_json(report.to_document()) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "canonical JSON"):
                read_cap_benchmark_report(path)

            document = report.to_document()
            document["payload"]["cap_attempts"] = _CAP + 1
            path.write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest"):
                read_cap_benchmark_report(path)


if __name__ == "__main__":
    unittest.main()
