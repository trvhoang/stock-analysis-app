"""Read-only production benchmark runner for Flexible Rulebook discovery.

The public CLI is intentionally separate from Streamlit and policy loading.
Each sample receives an isolated storage root, records every failure truthfully,
and can only produce evidence for later human review.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Callable, Literal

import pytz

from .benchmark import (
    BenchmarkSample,
    ProductionBenchmarkReport,
    TERMINAL_SECONDS,
    write_production_benchmark_report,
)
from .cap_benchmark import SlotPhaseTiming, WindowPhaseTiming
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
from .features import (
    FeatureResolution,
    current_feature_build_contract,
    feature_snapshot_for_history,
    inspect_primitive_cache,
    resolve_feature_store,
)
from .history import HistorySnapshot, load_flexible_history, make_evaluation_split
from .runner import claim_campaign, start_campaign_worker, submit_campaign, watch_campaign_worker
from .worker_contract import WorkerRequest
from .search import CandidateSpace, SearchBudget, assign_frontier, candidate_space, scheduled_candidates
from .service import DiscoveryService
from .storage import resolve_flexible_root
from .worker import WorkerRequest


_HCM = pytz.timezone("Asia/Ho_Chi_Minh")
_TICKER = re.compile(r"^[A-Z0-9._-]+$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


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


def _duration(start: float, monotonic: Callable[[], float]) -> float:
    """Return a truthful non-negative elapsed duration from an injected clock."""

    value = float(monotonic()) - start
    return value if value >= 0.0 else 0.0


def _contained(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def validate_benchmark_output_path(path: Path | str) -> Path:
    """Accept only an absolute report path outside live Flexible evidence."""

    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError("benchmark output path must be absolute")
    resolved = candidate.resolve()
    production_root = resolve_flexible_root().resolve()
    if _contained(resolved, production_root):
        raise ValueError("benchmark output cannot be inside the Flexible Rulebook evidence root")
    if resolved.exists() and resolved.is_dir():
        raise ValueError("benchmark output path must name a file")
    return resolved


def _validate_isolated_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("benchmark sample root must be absolute")
    resolved = root.resolve()
    if _contained(resolved, resolve_flexible_root().resolve()):
        raise ValueError("benchmark sample root cannot be inside the Flexible Rulebook evidence root")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


@dataclass(frozen=True)
class BenchmarkSampleRequest:
    """One frozen one-slot measurement request before data is loaded."""

    ticker: str
    as_of: date
    seed: str
    global_slot: int
    mode: Literal["cold", "warm"]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _ticker(self.ticker))
        if type(self.as_of) is not date:
            raise ValueError("as_of must be a date without a time")
        object.__setattr__(self, "seed", _seed(self.seed))
        if isinstance(self.global_slot, bool) or not isinstance(self.global_slot, int) or self.global_slot < 0:
            raise ValueError("global_slot must be a non-negative integer")
        if self.mode not in {"cold", "warm"}:
            raise ValueError("mode must be cold or warm")


@dataclass(frozen=True)
class BenchmarkExecution:
    """Worker result plus measured subphases written by the isolated worker."""

    manifest: CampaignManifest
    training_seconds: float | None
    test_seconds: float | None
    selection_seconds: float | None
    write_seconds: float | None
    reached_maximal_path: bool
    worker_source_fingerprint: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, CampaignManifest):
            raise ValueError("benchmark execution requires CampaignManifest")
        for name in (
            "training_seconds", "test_seconds", "selection_seconds", "write_seconds",
        ):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0.0):
                raise ValueError(f"{name} must be non-negative or None")
        if not isinstance(self.reached_maximal_path, bool):
            raise ValueError("reached_maximal_path must be boolean")
        if self.worker_source_fingerprint is not None and (
            not isinstance(self.worker_source_fingerprint, str)
            or not _HASH.fullmatch(self.worker_source_fingerprint)
        ):
            raise ValueError("worker_source_fingerprint must be a digest or None")


@dataclass(frozen=True)
class BenchmarkSampleRuntime:
    """Injected runtime seams; production supplies real loader and worker calls."""

    catalog: CatalogRevision
    history_loader: Callable[[str, date], HistorySnapshot]
    feature_resolver: Callable[
        [HistorySnapshot, FeatureBuildContract, FeatureProfile, Path, Literal["reuse", "rebuild"]],
        FeatureResolution,
    ]
    campaign_executor: Callable[[CampaignRequest, Path], BenchmarkExecution]
    cache_is_complete: Callable[[HistorySnapshot, FeatureBuildContract, FeatureProfile, Path], bool]
    monotonic: Callable[[], float]
    rss_probe: Callable[[], int | None]
    pool_checkout_probe: Callable[[], int | None]
    worker_preparer: Callable[[CampaignRequest, FeatureResolution, Path], None] = (
        lambda _request, _features, _root: None
    )
    build_contract: FeatureBuildContract = field(default_factory=current_feature_build_contract)
    execution_contract: ExecutionContract = field(default_factory=ExecutionContract)
    runtime_budget: RuntimeBudget = field(default_factory=RuntimeBudget)
    selection_policy: SelectionPolicy = field(default_factory=SelectionPolicy)
    engine_revision: str = "flexible-benchmark-runner-v1"
    _space: CandidateSpace = field(init=False, repr=False, compare=False)
    _profile: FeatureProfile = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, CatalogRevision):
            raise ValueError("benchmark runtime requires a catalog")
        if not isinstance(self.build_contract, FeatureBuildContract):
            raise ValueError("benchmark runtime requires FeatureBuildContract")
        if not isinstance(self.execution_contract, ExecutionContract):
            raise ValueError("benchmark runtime requires ExecutionContract")
        if not isinstance(self.runtime_budget, RuntimeBudget):
            raise ValueError("benchmark runtime requires RuntimeBudget")
        if not isinstance(self.selection_policy, SelectionPolicy):
            raise ValueError("benchmark runtime requires SelectionPolicy")
        if not isinstance(self.engine_revision, str) or not self.engine_revision:
            raise ValueError("benchmark runtime engine_revision must be non-empty")
        if not all(callable(getattr(self, name)) for name in (
            "history_loader", "feature_resolver", "campaign_executor", "cache_is_complete",
            "monotonic", "rss_probe", "pool_checkout_probe", "worker_preparer",
        )):
            raise ValueError("benchmark runtime dependencies must be callable")
        object.__setattr__(self, "_space", candidate_space(self.catalog))
        object.__setattr__(self, "_profile", feature_profile(self.catalog))

    @property
    def space(self) -> CandidateSpace:
        return self._space

    @property
    def profile(self) -> FeatureProfile:
        return self._profile


def _slot_provenance(request: BenchmarkSampleRequest, runtime: BenchmarkSampleRuntime) -> tuple[str, int]:
    assignment = assign_frontier(
        runtime.space,
        frontier_seed=request.seed,
        source_ticker=request.ticker,
        start_slot=request.global_slot,
        budget=SearchBudget(attempt_count=1, runtime=runtime.runtime_budget),
    )
    _slot, stratum_id, canonical_index, _definition = next(scheduled_candidates(runtime.space, assignment))
    return stratum_id, canonical_index


def _campaign_request(
    request: BenchmarkSampleRequest,
    runtime: BenchmarkSampleRuntime,
    snapshot: HistorySnapshot,
    features: FeatureResolution,
) -> CampaignRequest:
    if snapshot.quality_state != "eligible" or snapshot.fingerprint is None:
        raise ValueError("data_ineligible")
    source = feature_snapshot_for_history(snapshot)
    if (
        features.plan.snapshot != source
        or features.plan.build_contract != runtime.build_contract
        or features.plan.profile != runtime.profile
    ):
        raise ValueError("feature resolution does not match benchmark profile")
    assignment = assign_frontier(
        runtime.space,
        frontier_seed=request.seed,
        source_ticker=request.ticker,
        start_slot=request.global_slot,
        budget=SearchBudget(attempt_count=1, runtime=runtime.runtime_budget),
    )
    return CampaignRequest(
        operation="discover",
        frozen_members=(request.ticker,),
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
        per_ticker_budget=1,
        frontier_assignment=assignment,
    )


def _failure_sample(
    request: BenchmarkSampleRequest,
    *,
    root: Path,
    stratum_id: str,
    canonical_index: int,
    source_fingerprint: str | None,
    preflight_seconds: float | None,
    maximal_slot_seconds: float | None,
    terminal_state: str,
    safe_error_code: str,
    runtime: BenchmarkSampleRuntime,
) -> BenchmarkSample:
    return BenchmarkSample(
        ticker=request.ticker,
        seed=request.seed,
        global_slot=request.global_slot,
        canonical_index=canonical_index,
        frontier_stratum=stratum_id,
        mode=request.mode,
        source_fingerprint=source_fingerprint,
        preflight_seconds=preflight_seconds,
        training_seconds=None,
        test_seconds=None,
        selection_seconds=None,
        write_seconds=None,
        maximal_slot_seconds=maximal_slot_seconds,
        terminal_state=terminal_state,
        safe_error_code=safe_error_code,
        reached_maximal_path=False,
        peak_rss_bytes=runtime.rss_probe(),
        peak_pool_checkouts=runtime.pool_checkout_probe(),
        cache_bytes=_tree_bytes(root / "cache"),
        artifact_bytes=max(0, _tree_bytes(root) - _tree_bytes(root / "cache")),
        split_identity="{}",
    )


def _tree_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


_WORKER_CONFIG_NAME = ".flexible-benchmark-worker-v1.json"
_PHASE_TELEMETRY_NAME = ".flexible-benchmark-phases-v1.json"
_WARM_PREPARATION_NAME = ".flexible-benchmark-warm-preparation-v1.json"
_PHASE_NAMES = ("training", "test", "selection", "write")


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    """Write small operational benchmark state atomically inside one temp root."""

    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, mode="w", encoding="utf-8", delete=False
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


def _worker_config_path(root: Path) -> Path:
    return _validate_isolated_root(root) / _WORKER_CONFIG_NAME


def _warm_preparation_path(root: Path) -> Path:
    return _validate_isolated_root(root) / _WARM_PREPARATION_NAME


def _read_warm_preparation_fingerprint(root: Path) -> str | None:
    try:
        payload = json.loads(_warm_preparation_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = payload.get("source_fingerprint") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "kind", "source_fingerprint", "feature_plan_hash"}
        or payload.get("schema_version") != 1
        or payload.get("kind") != "flexible_rulebook_benchmark_warm_preparation"
        or not isinstance(value, str)
        or not _HASH.fullmatch(value)
        or not isinstance(payload.get("feature_plan_hash"), str)
        or not re.fullmatch(r"frpl_[0-9a-f]{64}", payload["feature_plan_hash"])
    ):
        return None
    return value


def _write_worker_config(
    request: CampaignRequest,
    features: FeatureResolution,
    root: Path,
) -> None:
    """Freeze only operational worker inputs under the isolated sample root."""

    if not isinstance(request, CampaignRequest) or not isinstance(features, FeatureResolution):
        raise ValueError("benchmark worker config requires frozen campaign and features")
    _atomic_json(
        _worker_config_path(root),
        {
            "schema_version": 1,
            "kind": "flexible_rulebook_benchmark_worker",
            "cache_choice": "reuse",
            "catalog_hash": request.catalog_hash,
            "feature_build_contract_hash": features.plan.build_contract.feature_build_contract_hash,
            "feature_profile_hash": features.plan.profile.feature_profile_hash,
            "feature_plan_hash": features.plan.feature_plan_hash,
            "engine_revision": request.engine_revision,
        },
    )


def _read_worker_config(root: Path) -> dict[str, object]:
    path = _worker_config_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("benchmark worker configuration is unavailable") from error
    required = {
        "schema_version", "kind", "cache_choice", "catalog_hash",
        "feature_build_contract_hash", "feature_profile_hash", "feature_plan_hash",
        "engine_revision",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("benchmark worker configuration is invalid")
    if (
        payload["schema_version"] != 1
        or payload["kind"] != "flexible_rulebook_benchmark_worker"
        or payload["cache_choice"] != "reuse"
        or not isinstance(payload["catalog_hash"], str)
        or not _HASH.fullmatch(payload["catalog_hash"])
        or not isinstance(payload["feature_build_contract_hash"], str)
        or not re.fullmatch(r"frbc_[0-9a-f]{64}", payload["feature_build_contract_hash"])
        or not isinstance(payload["feature_profile_hash"], str)
        or not re.fullmatch(r"frfp_[0-9a-f]{64}", payload["feature_profile_hash"])
        or not isinstance(payload["feature_plan_hash"], str)
        or not re.fullmatch(r"frpl_[0-9a-f]{64}", payload["feature_plan_hash"])
        or not isinstance(payload["engine_revision"], str)
        or not payload["engine_revision"]
    ):
        raise ValueError("benchmark worker configuration is invalid")
    return payload


class _PhaseTelemetryRecorder:
    """Persist phase durations as worker-owned diagnostic state after each phase."""

    def __init__(self, root: Path) -> None:
        self._path = _validate_isolated_root(root) / _PHASE_TELEMETRY_NAME
        self._values: dict[str, float | None] = {name: None for name in _PHASE_NAMES}

    def __call__(self, event: SlotPhaseTiming | WindowPhaseTiming) -> None:
        if not isinstance(event, (SlotPhaseTiming, WindowPhaseTiming)):
            raise ValueError("benchmark phase telemetry event is invalid")
        if event.phase == "entry_mask":
            return
        if event.phase not in self._values or self._values[event.phase] is not None:
            raise ValueError("benchmark phase telemetry is invalid or duplicated")
        value = float(event.seconds)
        if value < 0.0:
            raise ValueError("benchmark phase duration cannot be negative")
        self._values[event.phase] = value
        _atomic_json(
            self._path,
            {
                "schema_version": 1,
                "kind": "flexible_rulebook_benchmark_phases",
                "phases": self._values,
            },
        )


def _read_phase_telemetry(root: Path) -> dict[str, float | None]:
    path = _validate_isolated_root(root) / _PHASE_TELEMETRY_NAME
    empty = {name: None for name in _PHASE_NAMES}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    phases = payload.get("phases") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("kind") != "flexible_rulebook_benchmark_phases"
        or not isinstance(phases, dict)
        or set(phases) != set(_PHASE_NAMES)
    ):
        return empty
    values: dict[str, float | None] = {}
    for name in _PHASE_NAMES:
        value = phases[name]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0.0
        ):
            return empty
        values[name] = None if value is None else float(value)
    return values


def _cache_is_complete(
    snapshot: HistorySnapshot,
    contract: FeatureBuildContract,
    profile: FeatureProfile,
    root: Path,
) -> bool:
    offer = inspect_primitive_cache(
        snapshot,
        contract,
        profile,
        root,
        datetime.now(_HCM),
    )
    expected = len(profile.primitive_specs)
    return (
        len(offer.reusable_keys) == expected
        and not offer.stale_keys
        and not offer.missing_keys
    )


def _resolve_production_features(
    snapshot: HistorySnapshot,
    contract: FeatureBuildContract,
    profile: FeatureProfile,
    root: Path,
    choice: Literal["reuse", "rebuild"],
) -> FeatureResolution:
    return resolve_feature_store(
        snapshot,
        contract,
        profile,
        root,
        choice=choice,
        now=datetime.now(_HCM),
    )


def benchmark_discovery_service(request: WorkerRequest) -> DiscoveryService:
    """Top-level worker factory; it accepts only a fully prebuilt cache receipt."""

    if not isinstance(request, WorkerRequest):
        raise ValueError("benchmark worker service requires a WorkerRequest")
    root = _validate_isolated_root(request.root)
    config = _read_worker_config(root)
    catalog = catalog_revision_1()
    contract = current_feature_build_contract()
    profile = feature_profile(catalog)
    if (
        config["catalog_hash"] != catalog.catalog_hash
        or config["feature_build_contract_hash"] != contract.feature_build_contract_hash
        or config["feature_profile_hash"] != profile.feature_profile_hash
        or config["engine_revision"] != "flexible-benchmark-runner-v1"
    ):
        raise ValueError("benchmark worker configuration does not match the production contract")
    recorder = _PhaseTelemetryRecorder(root)
    worker_started = time.monotonic()

    def resolve_verified_source(snapshot: HistorySnapshot) -> FeatureResolution:
        # ``resolve_feature_store(... reuse)`` may safely build a miss for the
        # normal product. A benchmark must reject that path: it is measuring a
        # preflight-built cache crossing a process boundary, not an accidental
        # second feature build in the worker.
        if not _cache_is_complete(snapshot, contract, profile, root):
            raise ValueError("benchmark worker cache is incomplete")
        resolution = _resolve_production_features(snapshot, contract, profile, root, "reuse")
        if resolution.plan.feature_plan_hash != config["feature_plan_hash"]:
            raise ValueError("benchmark worker feature plan changed")
        return resolution

    return DiscoveryService(
        root,
        candidate_space=candidate_space(catalog),
        feature_resolver=resolve_verified_source,
        monotonic=lambda: time.monotonic() - worker_started,
        phase_observer=recorder,
    )


def _load_history_with_engine(ticker: str, as_of: date) -> HistorySnapshot:
    """Open a short-lived read-only-use engine using the established env helper."""

    from backtest_engine.pipeline import _database_url
    from pages.data_preparation import get_engine_with_retry

    engine = get_engine_with_retry(_database_url())
    try:
        return load_flexible_history(engine, ticker, as_of=as_of)
    finally:
        engine.dispose()


def benchmark_source_loader(expected: object) -> HistorySnapshot:
    """Top-level worker loader; `run_campaign` proves every frozen field."""

    ticker = getattr(expected, "ticker", None)
    as_of = getattr(expected, "requested_as_of", None)
    if not isinstance(ticker, str) or type(as_of) is not date:
        raise ValueError("worker expected source is invalid")
    return _load_history_with_engine(ticker, as_of)


def _outcome_reached_test(root: Path, manifest: CampaignManifest) -> bool:
    assignment = manifest.request.frontier_assignment
    if assignment is None:
        return False
    directory = root / "campaigns" / manifest.campaign_id / "ledger" / manifest.request.frozen_members[0]
    if not directory.is_dir():
        return False
    for path in directory.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("rows") if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if (
                isinstance(row, dict)
                and row.get("global_slot") == assignment.start_slot
                and row.get("outcome") in {"qualified", "test_threshold"}
            ):
                return True
    return False


def _execute_campaign_through_worker(
    request: CampaignRequest,
    root: Path,
) -> BenchmarkExecution:
    campaign_id = submit_campaign(request, root)
    claim_campaign(campaign_id, root)
    process = start_campaign_worker(
        campaign_id,
        root,
        service_ref="flexible_rulebook.benchmark_runner:benchmark_discovery_service",
        source_loader_ref="flexible_rulebook.benchmark_runner:benchmark_source_loader",
    )
    manifest = watch_campaign_worker(
        process,
        campaign_id,
        root,
        watchdog_seconds=request.runtime_budget.outer_worker_watchdog_seconds,
    )
    phases = _read_phase_telemetry(root)
    # A persisted feature receipt is only written after exact worker source
    # verification. Source mismatch before that is retained as a blocked run.
    worker_fingerprint = (
        request.source_snapshots[0].raw_history_fingerprint
        if manifest.feature_receipt_ids
        else None
    )
    return BenchmarkExecution(
        manifest=manifest,
        training_seconds=phases["training"],
        test_seconds=phases["test"],
        selection_seconds=phases["selection"],
        write_seconds=phases["write"],
        reached_maximal_path=_outcome_reached_test(root, manifest),
        worker_source_fingerprint=worker_fingerprint,
    )


@dataclass
class _ClientPoolCheckoutProbe:
    """Best-effort client-process checkout count; never a server-side metric."""

    current: int = 0
    peak: int = 0

    def checkout(self, *_args: object) -> None:
        self.current += 1
        self.peak = max(self.peak, self.current)

    def checkin(self, *_args: object) -> None:
        self.current = max(0, self.current - 1)

    def read(self) -> int:
        return self.peak


def _load_history_with_pool_probe(
    ticker: str,
    as_of: date,
    probe: _ClientPoolCheckoutProbe,
) -> HistorySnapshot:
    from sqlalchemy import event

    from backtest_engine.pipeline import _database_url
    from pages.data_preparation import get_engine_with_retry

    engine = get_engine_with_retry(_database_url())
    event.listen(engine.pool, "checkout", probe.checkout)
    event.listen(engine.pool, "checkin", probe.checkin)
    try:
        return load_flexible_history(engine, ticker, as_of=as_of)
    finally:
        event.remove(engine.pool, "checkout", probe.checkout)
        event.remove(engine.pool, "checkin", probe.checkin)
        engine.dispose()


def _peak_child_rss_bytes() -> int | None:
    """Return fresh benchmark-child high-water RSS, if this OS exposes it."""

    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (ImportError, AttributeError, OSError, ValueError):
        return None
    # Linux reports KiB; macOS reports bytes. Windows normally has no resource.
    return value if sys.platform == "darwin" else value * 1024


def production_sample_runtime() -> BenchmarkSampleRuntime:
    """Build the real DB/cache/worker runtime for one fresh sample process."""

    pool_probe = _ClientPoolCheckoutProbe()
    return BenchmarkSampleRuntime(
        catalog=catalog_revision_1(),
        history_loader=lambda ticker, as_of: _load_history_with_pool_probe(ticker, as_of, pool_probe),
        feature_resolver=_resolve_production_features,
        campaign_executor=_execute_campaign_through_worker,
        cache_is_complete=_cache_is_complete,
        monotonic=time.monotonic,
        rss_probe=_peak_child_rss_bytes,
        pool_checkout_probe=pool_probe.read,
        worker_preparer=_write_worker_config,
    )


def _sample_request_payload(
    request: BenchmarkSampleRequest,
    *,
    root: Path,
    result_path: Path,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "flexible_rulebook_benchmark_sample_request",
        "root": str(root),
        "result_path": str(result_path),
        "request": {
            "ticker": request.ticker,
            "as_of": request.as_of.isoformat(),
            "seed": request.seed,
            "global_slot": request.global_slot,
            "mode": request.mode,
        },
    }


def _read_sample_request(path: Path) -> tuple[BenchmarkSampleRequest, Path, Path]:
    if not path.is_absolute():
        raise ValueError("benchmark sample request path must be absolute")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("benchmark sample request is unreadable") from error
    required = {"schema_version", "kind", "root", "result_path", "request"}
    if (
        not isinstance(payload, dict)
        or set(payload) != required
        or payload["schema_version"] != 1
        or payload["kind"] != "flexible_rulebook_benchmark_sample_request"
        or not isinstance(payload["root"], str)
        or not isinstance(payload["result_path"], str)
        or not isinstance(payload["request"], dict)
    ):
        raise ValueError("benchmark sample request is invalid")
    root = _validate_isolated_root(Path(payload["root"]))
    result_path = Path(payload["result_path"])
    if not result_path.is_absolute() or not _contained(result_path.resolve(), root):
        raise ValueError("benchmark sample result path escapes isolated root")
    request_payload = payload["request"]
    if set(request_payload) != {"ticker", "as_of", "seed", "global_slot", "mode"}:
        raise ValueError("benchmark sample request fields are invalid")
    try:
        as_of = date.fromisoformat(request_payload["as_of"])
    except (TypeError, ValueError) as error:
        raise ValueError("benchmark sample request as_of is invalid") from error
    return (
        BenchmarkSampleRequest(
            ticker=request_payload["ticker"],
            as_of=as_of,
            seed=request_payload["seed"],
            global_slot=request_payload["global_slot"],
            mode=request_payload["mode"],
        ),
        root,
        result_path.resolve(),
    )


def _unmeasured_child_failure(
    request: BenchmarkSampleRequest,
    *,
    safe_error_code: str,
) -> BenchmarkSample:
    space = candidate_space(catalog_revision_1())
    assignment = assign_frontier(
        space,
        frontier_seed=request.seed,
        source_ticker=request.ticker,
        start_slot=request.global_slot,
        budget=SearchBudget(attempt_count=1),
    )
    _slot, stratum, canonical, _definition = next(scheduled_candidates(space, assignment))
    return BenchmarkSample(
        ticker=request.ticker,
        seed=request.seed,
        global_slot=request.global_slot,
        canonical_index=canonical,
        frontier_stratum=stratum,
        split_identity="{}",
        mode=request.mode,
        source_fingerprint=None,
        preflight_seconds=None,
        training_seconds=None,
        test_seconds=None,
        selection_seconds=None,
        write_seconds=None,
        maximal_slot_seconds=None,
        terminal_state="failed",
        safe_error_code=safe_error_code,
        reached_maximal_path=False,
        peak_rss_bytes=None,
        peak_pool_checkouts=None,
        cache_bytes=0,
        artifact_bytes=0,
    )


def _write_sample_result(path: Path, sample: BenchmarkSample) -> None:
    _atomic_json(
        path,
        {
            "schema_version": 1,
            "kind": "flexible_rulebook_benchmark_sample_result",
            "sample": sample.to_dict(),
        },
    )


def _read_sample_result(path: Path) -> BenchmarkSample:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("benchmark sample result is unreadable") from error
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "kind", "sample"}
        or payload["schema_version"] != 1
        or payload["kind"] != "flexible_rulebook_benchmark_sample_result"
    ):
        raise ValueError("benchmark sample result is invalid")
    return BenchmarkSample.from_dict(payload["sample"])


def _run_internal_sample(request_path: Path) -> int:
    request, root, result_path = _read_sample_request(request_path)
    try:
        runtime = production_sample_runtime()
        if request.mode == "warm":
            try:
                prepare_warm_sample_cache(request, root, runtime=runtime)
            except Exception:
                sample = _unmeasured_child_failure(
                    request,
                    safe_error_code="FEATURE.WARM_PREPOPULATION_FAILED",
                )
            else:
                sample = run_benchmark_sample(request, root, runtime=runtime)
        else:
            sample = run_benchmark_sample(request, root, runtime=runtime)
    except Exception:
        sample = _unmeasured_child_failure(
            request,
            safe_error_code="INFRA.SAMPLE_RUNTIME",
        )
    _write_sample_result(result_path, sample)
    return 0


def _terminate_sample_process(process: subprocess.Popen[object]) -> None:
    """Stop a timed-out benchmark child and its worker before temp cleanup."""

    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:  # pragma: no cover - Docker is the production target.
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        else:  # pragma: no cover - Docker is the production target.
            process.kill()
        process.wait()


def _run_isolated_sample(
    request: BenchmarkSampleRequest,
    *,
    timeout_seconds: int = TERMINAL_SECONDS,
) -> BenchmarkSample:
    """Use a fresh benchmark-child process so RSS is not cumulative across slots."""

    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or timeout_seconds <= 0
    ):
        raise ValueError("benchmark sample timeout must be a positive integer")
    with tempfile.TemporaryDirectory(prefix="flexible-benchmark-") as directory:
        root = Path(directory).resolve()
        request_path = root / "sample-request.json"
        result_path = root / "sample-result.json"
        _atomic_json(
            request_path,
            _sample_request_payload(request, root=root, result_path=result_path),
        )
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "flexible_rulebook.benchmark_runner", "--_sample-request", str(request_path)],
                cwd=Path(__file__).resolve().parents[1],
                start_new_session=os.name == "posix",
            )
        except OSError:
            return _unmeasured_child_failure(
                request,
                safe_error_code="INFRA.SAMPLE_PROCESS_FAILED",
            )
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_sample_process(process)
            return _unmeasured_child_failure(
                request,
                safe_error_code="INFRA.SAMPLE_PROCESS_TIMEOUT",
            )
        try:
            sample = _read_sample_result(result_path)
        except ValueError:
            return _unmeasured_child_failure(
                request,
                safe_error_code="INFRA.SAMPLE_PROCESS_FAILED",
            )
        if process.returncode != 0 and sample.is_complete:
            return _unmeasured_child_failure(
                request,
                safe_error_code="INFRA.SAMPLE_PROCESS_FAILED",
            )
        return sample


def _unique_requests(values: object, name: str, normalizer: Callable[[object], str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        normalized = tuple(normalizer(value) for value in values)  # type: ignore[arg-type]
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    if not normalized or len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must be non-empty and unique")
    return normalized


def run_production_benchmark(
    *,
    tickers: tuple[str, ...] | list[str],
    as_of: date,
    seeds: tuple[str, ...] | list[str],
    cold_samples: int,
    warm_samples: int,
    output: Path | str,
    sample_runner: Callable[[BenchmarkSampleRequest], BenchmarkSample] = _run_isolated_sample,
    ticker_budget_seconds: int = TERMINAL_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
) -> ProductionBenchmarkReport:
    """Run serial isolated samples and always write their immutable report.

    A returned report can be ineligible. This function intentionally does not
    derive or load a `ScalePolicy`; CLI exits non-zero in that case.
    """

    ticker_values = _unique_requests(tickers, "tickers", _ticker)
    seed_values = _unique_requests(seeds, "seeds", _seed)
    if type(as_of) is not date:
        raise ValueError("as_of must be a date without a time")
    for name, value, minimum in (
        ("cold_samples", cold_samples, 1),
        ("warm_samples", warm_samples, 0),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} is invalid")
    if not callable(sample_runner):
        raise ValueError("sample_runner must be callable")
    if not callable(monotonic):
        raise ValueError("monotonic must be callable")
    if (
        isinstance(ticker_budget_seconds, bool)
        or not isinstance(ticker_budget_seconds, int)
        or not 0 < ticker_budget_seconds <= TERMINAL_SECONDS
    ):
        raise ValueError("ticker_budget_seconds must stay within the 4h55 terminal limit")
    target = validate_benchmark_output_path(output)
    catalog = catalog_revision_1()
    contract = current_feature_build_contract()
    execution = ExecutionContract()
    space = candidate_space(catalog)
    samples: list[BenchmarkSample] = []
    for ticker in ticker_values:
        ticker_deadline = float(monotonic()) + ticker_budget_seconds
        for seed in seed_values:
            for mode, count in (("cold", cold_samples), ("warm", warm_samples)):
                for global_slot in range(count):
                    request = BenchmarkSampleRequest(ticker, as_of, seed, global_slot, mode)
                    remaining = int(ticker_deadline - float(monotonic()))
                    if remaining <= 0:
                        sample = _unmeasured_child_failure(
                            request,
                            safe_error_code="BENCHMARK.TICKER_BUDGET_EXHAUSTED",
                        )
                    else:
                        try:
                            sample = (
                                _run_isolated_sample(request, timeout_seconds=remaining)
                                if sample_runner is _run_isolated_sample
                                else sample_runner(request)
                            )
                        except Exception:
                            sample = _unmeasured_child_failure(
                                request,
                                safe_error_code="INFRA.SAMPLE_COORDINATOR",
                            )
                    if not isinstance(sample, BenchmarkSample) or sample.identity != (
                        ticker, seed, mode, global_slot
                    ):
                        raise ValueError("sample runner returned incompatible benchmark evidence")
                    samples.append(sample)
    report = ProductionBenchmarkReport(
        as_of=as_of,
        tickers=ticker_values,
        seeds=seed_values,
        catalog_hash=catalog.catalog_hash,
        feature_build_contract_hash=contract.feature_build_contract_hash,
        candidate_space_hash=space.candidate_space_hash,
        split_identity=canonical_json({"split_scope": "per_sample_frozen_identity_v1"}),
        execution_contract_identity=canonical_json(execution.to_identity_dict()),
        samples=tuple(samples),
    )
    write_production_benchmark_report(target, report)
    return report


def prepare_warm_sample_cache(
    request: BenchmarkSampleRequest,
    root: Path,
    *,
    runtime: BenchmarkSampleRuntime,
) -> HistorySnapshot:
    """Build a full isolated warm cache before timed warm preflight begins."""

    if request.mode != "warm":
        raise ValueError("warm cache preparation requires a warm sample request")
    root = _validate_isolated_root(root)
    snapshot = runtime.history_loader(request.ticker, request.as_of)
    if (
        not isinstance(snapshot, HistorySnapshot)
        or snapshot.quality_state != "eligible"
        or snapshot.fingerprint is None
    ):
        raise ValueError("warm cache requires eligible fresh history")
    resolution = runtime.feature_resolver(snapshot, runtime.build_contract, runtime.profile, root, "rebuild")
    if not runtime.cache_is_complete(snapshot, runtime.build_contract, runtime.profile, root):
        raise ValueError("warm cache prepopulation did not create every reusable component")
    _atomic_json(
        _warm_preparation_path(root),
        {
            "schema_version": 1,
            "kind": "flexible_rulebook_benchmark_warm_preparation",
            "source_fingerprint": snapshot.fingerprint,
            "feature_plan_hash": resolution.plan.feature_plan_hash,
        },
    )
    return snapshot


def run_benchmark_sample(
    request: BenchmarkSampleRequest,
    root: Path,
    *,
    runtime: BenchmarkSampleRuntime,
) -> BenchmarkSample:
    """Run exactly one isolated measurement, retaining every failure as evidence."""

    if not isinstance(request, BenchmarkSampleRequest) or not isinstance(runtime, BenchmarkSampleRuntime):
        raise ValueError("benchmark sample requires a request and runtime")
    root = _validate_isolated_root(root)
    stratum_id, canonical_index = _slot_provenance(request, runtime)
    cache_directory = root / "cache"
    if request.mode == "cold" and cache_directory.exists() and any(cache_directory.rglob("*")):
        return _failure_sample(
            request,
            root=root,
            stratum_id=stratum_id,
            canonical_index=canonical_index,
            source_fingerprint=None,
            preflight_seconds=None,
            maximal_slot_seconds=None,
            terminal_state="failed",
            safe_error_code="BENCHMARK.COLD_CACHE_PRESENT",
            runtime=runtime,
        )

    source_fingerprint: str | None = None
    preflight_started = float(runtime.monotonic())
    try:
        snapshot = runtime.history_loader(request.ticker, request.as_of)
    except Exception:
        return _failure_sample(
            request,
            root=root,
            stratum_id=stratum_id,
            canonical_index=canonical_index,
            source_fingerprint=None,
            preflight_seconds=_duration(preflight_started, runtime.monotonic),
            maximal_slot_seconds=None,
            terminal_state="blocked",
            safe_error_code="SOURCE.UNAVAILABLE",
            runtime=runtime,
        )
    if not isinstance(snapshot, HistorySnapshot) or snapshot.quality_state != "eligible" or snapshot.fingerprint is None:
        return _failure_sample(
            request,
            root=root,
            stratum_id=stratum_id,
            canonical_index=canonical_index,
            source_fingerprint=getattr(snapshot, "fingerprint", None),
            preflight_seconds=_duration(preflight_started, runtime.monotonic),
            maximal_slot_seconds=None,
            terminal_state="blocked",
            safe_error_code="DATA.INELIGIBLE",
            runtime=runtime,
        )
    source_fingerprint = snapshot.fingerprint
    if request.mode == "warm":
        prepared_fingerprint = _read_warm_preparation_fingerprint(root)
        if prepared_fingerprint is not None and prepared_fingerprint != source_fingerprint:
            return _failure_sample(
                request,
                root=root,
                stratum_id=stratum_id,
                canonical_index=canonical_index,
                source_fingerprint=source_fingerprint,
                preflight_seconds=_duration(preflight_started, runtime.monotonic),
                maximal_slot_seconds=None,
                terminal_state="blocked",
                safe_error_code="SOURCE.CHANGED",
                runtime=runtime,
            )
        if prepared_fingerprint is None or not runtime.cache_is_complete(
            snapshot, runtime.build_contract, runtime.profile, root
        ):
            return _failure_sample(
                request,
                root=root,
                stratum_id=stratum_id,
                canonical_index=canonical_index,
                source_fingerprint=source_fingerprint,
                preflight_seconds=_duration(preflight_started, runtime.monotonic),
                maximal_slot_seconds=None,
                terminal_state="failed",
                safe_error_code="FEATURE.WARM_CACHE_UNAVAILABLE",
                runtime=runtime,
            )
    try:
        features = runtime.feature_resolver(
            snapshot,
            runtime.build_contract,
            runtime.profile,
            root,
            "rebuild" if request.mode == "cold" else "reuse",
        )
        campaign = _campaign_request(request, runtime, snapshot, features)
        runtime.worker_preparer(campaign, features, root)
    except Exception:
        return _failure_sample(
            request,
            root=root,
            stratum_id=stratum_id,
            canonical_index=canonical_index,
            source_fingerprint=source_fingerprint,
            preflight_seconds=_duration(preflight_started, runtime.monotonic),
            maximal_slot_seconds=None,
            terminal_state="failed",
            safe_error_code="FEATURE.PREFLIGHT_FAILED",
            runtime=runtime,
        )
    preflight_seconds = _duration(preflight_started, runtime.monotonic)

    maximal_started = float(runtime.monotonic())
    try:
        execution = runtime.campaign_executor(campaign, root)
    except Exception:
        return _failure_sample(
            request,
            root=root,
            stratum_id=stratum_id,
            canonical_index=canonical_index,
            source_fingerprint=source_fingerprint,
            preflight_seconds=preflight_seconds,
            maximal_slot_seconds=_duration(maximal_started, runtime.monotonic),
            terminal_state="failed",
            safe_error_code="INFRA.WORKER_START",
            runtime=runtime,
        )
    maximal_slot_seconds = _duration(maximal_started, runtime.monotonic)
    manifest = execution.manifest
    if execution.worker_source_fingerprint is not None and execution.worker_source_fingerprint != source_fingerprint:
        return _failure_sample(
            request,
            root=root,
            stratum_id=stratum_id,
            canonical_index=canonical_index,
            source_fingerprint=source_fingerprint,
            preflight_seconds=preflight_seconds,
            maximal_slot_seconds=maximal_slot_seconds,
            terminal_state="blocked",
            safe_error_code="SOURCE.CHANGED",
            runtime=runtime,
        )
    terminal_state = manifest.state
    safe_error_code = manifest.safe_error_code
    phase_values = (
        execution.training_seconds,
        execution.test_seconds,
        execution.selection_seconds,
        execution.write_seconds,
    )
    if terminal_state == "completed" and (
        safe_error_code is not None or any(value is None for value in phase_values)
    ):
        terminal_state = "completed_with_errors"
        safe_error_code = safe_error_code or "BENCHMARK.PHASE_TELEMETRY_UNAVAILABLE"
    receipt_id = manifest.feature_receipt_ids[0] if len(manifest.feature_receipt_ids) == 1 else None
    return BenchmarkSample(
        ticker=request.ticker,
        seed=request.seed,
        global_slot=request.global_slot,
        canonical_index=canonical_index,
        frontier_stratum=stratum_id,
        mode=request.mode,
        source_fingerprint=source_fingerprint,
        feature_receipt_id=receipt_id,
        split_identity=canonical_json(campaign.split.to_identity_dict()),
        preflight_seconds=preflight_seconds,
        training_seconds=execution.training_seconds,
        test_seconds=execution.test_seconds,
        selection_seconds=execution.selection_seconds,
        write_seconds=execution.write_seconds,
        maximal_slot_seconds=maximal_slot_seconds,
        terminal_state=terminal_state,
        safe_error_code=safe_error_code,
        reached_maximal_path=execution.reached_maximal_path,
        peak_rss_bytes=runtime.rss_probe(),
        peak_pool_checkouts=runtime.pool_checkout_probe(),
        cache_bytes=_tree_bytes(root / "cache"),
        artifact_bytes=_tree_bytes(root) - _tree_bytes(root / "cache"),
    )


def main(argv: list[str] | None = None) -> int:
    """Run explicit production evidence or one internal isolated sample."""

    parser = argparse.ArgumentParser(description="Run a read-only Flexible Rulebook production benchmark.")
    parser.add_argument("--tickers", nargs="+", help="Explicit ticker symbols")
    parser.add_argument("--as-of", help="Fixed YYYY-MM-DD source boundary")
    parser.add_argument("--seed", action="append", help="Frozen frontier seed; repeatable")
    parser.add_argument("--cold-samples", type=int, help="Cold samples per ticker and seed")
    parser.add_argument("--warm-samples", type=int, default=0, help="Diagnostic warm samples per ticker and seed")
    parser.add_argument("--output", help="Absolute report path outside Flexible-Rulebook")
    parser.add_argument("--_sample-request", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments._sample_request is not None:
        return _run_internal_sample(Path(arguments._sample_request).resolve())
    missing = [
        name for name, value in (
            ("--tickers", arguments.tickers),
            ("--as-of", arguments.as_of),
            ("--seed", arguments.seed),
            ("--cold-samples", arguments.cold_samples),
            ("--output", arguments.output),
        ) if value is None
    ]
    if missing:
        parser.error(f"missing required arguments: {', '.join(missing)}")
    try:
        as_of = date.fromisoformat(arguments.as_of)
    except ValueError:
        parser.error("--as-of must be YYYY-MM-DD")
    try:
        report = run_production_benchmark(
            tickers=arguments.tickers,
            as_of=as_of,
            seeds=arguments.seed,
            cold_samples=arguments.cold_samples,
            warm_samples=arguments.warm_samples,
            output=Path(arguments.output),
        )
    except ValueError as error:
        parser.error(str(error))
    print(f"Benchmark report: {Path(arguments.output).resolve()}")
    if not report.is_discovery_eligible:
        print("Benchmark result: ineligible evidence recorded; discovery remains disabled.")
        return 2
    print("Benchmark result: eligible evidence recorded; policy remains unchanged pending review.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI process entry point
    raise SystemExit(main())


__all__ = [
    "BenchmarkExecution", "BenchmarkSampleRequest", "BenchmarkSampleRuntime",
    "benchmark_discovery_service", "benchmark_source_loader", "main",
    "prepare_warm_sample_cache", "production_sample_runtime", "run_benchmark_sample",
    "run_production_benchmark", "validate_benchmark_output_path",
]
