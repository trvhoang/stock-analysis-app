from datetime import date
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from flexible_rulebook.scope_expansion import (
    ScopeExpansionStatus,
    build_scope_expansion_request,
    read_scope_status,
    write_scope_request,
)
from flexible_rulebook.scope_expansion_worker import run_scope_expansion_worker


_POLICY = SimpleNamespace(
    policy_digest="a" * 64,
    allowed_tickers=("VCB",),
    allowed_seeds=("frb-default-seed-v1",),
    cap_attempts=8,
    worker_count=1,
)


class FlexibleRulebookScopeExpansionWorkerTests(unittest.TestCase):
    def _request(self):
        return build_scope_expansion_request(
            _POLICY,
            benchmark_as_of=date(2026, 8, 27),
            additional_tickers="FPT",
            additional_seeds="seed-a",
            approved_by="operator",
            approval_note="approved expansion",
        )

    def test_worker_reports_pair_and_window_progress_and_terminal_report(self):
        request = self._request()
        progress = []

        def fake_benchmark(**kwargs):
            callback = kwargs["progress_fn"]
            callback(SimpleNamespace(phase="benchmark", completed=1, total=400, label="VCB / seed-a", safe_error=None))
            callback(SimpleNamespace(phase="benchmark", completed=400, total=400, label="FPT / seed-a", safe_error=None))
            return SimpleNamespace(digest="b" * 64, is_eligible=True)

        with tempfile.TemporaryDirectory() as directory:
            request_path = write_scope_request(Path(directory) / "job.request.json", request)
            with patch("flexible_rulebook.scope_expansion_worker.run_cap_benchmark", side_effect=fake_benchmark):
                status = run_scope_expansion_worker(request_path)
            self.assertIsInstance(status, ScopeExpansionStatus)
            self.assertEqual(status.state, "completed")
            self.assertEqual(status.report_digest, "b" * 64)
            self.assertEqual(status.completed_pairs, 4)
            self.assertEqual(status.total_pairs, 4)
            self.assertEqual(status.completed_windows, 100)
            self.assertEqual(read_scope_status(Path(directory) / "job.status.json"), status)

    def test_worker_records_safe_failure_without_writing_policy(self):
        request = self._request()
        with tempfile.TemporaryDirectory() as directory:
            request_path = write_scope_request(Path(directory) / "job.request.json", request)
            with patch(
                "flexible_rulebook.scope_expansion_worker.run_cap_benchmark",
                side_effect=ValueError("source unavailable"),
            ):
                status = run_scope_expansion_worker(request_path)
            self.assertEqual(status.state, "failed")
            self.assertIn("source unavailable", status.safe_error)
            self.assertFalse((Path(directory) / "active-policy.json").exists())


if __name__ == "__main__":
    unittest.main()
