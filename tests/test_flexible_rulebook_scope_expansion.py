from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from flexible_rulebook.scope_expansion import (
    ProgressEvent,
    ScopeExpansionStatus,
    build_scope_expansion_request,
    parse_scope_values,
    read_scope_request,
    read_scope_status,
    write_scope_request,
    write_scope_status,
)


_POLICY = SimpleNamespace(
    policy_digest="a" * 64,
    allowed_tickers=("VCB",),
    allowed_seeds=("frb-default-seed-v1",),
    cap_attempts=8,
    worker_count=1,
)


class FlexibleRulebookScopeExpansionTests(unittest.TestCase):
    def test_progress_event_requires_bounded_counts_and_exposes_safe_label(self):
        event = ProgressEvent("benchmark", 2, 4, "VCB / seed-a")
        self.assertEqual(event.phase, "benchmark")
        self.assertEqual(event.completed, 2)
        self.assertEqual(event.total, 4)
        self.assertEqual(event.label, "VCB / seed-a")
        with self.assertRaisesRegex(ValueError, "completed"):
            ProgressEvent("benchmark", 5, 4, "invalid")

    def test_scope_parser_normalizes_tickers_and_deduplicates_values(self):
        self.assertEqual(parse_scope_values(" vcb, fpt FPT ", "ticker"), ("FPT", "VCB"))
        self.assertEqual(parse_scope_values(" seed-b, seed-a seed-b ", "seed"), ("seed-a", "seed-b"))

    def test_scope_parser_rejects_invalid_kind_and_values(self):
        with self.assertRaisesRegex(ValueError, "kind"):
            parse_scope_values("VCB", "horizon")
        with self.assertRaisesRegex(ValueError, "ticker"):
            parse_scope_values("VCB/INVALID", "ticker")

    def test_request_uses_additive_sorted_union_and_frozen_operator_metadata(self):
        request = build_scope_expansion_request(
            _POLICY,
            benchmark_as_of=date(2026, 8, 27),
            additional_tickers="fpt, ree",
            additional_seeds="seed-b seed-a",
            approved_by="operator@example",
            approval_note="approved expansion",
        )
        self.assertEqual(request.benchmark_as_of, date(2026, 8, 27))
        self.assertEqual(request.tickers, ("FPT", "REE", "VCB"))
        self.assertEqual(request.seeds, ("frb-default-seed-v1", "seed-a", "seed-b"))
        self.assertEqual(request.cap_attempts, 8)
        self.assertEqual(request.cold_samples, 100)
        self.assertEqual(request.worker_count, 1)
        self.assertTrue(request.job_id.startswith("fse_"))
        self.assertEqual(request.approved_by, "operator@example")

    def test_duplicate_only_scope_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "new ticker or seed"):
            build_scope_expansion_request(
                _POLICY,
                benchmark_as_of=date(2026, 8, 27),
                additional_tickers="VCB",
                additional_seeds="frb-default-seed-v1",
                approved_by="operator",
                approval_note="note",
            )

    def test_request_rejects_missing_operator_metadata(self):
        with self.assertRaisesRegex(ValueError, "approved_by"):
            build_scope_expansion_request(
                _POLICY,
                benchmark_as_of=date(2026, 8, 27),
                additional_tickers="FPT",
                additional_seeds="",
                approved_by=" ",
                approval_note="note",
            )
        with self.assertRaisesRegex(ValueError, "approval_note"):
            build_scope_expansion_request(
                _POLICY,
                benchmark_as_of=date(2026, 8, 27),
                additional_tickers="FPT",
                additional_seeds="",
                approved_by="operator",
                approval_note=" ",
            )

    def test_request_and_status_files_round_trip_and_request_is_immutable(self):
        request = build_scope_expansion_request(
            _POLICY,
            benchmark_as_of=date(2026, 8, 27),
            additional_tickers="FPT",
            additional_seeds="seed-a",
            approved_by="operator",
            approval_note="note",
        )
        status = ScopeExpansionStatus(
            job_id=request.job_id,
            state="running",
            phase="benchmark",
            completed_pairs=1,
            total_pairs=4,
            completed_windows=32,
            required_windows=100,
            current_ticker="FPT",
            current_seed="frb-default-seed-v1",
            elapsed_seconds=12.5,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = write_scope_request(root / "request.json", request)
            status_path = write_scope_status(root / "status.json", status)
            self.assertEqual(read_scope_request(request_path), request)
            self.assertEqual(read_scope_status(status_path), status)
            request_path.write_text(json.dumps({"different": True}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "immutable"):
                write_scope_request(request_path, request)

    def test_status_rejects_non_monotonic_or_out_of_range_progress(self):
        with self.assertRaisesRegex(ValueError, "completed_pairs"):
            ScopeExpansionStatus(
                job_id="fse_" + "a" * 64,
                state="running",
                phase="benchmark",
                completed_pairs=2,
                total_pairs=1,
                completed_windows=0,
                required_windows=100,
                current_ticker=None,
                current_seed=None,
                elapsed_seconds=0.0,
            )

    def test_progress_event_callback_failures_do_not_abort_benchmark(self):
        event = ProgressEvent("benchmark", 1, 1, "VCB / seed-a")
        self.assertIsNone(event.safe_error)


if __name__ == "__main__":
    unittest.main()
