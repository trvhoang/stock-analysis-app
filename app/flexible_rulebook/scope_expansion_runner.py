"""Durable coordinator for benchmark-then-activate scope expansion."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Callable

from .activation import activate_cap_report, load_active_policy
from .scope_expansion import (
    ScopeExpansionRequest,
    ScopeExpansionStatus,
    read_scope_request,
    write_scope_request,
    write_scope_status,
)
from .scope_expansion_worker import run_scope_expansion_worker


def _jobs_root(benchmark_directory: Path | str) -> Path:
    root = Path(benchmark_directory).resolve()
    if not root.is_absolute():
        raise ValueError("benchmark directory must be absolute")
    return root / "jobs"


def _request_path(benchmark_directory: Path | str, job_id: str) -> Path:
    return _jobs_root(benchmark_directory) / f"{job_id}.request.json"


def _status_path(request_path: Path) -> Path:
    return request_path.with_name(request_path.name.removesuffix(".request.json") + ".status.json")


def _report_path(request_path: Path) -> Path:
    return request_path.with_name(request_path.name.removesuffix(".request.json") + ".report.json")


def _default_launcher(request_path: Path) -> object:
    return subprocess.Popen(
        [sys.executable, "-m", "flexible_rulebook.scope_expansion_runner", "--request", str(request_path)],
        start_new_session=True,
    )


def submit_scope_expansion(
    request: ScopeExpansionRequest,
    *,
    benchmark_directory: Path | str,
    policy_loader_fn: Callable[[], tuple[object | None, str]] = load_active_policy,
    process_launcher: Callable[[Path], object] | None = None,
) -> str:
    """Persist one idempotent expansion request and launch its coordinator."""

    if not isinstance(request, ScopeExpansionRequest):
        raise ValueError("request must be ScopeExpansionRequest")
    policy, reason = policy_loader_fn()
    if policy is None or getattr(policy, "policy_digest", None) != request.policy_digest:
        raise ValueError(f"active policy changed or unavailable: {reason}")
    if (
        getattr(policy, "cap_attempts", None) != request.cap_attempts
        or getattr(policy, "worker_count", None) != request.worker_count
        or not set(getattr(policy, "allowed_tickers", ())).issubset(request.tickers)
        or not set(getattr(policy, "allowed_seeds", ())).issubset(request.seeds)
    ):
        raise ValueError("request does not preserve the active policy scope")
    request_path = _request_path(benchmark_directory, request.job_id)
    existing = request_path.exists()
    write_scope_request(request_path, request)
    status_path = _status_path(request_path)
    if existing and status_path.exists():
        return request.job_id
    write_scope_status(
        status_path,
        ScopeExpansionStatus(
            job_id=request.job_id,
            state="queued",
            phase="queued",
            completed_pairs=0,
            total_pairs=len(request.tickers) * len(request.seeds),
            completed_windows=0,
            required_windows=request.cold_samples,
            policy_digest=request.policy_digest,
        ),
    )
    launcher = _default_launcher if process_launcher is None else process_launcher
    launcher(request_path)
    return request.job_id


def run_scope_expansion_job(
    request_path: Path | str,
    *,
    benchmark_directory: Path | str | None = None,
    policy_loader_fn: Callable[[], tuple[object | None, str]] = load_active_policy,
) -> ScopeExpansionStatus:
    """Run benchmark and activate its additive policy only after validation."""

    path = Path(request_path).resolve()
    request = read_scope_request(path)
    benchmark_root = Path(benchmark_directory).resolve() if benchmark_directory is not None else path.parent.parent.resolve()
    status_path = _status_path(path)
    try:
        benchmark_status = run_scope_expansion_worker(path)
        if benchmark_status.state != "completed":
            return benchmark_status
        policy, reason = policy_loader_fn()
        if policy is None or getattr(policy, "policy_digest", None) != request.policy_digest:
            raise ValueError(f"active policy changed or unavailable: {reason}")
        report_path = _report_path(path)
        activated = activate_cap_report(
            report_path,
            benchmark_root,
            allowed_tickers=request.tickers,
            allowed_seeds=request.seeds,
            approved_by=request.approved_by,
            approval_note=request.approval_note,
        )
        status = ScopeExpansionStatus(
            job_id=request.job_id,
            state="completed",
            phase="activation",
            completed_pairs=benchmark_status.completed_pairs,
            total_pairs=benchmark_status.total_pairs,
            completed_windows=benchmark_status.completed_windows,
            required_windows=benchmark_status.required_windows,
            elapsed_seconds=benchmark_status.elapsed_seconds,
            report_digest=benchmark_status.report_digest,
            policy_digest=getattr(activated, "policy_digest", None),
        )
    except Exception as error:
        status = ScopeExpansionStatus(
            job_id=request.job_id,
            state="failed",
            phase="activation",
            completed_pairs=0,
            total_pairs=len(request.tickers) * len(request.seeds),
            completed_windows=0,
            required_windows=request.cold_samples,
            policy_digest=request.policy_digest,
            safe_error=f"SCOPE_EXPANSION.ACTIVATION_FAILED: {error}",
        )
    write_scope_status(status_path, status)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and activate one Flexible Rulebook scope expansion job.")
    parser.add_argument("--request", required=True, type=Path, help="Absolute scope-expansion request JSON path")
    arguments = parser.parse_args(argv)
    status = run_scope_expansion_job(arguments.request)
    print(f"Scope expansion job {status.job_id}: {status.state}")
    return 0 if status.state == "completed" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["main", "run_scope_expansion_job", "submit_scope_expansion"]
