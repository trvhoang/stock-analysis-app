"""Read-only fixed-cap benchmark runner for Flexible Rulebook discovery."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date
import json
import math
import os
import re
from pathlib import Path
import tempfile
import time
from typing import Callable, Literal, Sequence

from .benchmark import TERMINAL_SECONDS
from .benchmark_runner import production_sample_runtime, validate_benchmark_output_path
from .cap_benchmark import (
    DiscoveryCapBenchmarkReport,
    DiscoveryCapSample,
    SlotPhaseTiming,
    WindowPhaseTiming,
    write_cap_benchmark_report,
)
from .campaigns import CampaignManifest, CampaignRequest
from .catalog import CatalogRevision, catalog_revision_1, feature_profile
from .contracts import (
    ExecutionContract,
    FeatureBuildContract,
    FeatureProfile,
    RuntimeBudget,
    SelectionPolicy,
    canonical_json,
)
from .features import FeatureResolution, feature_snapshot_for_history
from .history import HistorySnapshot, make_evaluation_split
from .search import CandidateSpace, SearchBudget, assign_frontier, candidate_space
from .storage import resolve_flexible_root
from .scope_expansion import ProgressEvent


_TICKER = re.compile(r"^[A-Z0-9._-]+$")
_SAFE_ERROR = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+$")
_PHASE_TELEMETRY_NAME = ".flexible-cap-benchmark-phases-v1.json"
_DEADLINE_NAME = ".flexible-cap-benchmark-deadline-v1.json"


def _ticker(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("ticker must be text")
    normalized = value.strip().upper()
    if not normalized or not _TICKER.fullmatch(normalized):
        raise ValueError("ticker must contain only persistence-safe characters")
    return normalized


def _seed(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("seed must be non-empty text")
    return value.strip()


def _unique(values: object, name: str, normalizer: Callable[[object], str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        normalized = tuple(normalizer(value) for value in values)
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    if not normalized or len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must be non-empty and unique")
    return normalized


def _duration(start: float, monotonic: Callable[[], float]) -> float:
    elapsed = float(monotonic()) - start
    return elapsed if elapsed >= 0.0 else 0.0


def _tree_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class CapPhaseTelemetryRecorder:
    """Persist worker-owned timing events under one isolated cap-window root."""

    def __init__(
        self,
        root: Path,
        *,
        rss_probe: Callable[[], int | None] = lambda: None,
    ) -> None:
        self._path = _outside_live_root(root) / _PHASE_TELEMETRY_NAME
        self._slot_timings: list[SlotPhaseTiming] = []
        self._window_timings: dict[str, WindowPhaseTiming] = {}
        if not callable(rss_probe):
            raise ValueError("cap benchmark RSS probe must be callable")
        self._rss_probe = rss_probe

    def __call__(self, event: SlotPhaseTiming | WindowPhaseTiming) -> None:
        if isinstance(event, SlotPhaseTiming):
            self._slot_timings.append(event)
        elif isinstance(event, WindowPhaseTiming):
            if event.phase in self._window_timings:
                raise ValueError("cap benchmark window timing is duplicated")
            self._window_timings[event.phase] = event
        else:
            raise ValueError("cap benchmark timing event is invalid")
        _atomic_json(
            self._path,
            {
                "schema_version": 1,
                "kind": "flexible_rulebook_cap_benchmark_phases",
                "slot_timings": [event.to_dict() for event in self._slot_timings],
                "window_timings": [
                    self._window_timings[name].to_dict()
                    for name in ("selection", "write")
                    if name in self._window_timings
                ],
                "peak_rss_bytes": _probe(self._rss_probe),
            },
        )


def _read_cap_phase_telemetry(
    root: Path,
) -> tuple[tuple[SlotPhaseTiming, ...], float, float, int | None]:
    try:
        payload = json.loads((_outside_live_root(root) / _PHASE_TELEMETRY_NAME).read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {"schema_version", "kind", "slot_timings", "window_timings", "peak_rss_bytes"}
            or payload["schema_version"] != 1
            or payload["kind"] != "flexible_rulebook_cap_benchmark_phases"
            or not isinstance(payload["slot_timings"], list)
            or not isinstance(payload["window_timings"], list)
        ):
            raise ValueError("cap benchmark phase telemetry is invalid")
        slot_timings = tuple(SlotPhaseTiming(**item) for item in payload["slot_timings"])
        window_timings = tuple(WindowPhaseTiming(**item) for item in payload["window_timings"])
        if len({event.phase for event in window_timings}) != len(window_timings):
            raise ValueError("cap benchmark window timing is duplicated")
        durations = {event.phase: event.seconds for event in window_timings}
        peak_rss = payload["peak_rss_bytes"]
        if (
            peak_rss is not None
            and (
                isinstance(peak_rss, bool)
                or not isinstance(peak_rss, int)
                or peak_rss < 0
            )
        ):
            raise ValueError("cap benchmark child RSS is invalid")
        return (
            slot_timings,
            durations.get("selection", 0.0),
            durations.get("write", 0.0),
            peak_rss,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return (), 0.0, 0.0, None


def _write_remaining_deadline(root: Path, remaining_seconds: int) -> None:
    if (
        isinstance(remaining_seconds, bool)
        or not isinstance(remaining_seconds, int)
        or not 0 < remaining_seconds <= TERMINAL_SECONDS
    ):
        raise ValueError("remaining cap benchmark deadline is invalid")
    _atomic_json(
        _outside_live_root(root) / _DEADLINE_NAME,
        {
            "schema_version": 1,
            "kind": "flexible_rulebook_cap_benchmark_deadline",
            "remaining_seconds": remaining_seconds,
        },
    )


def _read_remaining_deadline(root: Path) -> int | None:
    try:
        payload = json.loads((_outside_live_root(root) / _DEADLINE_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "kind", "remaining_seconds"}
        or payload["schema_version"] != 1
        or payload["kind"] != "flexible_rulebook_cap_benchmark_deadline"
    ):
        return None
    value = payload["remaining_seconds"]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= TERMINAL_SECONDS:
        return None
    return value


def _outside_live_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("cap benchmark sample root must be absolute")
    resolved = root.resolve()
    live = resolve_flexible_root().resolve()
    if resolved == live or live in resolved.parents:
        raise ValueError("cap benchmark sample root cannot be inside the Flexible Rulebook evidence root")
    return resolved


@dataclass(frozen=True)
class CapBenchmarkRuntime:
    """Injected seams for one complete cap window; production remains read-only."""

    catalog: CatalogRevision
    history_loader: Callable[[str, date], HistorySnapshot]
    feature_resolver: Callable[
        [HistorySnapshot, FeatureBuildContract, FeatureProfile, Path, Literal["reuse", "rebuild"]],
        FeatureResolution,
    ]
    campaign_executor: Callable[[CampaignRequest, Path], CampaignManifest]
    cache_is_complete: Callable[[HistorySnapshot, FeatureBuildContract, FeatureProfile, Path], bool]
    monotonic: Callable[[], float]
    rss_probe: Callable[[], int | None]
    pool_checkout_probe: Callable[[], int | None]
    worker_preparer: Callable[[CampaignRequest, FeatureResolution, Path], None] = (
        lambda _request, _features, _root: None
    )
    build_contract: FeatureBuildContract = field(default_factory=FeatureBuildContract)
    execution_contract: ExecutionContract = field(default_factory=ExecutionContract)
    runtime_budget: RuntimeBudget = field(default_factory=RuntimeBudget)
    selection_policy: SelectionPolicy = field(default_factory=SelectionPolicy)
    engine_revision: str = "flexible-cap-benchmark-runner-v1"
    _space: CandidateSpace = field(init=False, repr=False, compare=False)
    _profile: FeatureProfile = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, CatalogRevision):
            raise ValueError("cap benchmark runtime requires a catalog")
        if not isinstance(self.build_contract, FeatureBuildContract):
            raise ValueError("cap benchmark runtime requires FeatureBuildContract")
        if not isinstance(self.execution_contract, ExecutionContract):
            raise ValueError("cap benchmark runtime requires ExecutionContract")
        if not isinstance(self.runtime_budget, RuntimeBudget):
            raise ValueError("cap benchmark runtime requires RuntimeBudget")
        if not isinstance(self.selection_policy, SelectionPolicy):
            raise ValueError("cap benchmark runtime requires SelectionPolicy")
        if not isinstance(self.engine_revision, str) or not self.engine_revision:
            raise ValueError("cap benchmark runtime engine_revision must be non-empty")
        if not all(
            callable(getattr(self, name))
            for name in (
                "history_loader",
                "feature_resolver",
                "campaign_executor",
                "cache_is_complete",
                "monotonic",
                "rss_probe",
                "pool_checkout_probe",
                "worker_preparer",
            )
        ):
            raise ValueError("cap benchmark runtime dependencies must be callable")
        object.__setattr__(self, "_space", candidate_space(self.catalog))
        object.__setattr__(self, "_profile", feature_profile(self.catalog))

    @property
    def space(self) -> CandidateSpace:
        return self._space

    @property
    def profile(self) -> FeatureProfile:
        return self._profile


def _source_identity(snapshot: HistorySnapshot) -> str:
    source = feature_snapshot_for_history(snapshot)
    return canonical_json(
        {
            "ticker": source.ticker,
            "raw_history_fingerprint": source.raw_history_fingerprint,
            "requested_start": source.requested_start.isoformat(),
            "requested_as_of": source.requested_as_of.isoformat(),
            "first_date": source.first_date.isoformat(),
            "as_of_date": source.as_of_date.isoformat(),
            "quality_state": source.quality_state,
            "quality_revision": source.quality_revision,
        }
    )


def discovery_runtime_contract_identity(runtime: CapBenchmarkRuntime) -> str:
    """Return the full immutable runtime identity that cap reports authorize."""

    assignment = assign_frontier(
        runtime.space,
        frontier_seed="frb-default-seed-v1",
        source_ticker="VNINDEX",
        start_slot=0,
        budget=SearchBudget(attempt_count=1, runtime=runtime.runtime_budget),
    )
    return canonical_json(
        {
            "catalog_hash": runtime.catalog.catalog_hash,
            "feature_build_contract_hash": runtime.build_contract.feature_build_contract_hash,
            "feature_profile_hash": runtime.profile.feature_profile_hash,
            "candidate_space_hash": runtime.space.candidate_space_hash,
            "candidate_space_algorithm_version": runtime.space.candidate_space_algorithm_version,
            "frontier_algorithm_version": assignment.algorithm_version,
            "frontier_stratification_revision": assignment.stratification_revision,
            "execution_contract": runtime.execution_contract.to_identity_dict(),
            "runtime_budget": runtime.runtime_budget.to_identity_dict(),
            "selection_policy": runtime.selection_policy.to_identity_dict(),
            "engine_revision": runtime.engine_revision,
            "qualification_revision": "both-partitions-12-65-15-v1",
        }
    )


def _campaign_request(
    *,
    ticker: str,
    seed: str,
    sample_index: int,
    cap_attempts: int,
    snapshot: HistorySnapshot,
    features: FeatureResolution,
    runtime: CapBenchmarkRuntime,
) -> CampaignRequest:
    source = feature_snapshot_for_history(snapshot)
    if (
        features.plan.snapshot != source
        or features.plan.build_contract != runtime.build_contract
        or features.plan.profile != runtime.profile
    ):
        raise ValueError("feature resolution does not match the cap benchmark contract")
    start_slot = sample_index * cap_attempts
    assignment = assign_frontier(
        runtime.space,
        frontier_seed=seed,
        source_ticker=ticker,
        start_slot=start_slot,
        budget=SearchBudget(attempt_count=cap_attempts, runtime=runtime.runtime_budget),
    )
    return CampaignRequest(
        operation="discover",
        frozen_members=(ticker,),
        source_snapshots=(source,),
        catalog_hash=runtime.catalog.catalog_hash,
        engine_revision=runtime.engine_revision,
        rulebook_ids=(),
        feature_build_contract_hashes=(runtime.build_contract.feature_build_contract_hash,),
        feature_plan_hashes=(features.plan.feature_plan_hash,),
        execution_contract=runtime.execution_contract,
        split=make_evaluation_split(snapshot),
        runtime_budget=runtime.runtime_budget,
        selection_policy=runtime.selection_policy,
        per_ticker_budget=cap_attempts,
        frontier_assignment=assignment,
    )


def _probe(probe: Callable[[], int | None]) -> int | None:
    try:
        value = probe()
    except Exception:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _diagnostic_sample(
    *,
    ticker: str,
    seed: str,
    mode: Literal["cold", "warm"],
    sample_index: int,
    benchmark_as_of: date,
    cap_attempts: int,
    assignment_hash: str,
    source_identity: str | None,
    split_identity: str | None,
    preflight_seconds: float,
    cap_window_seconds: float,
    total_seconds: float,
    terminal_state: str,
    safe_error_code: str,
    runtime: CapBenchmarkRuntime,
    root: Path,
) -> DiscoveryCapSample:
    start_slot = sample_index * cap_attempts
    return DiscoveryCapSample(
        ticker=ticker,
        seed=seed,
        mode=mode,
        sample_index=sample_index,
        benchmark_as_of=benchmark_as_of,
        cap_attempts=cap_attempts,
        start_slot=start_slot,
        assignment_hash=assignment_hash,
        source_identity=source_identity,
        split_identity=split_identity,
        attempted_count=0,
        committed_count=0,
        next_slot=start_slot,
        uncommitted_slot=start_slot,
        preflight_seconds=preflight_seconds,
        cap_window_seconds=cap_window_seconds,
        total_seconds=total_seconds,
        slot_timings=(),
        selection_seconds=0.0,
        write_seconds=0.0,
        terminal_state=terminal_state,
        safe_error_code=safe_error_code,
        peak_rss_bytes=_probe(runtime.rss_probe),
        peak_pool_checkouts=_probe(runtime.pool_checkout_probe),
        cache_bytes=_tree_bytes(root / "cache"),
        artifact_bytes=max(0, _tree_bytes(root) - _tree_bytes(root / "cache")),
    )


def _manifest_counts(manifest: CampaignManifest, start_slot: int, cap_attempts: int) -> tuple[int, int, int, int | None]:
    end_slot = start_slot + cap_attempts
    next_slot = manifest.next_slot
    if (
        isinstance(next_slot, bool)
        or not isinstance(next_slot, int)
        or not start_slot <= next_slot <= end_slot
        or manifest.chain_attempted_count != next_slot
    ):
        raise ValueError("cap worker manifest cursor is invalid")
    uncommitted = manifest.uncommitted_slot
    if uncommitted is not None and not start_slot <= uncommitted < end_slot:
        raise ValueError("cap worker uncommitted slot is outside its window")
    count = next_slot - start_slot
    return count, count, next_slot, uncommitted


def run_cap_window(
    *,
    ticker: str,
    as_of: date,
    seed: str,
    mode: Literal["cold", "warm"],
    sample_index: int,
    cap_attempts: int,
    root: Path,
    runtime: CapBenchmarkRuntime,
    remaining_seconds: Callable[[], int] | None = None,
) -> DiscoveryCapSample:
    """Measure one fixed cap window without writing to live Flexible evidence."""

    root = _outside_live_root(root)
    start_slot = sample_index * cap_attempts
    assignment = assign_frontier(
        runtime.space,
        frontier_seed=seed,
        source_ticker=ticker,
        start_slot=start_slot,
        budget=SearchBudget(attempt_count=cap_attempts, runtime=runtime.runtime_budget),
    )
    preflight_started = float(runtime.monotonic())
    source_identity: str | None = None
    split_identity: str | None = None
    try:
        snapshot = runtime.history_loader(ticker, as_of)
        if (
            not isinstance(snapshot, HistorySnapshot)
            or snapshot.quality_state != "eligible"
            or snapshot.fingerprint is None
        ):
            raise ValueError("data is not eligible")
        source_identity = _source_identity(snapshot)
        split_identity = canonical_json(make_evaluation_split(snapshot).to_identity_dict())
        choice: Literal["reuse", "rebuild"] = "rebuild"
        if mode == "warm":
            runtime.feature_resolver(
                snapshot,
                runtime.build_contract,
                runtime.profile,
                root,
                "rebuild",
            )
            if not runtime.cache_is_complete(
                snapshot,
                runtime.build_contract,
                runtime.profile,
                root,
            ):
                raise ValueError("warm prepopulation did not create a complete cache")
            refreshed = runtime.history_loader(ticker, as_of)
            if (
                not isinstance(refreshed, HistorySnapshot)
                or refreshed.quality_state != "eligible"
                or refreshed.fingerprint is None
            ):
                elapsed = _duration(preflight_started, runtime.monotonic)
                return _diagnostic_sample(
                    ticker=ticker,
                    seed=seed,
                    mode=mode,
                    sample_index=sample_index,
                    benchmark_as_of=as_of,
                    cap_attempts=cap_attempts,
                    assignment_hash=assignment.assignment_hash,
                    source_identity=source_identity,
                    split_identity=split_identity,
                    preflight_seconds=elapsed,
                    cap_window_seconds=0.0,
                    total_seconds=elapsed,
                    terminal_state="blocked",
                    safe_error_code="SOURCE.CHANGED",
                    runtime=runtime,
                    root=root,
                )
            if _source_identity(refreshed) != source_identity:
                elapsed = _duration(preflight_started, runtime.monotonic)
                return _diagnostic_sample(
                    ticker=ticker,
                    seed=seed,
                    mode=mode,
                    sample_index=sample_index,
                    benchmark_as_of=as_of,
                    cap_attempts=cap_attempts,
                    assignment_hash=assignment.assignment_hash,
                    source_identity=source_identity,
                    split_identity=split_identity,
                    preflight_seconds=elapsed,
                    cap_window_seconds=0.0,
                    total_seconds=elapsed,
                    terminal_state="blocked",
                    safe_error_code="SOURCE.CHANGED",
                    runtime=runtime,
                    root=root,
                )
            snapshot = refreshed
            split_identity = canonical_json(make_evaluation_split(snapshot).to_identity_dict())
            choice = "reuse"
        features = runtime.feature_resolver(
            snapshot,
            runtime.build_contract,
            runtime.profile,
            root,
            choice,
        )
        campaign = _campaign_request(
            ticker=ticker,
            seed=seed,
            sample_index=sample_index,
            cap_attempts=cap_attempts,
            snapshot=snapshot,
            features=features,
            runtime=runtime,
        )
        runtime.worker_preparer(campaign, features, root)
    except Exception:
        elapsed = _duration(preflight_started, runtime.monotonic)
        return _diagnostic_sample(
            ticker=ticker,
            seed=seed,
            mode=mode,
            sample_index=sample_index,
            benchmark_as_of=as_of,
            cap_attempts=cap_attempts,
            assignment_hash=assignment.assignment_hash,
            source_identity=source_identity,
            split_identity=split_identity,
            preflight_seconds=elapsed,
            cap_window_seconds=0.0,
            total_seconds=elapsed,
            terminal_state="blocked" if source_identity is None else "failed",
            safe_error_code="SOURCE.UNAVAILABLE" if source_identity is None else "FEATURE.PREFLIGHT_FAILED",
            runtime=runtime,
            root=root,
        )

    if remaining_seconds is not None:
        if not callable(remaining_seconds):
            raise ValueError("remaining_seconds must be callable or None")
        available = remaining_seconds()
        if (
            isinstance(available, bool)
            or not isinstance(available, int)
            or available <= 0
        ):
            elapsed = _duration(preflight_started, runtime.monotonic)
            return _diagnostic_sample(
                ticker=ticker,
                seed=seed,
                mode=mode,
                sample_index=sample_index,
                benchmark_as_of=as_of,
                cap_attempts=cap_attempts,
                assignment_hash=assignment.assignment_hash,
                source_identity=source_identity,
                split_identity=split_identity,
                preflight_seconds=elapsed,
                cap_window_seconds=0.0,
                total_seconds=elapsed,
                terminal_state="interrupted",
                safe_error_code="BENCHMARK.TICKER_BUDGET_EXHAUSTED",
                runtime=runtime,
                root=root,
            )
        _write_remaining_deadline(root, min(available, TERMINAL_SECONDS))

    cap_started = float(runtime.monotonic())
    try:
        manifest = runtime.campaign_executor(campaign, root)
        if not isinstance(manifest, CampaignManifest):
            raise ValueError("cap campaign executor did not return a CampaignManifest")
        attempted, committed, next_slot, uncommitted = _manifest_counts(
            manifest,
            start_slot,
            cap_attempts,
        )
    except Exception:
        preflight_seconds = _duration(preflight_started, runtime.monotonic)
        cap_seconds = _duration(cap_started, runtime.monotonic)
        return _diagnostic_sample(
            ticker=ticker,
            seed=seed,
            mode=mode,
            sample_index=sample_index,
            benchmark_as_of=as_of,
            cap_attempts=cap_attempts,
            assignment_hash=assignment.assignment_hash,
            source_identity=source_identity,
            split_identity=split_identity,
            preflight_seconds=preflight_seconds,
            cap_window_seconds=cap_seconds,
            total_seconds=_duration(preflight_started, runtime.monotonic),
            terminal_state="failed",
            safe_error_code="INFRA.WORKER_START",
            runtime=runtime,
            root=root,
        )

    cap_seconds = _duration(cap_started, runtime.monotonic)
    observed_total_seconds = _duration(preflight_started, runtime.monotonic)
    preflight_seconds = max(0.0, observed_total_seconds - cap_seconds)
    total_seconds = max(observed_total_seconds, preflight_seconds + cap_seconds)
    slot_timings, selection_seconds, write_seconds, child_rss = _read_cap_phase_telemetry(root)
    safe_error_code = manifest.safe_error_code
    if (
        safe_error_code is not None
        and (
            not isinstance(safe_error_code, str)
            or not _SAFE_ERROR.fullmatch(safe_error_code)
        )
    ):
        safe_error_code = "INVARIANT.MANIFEST_ERROR"
    return DiscoveryCapSample(
        ticker=ticker,
        seed=seed,
        mode=mode,
        sample_index=sample_index,
        benchmark_as_of=as_of,
        cap_attempts=cap_attempts,
        start_slot=start_slot,
        assignment_hash=assignment.assignment_hash,
        source_identity=source_identity,
        split_identity=split_identity,
        attempted_count=attempted,
        committed_count=committed,
        next_slot=next_slot,
        uncommitted_slot=uncommitted,
        preflight_seconds=preflight_seconds,
        cap_window_seconds=cap_seconds,
        total_seconds=total_seconds,
        slot_timings=slot_timings,
        selection_seconds=selection_seconds,
        write_seconds=write_seconds,
        terminal_state=manifest.state,
        safe_error_code=safe_error_code,
        peak_rss_bytes=child_rss if child_rss is not None else _probe(runtime.rss_probe),
        peak_pool_checkouts=_probe(runtime.pool_checkout_probe),
        cache_bytes=_tree_bytes(root / "cache"),
        artifact_bytes=max(0, _tree_bytes(root) - _tree_bytes(root / "cache")),
    )


def _exhausted_sample(
    *,
    ticker: str,
    as_of: date,
    seed: str,
    mode: Literal["cold", "warm"],
    sample_index: int,
    cap_attempts: int,
    runtime: CapBenchmarkRuntime,
    reference: DiscoveryCapSample | None,
) -> DiscoveryCapSample:
    assignment = assign_frontier(
        runtime.space,
        frontier_seed=seed,
        source_ticker=ticker,
        start_slot=sample_index * cap_attempts,
        budget=SearchBudget(attempt_count=cap_attempts, runtime=runtime.runtime_budget),
    )
    return _diagnostic_sample(
        ticker=ticker,
        seed=seed,
        mode=mode,
        sample_index=sample_index,
        benchmark_as_of=as_of,
        cap_attempts=cap_attempts,
        assignment_hash=assignment.assignment_hash,
        source_identity=None if reference is None else reference.source_identity,
        split_identity=None if reference is None else reference.split_identity,
        preflight_seconds=0.0,
        cap_window_seconds=0.0,
        total_seconds=0.0,
        terminal_state="interrupted",
        safe_error_code="BENCHMARK.TICKER_BUDGET_EXHAUSTED",
        runtime=runtime,
        root=Path(tempfile.gettempdir()).resolve() / "flexible-cap-benchmark-empty-observation",
    )


def production_cap_runtime() -> CapBenchmarkRuntime:
    """Build the production read-only runtime for a cap-sized campaign window."""

    base = production_sample_runtime()

    def execute(request: CampaignRequest, root: Path) -> CampaignManifest:
        from .benchmark_runner import benchmark_source_loader
        from .runner import (
            claim_campaign,
            start_campaign_worker,
            submit_campaign,
            watch_campaign_worker,
        )

        campaign_id = submit_campaign(request, root)
        claim_campaign(campaign_id, root)
        process = start_campaign_worker(
            campaign_id,
            root,
            service_ref="flexible_rulebook.cap_benchmark_runner:cap_benchmark_discovery_service",
            source_loader_ref="flexible_rulebook.benchmark_runner:benchmark_source_loader",
            process_group=True,
        )
        watchdog_seconds = _read_remaining_deadline(root)
        return watch_campaign_worker(
            process,
            campaign_id,
            root,
            watchdog_seconds=(
                request.runtime_budget.outer_worker_watchdog_seconds
                if watchdog_seconds is None
                else watchdog_seconds
            ),
            terminate_process_group=True,
        )

    return CapBenchmarkRuntime(
        catalog=base.catalog,
        history_loader=base.history_loader,
        feature_resolver=base.feature_resolver,
        campaign_executor=execute,
        cache_is_complete=base.cache_is_complete,
        monotonic=base.monotonic,
        # Production samples report worker-process RSS only through the
        # persisted worker telemetry; the coordinator has no child RSS value.
        rss_probe=lambda: None,
        pool_checkout_probe=base.pool_checkout_probe,
        build_contract=base.build_contract,
        execution_contract=base.execution_contract,
        runtime_budget=base.runtime_budget,
        selection_policy=base.selection_policy,
    )


def cap_benchmark_discovery_service(request):
    """Resolve a prebuilt isolated cache and persist cap-window timing events."""

    from .service import DiscoveryService
    from .worker_contract import WorkerRequest

    if not isinstance(request, WorkerRequest):
        raise ValueError("cap benchmark worker service requires a WorkerRequest")
    runtime = production_sample_runtime()
    started = time.monotonic()
    root = _outside_live_root(request.root)
    recorder = CapPhaseTelemetryRecorder(root, rss_probe=runtime.rss_probe)

    def feature_resolver(snapshot: HistorySnapshot) -> FeatureResolution:
        if not runtime.cache_is_complete(
            snapshot,
            runtime.build_contract,
            runtime.profile,
            root,
        ):
            raise ValueError("cap benchmark worker cache is incomplete")
        return runtime.feature_resolver(
            snapshot,
            runtime.build_contract,
            runtime.profile,
            root,
            "reuse",
        )

    return DiscoveryService(
        root,
        candidate_space=runtime.space,
        feature_resolver=feature_resolver,
        monotonic=lambda: time.monotonic() - started,
        phase_observer=recorder,
    )


def run_cap_benchmark(
    *,
    tickers: Sequence[str],
    as_of: date,
    seeds: Sequence[str],
    cap_attempts: int,
    cold_samples: int,
    output: Path,
    warm_samples: int = 0,
    ticker_budget_seconds: int = TERMINAL_SECONDS,
    runtime: CapBenchmarkRuntime | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    progress_fn: Callable[[ProgressEvent], None] | None = None,
) -> DiscoveryCapBenchmarkReport:
    """Run serial isolated cap windows and always persist immutable evidence."""

    ticker_values = _unique(tickers, "tickers", _ticker)
    seed_values = _unique(seeds, "seeds", _seed)
    if type(as_of) is not date:
        raise ValueError("as_of must be a date without a time")
    if isinstance(cap_attempts, bool) or not isinstance(cap_attempts, int) or cap_attempts <= 0:
        raise ValueError("cap_attempts must be a positive integer")
    if isinstance(cold_samples, bool) or not isinstance(cold_samples, int) or cold_samples < 100:
        raise ValueError("cold_samples must be at least 100")
    if isinstance(warm_samples, bool) or not isinstance(warm_samples, int) or warm_samples < 0:
        raise ValueError("warm_samples must be a non-negative integer")
    if (
        isinstance(ticker_budget_seconds, bool)
        or not isinstance(ticker_budget_seconds, int)
        or not 0 < ticker_budget_seconds <= TERMINAL_SECONDS
    ):
        raise ValueError("ticker_budget_seconds must stay within the 4h55 terminal limit")
    if not callable(monotonic):
        raise ValueError("monotonic must be callable")
    if progress_fn is not None and not callable(progress_fn):
        raise ValueError("progress_fn must be callable or None")
    target = validate_benchmark_output_path(output)
    actual_runtime = production_cap_runtime() if runtime is None else runtime
    if not isinstance(actual_runtime, CapBenchmarkRuntime):
        raise ValueError("runtime must be CapBenchmarkRuntime or None")
    if cold_samples * cap_attempts > actual_runtime.space.size:
        raise ValueError("cold cap windows exceed CandidateSpace")
    if warm_samples * cap_attempts > actual_runtime.space.size:
        raise ValueError("warm cap windows exceed CandidateSpace")

    samples: list[DiscoveryCapSample] = []
    ticker_elapsed: list[tuple[str, float]] = []
    total_windows = len(ticker_values) * len(seed_values) * (cold_samples + warm_samples)
    completed_windows = 0

    def emit_progress(event: ProgressEvent) -> None:
        if progress_fn is None:
            return
        try:
            progress_fn(event)
        except Exception:
            # Telemetry must never change benchmark evidence or eligibility.
            return

    for ticker in ticker_values:
        ticker_started = float(monotonic())
        ticker_deadline = ticker_started + ticker_budget_seconds
        reference: DiscoveryCapSample | None = None
        for seed in seed_values:
            for mode, sample_count in (("cold", cold_samples), ("warm", warm_samples)):
                for sample_index in range(sample_count):
                    elapsed = _duration(ticker_started, monotonic)
                    if elapsed >= ticker_budget_seconds:
                        sample = _exhausted_sample(
                            ticker=ticker,
                            as_of=as_of,
                            seed=seed,
                            mode=mode,
                            sample_index=sample_index,
                            cap_attempts=cap_attempts,
                            runtime=actual_runtime,
                            reference=reference,
                        )
                    else:
                        with tempfile.TemporaryDirectory(prefix="flexible-cap-benchmark-") as directory:
                            sample = run_cap_window(
                                ticker=ticker,
                                as_of=as_of,
                                seed=seed,
                                mode=mode,
                                sample_index=sample_index,
                                cap_attempts=cap_attempts,
                                root=Path(directory).resolve(),
                                runtime=actual_runtime,
                                remaining_seconds=lambda deadline=ticker_deadline: max(
                                    0,
                                    math.ceil(deadline - float(monotonic())),
                                ),
                            )
                    samples.append(sample)
                    completed_windows += 1
                    emit_progress(
                        ProgressEvent(
                            phase="benchmark",
                            completed=completed_windows,
                            total=total_windows,
                            label=f"{ticker} / {seed} / {mode} window {sample_index + 1}",
                            safe_error=sample.safe_error_code,
                        )
                    )
                    if sample.source_identity is not None and sample.split_identity is not None:
                        reference = sample
        observed = _duration(ticker_started, monotonic)
        total_samples = sum(sample.total_seconds for sample in samples if sample.ticker == ticker)
        ticker_elapsed.append((ticker, max(observed, total_samples)))

    report = DiscoveryCapBenchmarkReport(
        benchmark_as_of=as_of,
        tickers=ticker_values,
        seeds=seed_values,
        cap_attempts=cap_attempts,
        runtime_contract_identity=discovery_runtime_contract_identity(actual_runtime),
        samples=tuple(samples),
        ticker_elapsed_seconds_by_ticker=tuple(ticker_elapsed),
    )
    write_cap_benchmark_report(target, report)
    return report


def main(argv: list[str] | None = None) -> int:
    """Run an explicit fixed-cap benchmark; ineligible evidence exits with 2."""

    parser = argparse.ArgumentParser(
        description="Run a read-only Flexible Rulebook fixed-cap benchmark."
    )
    parser.add_argument("--tickers", nargs="+", help="Explicit ticker symbols")
    parser.add_argument("--as-of", help="Fixed YYYY-MM-DD source boundary")
    parser.add_argument("--seed", action="append", help="Frozen frontier seed; repeatable")
    parser.add_argument("--cap-attempts", type=int, help="Exact attempted slots per cap window")
    parser.add_argument("--cold-samples", type=int, help="Cold cap windows per ticker and seed")
    parser.add_argument("--warm-samples", type=int, default=0, help="Diagnostic warm cap windows")
    parser.add_argument("--output", help="Absolute cap report path outside Flexible-Rulebook")
    arguments = parser.parse_args(argv)
    missing = [
        name
        for name, value in (
            ("--tickers", arguments.tickers),
            ("--as-of", arguments.as_of),
            ("--seed", arguments.seed),
            ("--cap-attempts", arguments.cap_attempts),
            ("--cold-samples", arguments.cold_samples),
            ("--output", arguments.output),
        )
        if value is None
    ]
    if missing:
        parser.error(f"missing required arguments: {', '.join(missing)}")
    try:
        as_of = date.fromisoformat(arguments.as_of)
        report = run_cap_benchmark(
            tickers=arguments.tickers,
            as_of=as_of,
            seeds=arguments.seed,
            cap_attempts=arguments.cap_attempts,
            cold_samples=arguments.cold_samples,
            warm_samples=arguments.warm_samples,
            output=Path(arguments.output),
        )
    except ValueError as error:
        parser.error(str(error))
    print(f"Cap benchmark report: {Path(arguments.output).resolve()}")
    if not report.is_eligible:
        print("Cap benchmark result: ineligible evidence recorded; discovery remains disabled.")
        return 2
    print("Cap benchmark result: eligible evidence recorded; policy remains unchanged pending review.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "CapBenchmarkRuntime",
    "CapPhaseTelemetryRecorder",
    "cap_benchmark_discovery_service",
    "discovery_runtime_contract_identity",
    "main",
    "production_cap_runtime",
    "run_cap_benchmark",
    "run_cap_window",
]
