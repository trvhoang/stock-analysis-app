"""Isolated worker for a UI-triggered additive discovery-scope benchmark."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import time

from .cap_benchmark_runner import run_cap_benchmark
from .scope_expansion import (
    ProgressEvent,
    ScopeExpansionRequest,
    ScopeExpansionStatus,
    read_scope_request,
    write_scope_status,
)


def _status_path(request_path: Path) -> Path:
    name = request_path.name.removesuffix(".request.json")
    return request_path.with_name(name + ".status.json")


def _report_path(request_path: Path) -> Path:
    name = request_path.name.removesuffix(".request.json")
    return request_path.with_name(name + ".report.json")


def run_scope_expansion_worker(request_path: Path | str) -> ScopeExpansionStatus:
    """Run one immutable request and persist status/report sidecars."""

    request_path = Path(request_path).resolve()
    request = read_scope_request(request_path)
    status_path = _status_path(request_path)
    report_path = _report_path(request_path)
    total_pairs = len(request.tickers) * len(request.seeds)
    started = time.monotonic()

    running = ScopeExpansionStatus(
        job_id=request.job_id,
        state="running",
        phase="benchmark",
        completed_pairs=0,
        total_pairs=total_pairs,
        completed_windows=0,
        required_windows=request.cold_samples,
        policy_digest=request.policy_digest,
    )
    write_scope_status(status_path, running)

    def on_progress(event: ProgressEvent) -> None:
        completed_windows = event.completed
        pair_index = min((completed_windows - 1) // request.cold_samples, total_pairs - 1)
        completed_pairs = min(completed_windows // request.cold_samples, total_pairs)
        current_ticker = None
        current_seed = None
        if completed_windows < event.total:
            current_ticker = request.tickers[pair_index // len(request.seeds)]
            current_seed = request.seeds[pair_index % len(request.seeds)]
        write_scope_status(
            status_path,
            ScopeExpansionStatus(
                job_id=request.job_id,
                state="running",
                phase=event.phase,
                completed_pairs=completed_pairs,
                total_pairs=total_pairs,
                completed_windows=(completed_windows - pair_index * request.cold_samples),
                required_windows=request.cold_samples,
                current_ticker=current_ticker,
                current_seed=current_seed,
                elapsed_seconds=max(0.0, time.monotonic() - started),
                policy_digest=request.policy_digest,
                safe_error=event.safe_error,
            ),
        )

    try:
        report = run_cap_benchmark(
            tickers=request.tickers,
            as_of=request.benchmark_as_of,
            seeds=request.seeds,
            cap_attempts=request.cap_attempts,
            cold_samples=request.cold_samples,
            output=report_path,
            warm_samples=0,
            progress_fn=on_progress,
        )
        if not getattr(report, "is_eligible", False):
            status = ScopeExpansionStatus(
                job_id=request.job_id,
                state="failed",
                phase="benchmark",
                completed_pairs=total_pairs,
                total_pairs=total_pairs,
                completed_windows=request.cold_samples,
                required_windows=request.cold_samples,
                elapsed_seconds=max(0.0, time.monotonic() - started),
                report_digest=getattr(report, "digest", None),
                policy_digest=request.policy_digest,
                safe_error="BENCHMARK.INELIGIBLE",
            )
        else:
            status = ScopeExpansionStatus(
                job_id=request.job_id,
                state="completed",
                phase="benchmark",
                completed_pairs=total_pairs,
                total_pairs=total_pairs,
                completed_windows=request.cold_samples,
                required_windows=request.cold_samples,
                elapsed_seconds=max(0.0, time.monotonic() - started),
                report_digest=report.digest,
                policy_digest=request.policy_digest,
            )
    except Exception as error:
        status = ScopeExpansionStatus(
            job_id=request.job_id,
            state="failed",
            phase="benchmark",
            completed_pairs=0,
            total_pairs=total_pairs,
            completed_windows=0,
            required_windows=request.cold_samples,
            elapsed_seconds=max(0.0, time.monotonic() - started),
            policy_digest=request.policy_digest,
            safe_error=f"SCOPE_EXPANSION.WORKER_FAILED: {error}",
        )
    write_scope_status(status_path, status)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one Flexible Rulebook scope-expansion benchmark job.")
    parser.add_argument("request", type=Path, help="Absolute scope-expansion request JSON path")
    arguments = parser.parse_args(argv)
    status = run_scope_expansion_worker(arguments.request)
    print(f"Scope expansion job {status.job_id}: {status.state}")
    return 0 if status.state == "completed" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["main", "run_scope_expansion_worker"]
