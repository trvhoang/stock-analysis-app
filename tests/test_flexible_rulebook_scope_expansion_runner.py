from datetime import date
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from flexible_rulebook.scope_expansion import (
    ScopeExpansionStatus,
    build_scope_expansion_request,
    read_scope_status,
    write_scope_request,
)
from flexible_rulebook.scope_expansion_runner import (
    run_scope_expansion_job,
    submit_scope_expansion,
)


_POLICY = SimpleNamespace(
    policy_digest="a" * 64,
    allowed_tickers=("VCB",),
    allowed_seeds=("frb-default-seed-v1",),
    cap_attempts=8,
    worker_count=1,
)


def _request():
    return build_scope_expansion_request(
        _POLICY,
        benchmark_as_of=date(2026, 8, 27),
        additional_tickers="FPT",
        additional_seeds="seed-a",
        approved_by="operator",
        approval_note="approved expansion",
    )


class FlexibleRulebookScopeExpansionRunnerTests(unittest.TestCase):
    def test_submit_creates_queued_job_and_reuses_duplicate_request(self):
        request = _request()
        launched = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_id = submit_scope_expansion(
                request,
                benchmark_directory=root,
                policy_loader_fn=lambda: (_POLICY, "active"),
                process_launcher=launched.append,
            )
            duplicate = submit_scope_expansion(
                request,
                benchmark_directory=root,
                policy_loader_fn=lambda: (_POLICY, "active"),
                process_launcher=launched.append,
            )
            self.assertEqual(duplicate, job_id)
            self.assertEqual(len(launched), 1)
            status = read_scope_status(root / "jobs" / f"{job_id}.status.json")
            self.assertEqual(status.state, "queued")
            self.assertEqual(status.total_pairs, 4)

    def test_job_activates_union_scope_only_after_worker_success(self):
        request = _request()
        completed = ScopeExpansionStatus(
            job_id=request.job_id,
            state="completed",
            phase="benchmark",
            completed_pairs=4,
            total_pairs=4,
            completed_windows=100,
            required_windows=100,
            elapsed_seconds=1.0,
            report_digest="b" * 64,
            policy_digest=request.policy_digest,
        )
        activated = SimpleNamespace(policy_digest="c" * 64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = write_scope_request(root / "jobs" / f"{request.job_id}.request.json", request)
            with patch("flexible_rulebook.scope_expansion_runner.run_scope_expansion_worker", return_value=completed), patch(
                "flexible_rulebook.scope_expansion_runner.load_active_policy",
                return_value=(_POLICY, "active"),
            ), patch(
                "flexible_rulebook.scope_expansion_runner.activate_cap_report",
                return_value=activated,
            ) as activate:
                status = run_scope_expansion_job(
                    request_path,
                    benchmark_directory=root,
                    policy_loader_fn=lambda: (_POLICY, "active"),
                )
            self.assertEqual(status.state, "completed", status.safe_error)
            self.assertEqual(status.policy_digest, "c" * 64)
            activate.assert_called_once()
            self.assertEqual(activate.call_args.kwargs["allowed_tickers"], request.tickers)
            self.assertEqual(activate.call_args.kwargs["allowed_seeds"], request.seeds)

    def test_job_fails_and_preserves_pointer_when_active_policy_changed(self):
        request = _request()
        completed = ScopeExpansionStatus(
            job_id=request.job_id,
            state="completed",
            phase="benchmark",
            completed_pairs=4,
            total_pairs=4,
            completed_windows=100,
            required_windows=100,
            elapsed_seconds=1.0,
            report_digest="b" * 64,
            policy_digest=request.policy_digest,
        )
        changed = SimpleNamespace(policy_digest="d" * 64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = write_scope_request(root / "jobs" / f"{request.job_id}.request.json", request)
            with patch("flexible_rulebook.scope_expansion_runner.run_scope_expansion_worker", return_value=completed), patch(
                "flexible_rulebook.scope_expansion_runner.load_active_policy",
                return_value=(changed, "active"),
            ), patch("flexible_rulebook.scope_expansion_runner.activate_cap_report") as activate:
                status = run_scope_expansion_job(
                    request_path,
                    benchmark_directory=root,
                    policy_loader_fn=lambda: (changed, "active"),
                )
            self.assertEqual(status.state, "failed")
            self.assertIn("active policy changed", status.safe_error)
            activate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
