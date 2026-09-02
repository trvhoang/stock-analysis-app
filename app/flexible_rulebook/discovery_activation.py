"""Policy-bound activation boundary for interactive Flexible Discover work."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
import json
from pathlib import Path
from typing import Literal

import pytz

from .activation import (
    ActivatedDiscoveryPolicy,
    active_policy_directory,
    load_active_policy,
    load_policy_by_digest,
)
from .campaigns import CampaignManifest, CampaignRequest, transition, write_campaign_manifest
from .cap_benchmark_runner import (
    discovery_runtime_contract_identity,
    production_cap_runtime,
)
from .contracts import (
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureSnapshot,
    RuntimeBudget,
    SelectionPolicy,
    canonical_json,
)
from .features import (
    CacheOffer,
    FeatureResolution,
    feature_snapshot_for_history,
    inspect_primitive_cache,
)
from .history import HistorySnapshot, load_flexible_history, make_evaluation_split
from .runner import (
    claim_campaign,
    continue_campaign,
    read_campaign,
    release_campaign_lease,
    resume_campaign,
    start_campaign_worker,
    submit_campaign,
)
from .search import FrontierAssignment, SearchBudget, assign_frontier
from .service import DiscoveryService, resolve_frozen_feature_bundle
from .storage import resolve_flexible_root
from .worker_contract import WorkerRequest


_HCM = pytz.timezone("Asia/Ho_Chi_Minh")
_ACTIVATED_SERVICE_REF = "flexible_rulebook.discovery_activation:activated_discovery_service"
_ACTIVATED_SOURCE_REF = "flexible_rulebook.discovery_activation:activated_discovery_source_loader"


def _hcm_now(value: datetime | None) -> datetime:
    timestamp = datetime.now(_HCM) if value is None else value
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("activated discovery time must be timezone-aware")
    return timestamp.astimezone(_HCM)


def _live_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("activated discovery requires an absolute live evidence root")
    resolved = root.resolve()
    if resolved != resolve_flexible_root().resolve():
        raise ValueError("activated discovery requires the live Flexible Rulebook evidence root")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _normalized_ticker(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("ticker must be text")
    ticker = value.strip().upper()
    if not ticker:
        raise ValueError("ticker must be non-empty")
    return ticker


def _anchor_snapshot(policy: ActivatedDiscoveryPolicy, ticker: str) -> FeatureSnapshot:
    matches = [identity for member, identity in policy.source_anchors if member == ticker]
    if len(matches) != 1:
        raise ValueError("ticker is outside the activated policy source scope")
    try:
        payload = json.loads(matches[0])
    except json.JSONDecodeError as error:  # defensive; policy construction is canonical
        raise ValueError("activated policy source anchor is invalid") from error
    required = {
        "ticker",
        "raw_history_fingerprint",
        "requested_start",
        "requested_as_of",
        "first_date",
        "as_of_date",
        "quality_state",
        "quality_revision",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("activated policy source anchor is incomplete")
    try:
        return FeatureSnapshot(
            ticker=payload["ticker"],
            raw_history_fingerprint=payload["raw_history_fingerprint"],
            requested_start=date.fromisoformat(payload["requested_start"]),
            requested_as_of=date.fromisoformat(payload["requested_as_of"]),
            first_date=date.fromisoformat(payload["first_date"]),
            as_of_date=date.fromisoformat(payload["as_of_date"]),
            quality_state=payload["quality_state"],
            quality_revision=payload["quality_revision"],
        )
    except (TypeError, ValueError) as error:
        raise ValueError("activated policy source anchor is invalid") from error


def _anchor_split(policy: ActivatedDiscoveryPolicy, ticker: str) -> str:
    matches = [identity for member, identity in policy.benchmark_splits if member == ticker]
    if len(matches) != 1:
        raise ValueError("ticker is outside the activated policy split scope")
    return matches[0]


def _runtime():
    """Return the exact catalog and contracts authorized by direct-cap evidence."""

    return production_cap_runtime()


def _validated_active_policy(policy: ActivatedDiscoveryPolicy) -> ActivatedDiscoveryPolicy:
    """Accept New Start authority only from the currently active immutable pointer."""

    if not isinstance(policy, ActivatedDiscoveryPolicy):
        raise ValueError("activated discovery requires an activation policy")
    active, reason = load_active_policy()
    if active is None:
        raise ValueError(f"activated discovery policy is unavailable: {reason}")
    if active.policy_digest != policy.policy_digest or active != policy:
        raise ValueError("activated discovery policy is no longer active")
    return active


def _validate_policy_scope(
    policy: ActivatedDiscoveryPolicy,
    ticker: str,
    seed: str,
) -> object:
    if not isinstance(policy, ActivatedDiscoveryPolicy):
        raise ValueError("activated discovery requires an activation policy")
    if ticker not in policy.allowed_tickers or seed not in policy.allowed_seeds:
        raise ValueError("ticker or seed is outside the activated policy scope")
    runtime = _runtime()
    if policy.runtime_contract_identity != discovery_runtime_contract_identity(runtime):
        raise ValueError("activated policy runtime contract does not match the current implementation")
    if policy.worker_count != 1:
        raise ValueError("activated discovery requires exactly one worker")
    return runtime


def _verify_historical_anchor(
    engine: object,
    policy: ActivatedDiscoveryPolicy,
    ticker: str,
) -> FeatureSnapshot:
    expected = _anchor_snapshot(policy, ticker)
    historical = load_flexible_history(engine, ticker, as_of=expected.requested_as_of)
    try:
        actual = feature_snapshot_for_history(historical)
    except ValueError as error:
        raise ValueError("benchmark source anchor is unavailable") from error
    if actual != expected:
        raise ValueError("benchmark source anchor changed")
    if canonical_json(make_evaluation_split(historical).to_identity_dict()) != _anchor_split(policy, ticker):
        raise ValueError("benchmark source split changed")
    return expected


@dataclass(frozen=True)
class ActivatedDiscoveryPreflight:
    """Fresh current source and immutable policy authority awaiting a cache choice."""

    policy: ActivatedDiscoveryPolicy
    root: Path
    ticker: str
    seed: str
    snapshot: HistorySnapshot
    build_contract: FeatureBuildContract
    feature_plan: FeaturePlan
    cache_offer: CacheOffer
    split: EvaluationSplit
    execution_contract: ExecutionContract
    runtime_budget: RuntimeBudget
    selection_policy: SelectionPolicy
    catalog_hash: str
    engine_revision: str
    frontier_assignment: FrontierAssignment

    def __post_init__(self) -> None:
        if not isinstance(self.policy, ActivatedDiscoveryPolicy):
            raise ValueError("preflight requires an activation policy")
        if not isinstance(self.root, Path) or not self.root.is_absolute():
            raise ValueError("preflight root is invalid")
        if self.snapshot.quality_state != "eligible":
            raise ValueError("preflight requires eligible current history")
        if self.feature_plan.snapshot != feature_snapshot_for_history(self.snapshot):
            raise ValueError("preflight feature plan does not freeze the current source")
        if self.feature_plan.build_contract != self.build_contract:
            raise ValueError("preflight feature build contract is invalid")
        if not isinstance(self.cache_offer, CacheOffer):
            raise ValueError("preflight cache offer is invalid")
        if self.frontier_assignment.source_ticker != self.ticker:
            raise ValueError("preflight frontier ticker is invalid")

    @property
    def policy_digest(self) -> str:
        return self.policy.policy_digest


def preflight_activated_discovery(
    engine: object,
    ticker: str,
    seed: str,
    policy: ActivatedDiscoveryPolicy,
    *,
    root: Path,
    now: datetime,
) -> ActivatedDiscoveryPreflight:
    """Prove the benchmark anchor, then freeze one fresh current data source."""

    live_root = _live_root(root)
    normalized_ticker = _normalized_ticker(ticker)
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("seed must be non-empty")
    normalized_seed = seed.strip()
    timestamp = _hcm_now(now)
    policy = _validated_active_policy(policy)
    runtime = _validate_policy_scope(policy, normalized_ticker, normalized_seed)
    _verify_historical_anchor(engine, policy, normalized_ticker)

    current = load_flexible_history(engine, normalized_ticker, as_of=timestamp.date())
    if current.quality_state != "eligible":
        raise ValueError("current source is not eligible")
    source = feature_snapshot_for_history(current)
    plan = FeaturePlan(source, runtime.build_contract, runtime.profile)
    offer = inspect_primitive_cache(current, runtime.build_contract, runtime.profile, live_root, timestamp)
    assignment = assign_frontier(
        runtime.space,
        frontier_seed=normalized_seed,
        source_ticker=normalized_ticker,
        start_slot=0,
        budget=SearchBudget(attempt_count=policy.cap_attempts, runtime=runtime.runtime_budget),
    )
    return ActivatedDiscoveryPreflight(
        policy=policy,
        root=live_root,
        ticker=normalized_ticker,
        seed=normalized_seed,
        snapshot=current,
        build_contract=runtime.build_contract,
        feature_plan=plan,
        cache_offer=offer,
        split=make_evaluation_split(current),
        execution_contract=runtime.execution_contract,
        runtime_budget=runtime.runtime_budget,
        selection_policy=runtime.selection_policy,
        catalog_hash=runtime.catalog.catalog_hash,
        engine_revision=runtime.engine_revision,
        frontier_assignment=assignment,
    )


def _validate_cache_choice(preflight: ActivatedDiscoveryPreflight, choice: str) -> Literal["reuse", "rebuild"]:
    if choice not in {"reuse", "rebuild"}:
        raise ValueError("cache_choice must be reuse or rebuild")
    if choice == "reuse" and (preflight.cache_offer.stale_keys or preflight.cache_offer.missing_keys):
        raise ValueError("cache reuse is unavailable; rebuild is required")
    return choice


def _validate_preflight_contract(preflight: ActivatedDiscoveryPreflight) -> None:
    """Reject a forged or stale in-memory preflight before it can persist work."""

    runtime = _validate_policy_scope(preflight.policy, preflight.ticker, preflight.seed)
    source = feature_snapshot_for_history(preflight.snapshot)
    expected_plan = FeaturePlan(source, runtime.build_contract, runtime.profile)
    expected_assignment = assign_frontier(
        runtime.space,
        frontier_seed=preflight.seed,
        source_ticker=preflight.ticker,
        start_slot=0,
        budget=SearchBudget(
            attempt_count=preflight.policy.cap_attempts,
            runtime=runtime.runtime_budget,
        ),
    )
    if (
        preflight.snapshot.quality_state != "eligible"
        or preflight.build_contract != runtime.build_contract
        or preflight.feature_plan != expected_plan
        or preflight.split != make_evaluation_split(preflight.snapshot)
        or preflight.execution_contract != runtime.execution_contract
        or preflight.runtime_budget != runtime.runtime_budget
        or preflight.selection_policy != runtime.selection_policy
        or preflight.catalog_hash != runtime.catalog.catalog_hash
        or preflight.engine_revision != runtime.engine_revision
        or preflight.frontier_assignment != expected_assignment
    ):
        raise ValueError("activated discovery preflight contract is stale or invalid")


def _request_from_preflight(
    preflight: ActivatedDiscoveryPreflight,
    cache_choice: Literal["reuse", "rebuild"],
) -> CampaignRequest:
    return CampaignRequest(
        operation="discover",
        frozen_members=(preflight.ticker,),
        source_snapshots=(preflight.feature_plan.snapshot,),
        catalog_hash=preflight.catalog_hash,
        engine_revision=preflight.engine_revision,
        rulebook_ids=(),
        feature_build_contract_hashes=(preflight.build_contract.feature_build_contract_hash,),
        feature_plan_hashes=(preflight.feature_plan.feature_plan_hash,),
        execution_contract=preflight.execution_contract,
        split=preflight.split,
        runtime_budget=preflight.runtime_budget,
        selection_policy=preflight.selection_policy,
        per_ticker_budget=preflight.policy.cap_attempts,
        frontier_assignment=preflight.frontier_assignment,
        activation_policy_digest=preflight.policy_digest,
        submitted_at=datetime.now(_HCM).isoformat(),
        cache_choice=cache_choice,
        cache_path=str(preflight.root / "cache"),
        cache_age_seconds=None,
    )


def _mark_worker_start_failure(campaign_id: str, root: Path) -> None:
    """Release a newly claimed lease if the subprocess cannot be created."""

    try:
        manifest = read_campaign(campaign_id, root)
        if manifest.state == "running":
            interrupted = replace(
                transition(manifest, "interrupted"),
                safe_error_code="INFRA.WORKER_START",
                safe_error_message="Worker could not be started safely.",
            )
            write_campaign_manifest(root, interrupted)
            release_campaign_lease(campaign_id, root)
    except (OSError, ValueError):
        # The original startup exception remains the only user-facing error.
        # Never forge a terminal state when the pre-existing manifest is unreadable.
        return


def _start_activated_worker(campaign_id: str, root: Path, *, claim: bool) -> None:
    if claim:
        claim_campaign(campaign_id, root)
    try:
        start_campaign_worker(
            campaign_id,
            root,
            service_ref=_ACTIVATED_SERVICE_REF,
            source_loader_ref=_ACTIVATED_SOURCE_REF,
        )
    except Exception:
        _mark_worker_start_failure(campaign_id, root)
        raise


def submit_activated_discovery(
    preflight: ActivatedDiscoveryPreflight,
    *,
    cache_choice: Literal["reuse", "rebuild"],
    root: Path,
) -> str:
    """Persist, claim, and start exactly one policy-bound Discover worker."""

    if not isinstance(preflight, ActivatedDiscoveryPreflight):
        raise ValueError("activated discovery requires a policy preflight")
    live_root = _live_root(root)
    if live_root != preflight.root:
        raise ValueError("preflight root does not match the live evidence root")
    _validated_active_policy(preflight.policy)
    _validate_preflight_contract(preflight)
    current_offer = inspect_primitive_cache(
        preflight.snapshot,
        preflight.build_contract,
        preflight.feature_plan.profile,
        live_root,
        datetime.now(_HCM),
    )
    if current_offer != preflight.cache_offer:
        raise ValueError("cache preflight changed; run Preflight Discover again")
    choice = _validate_cache_choice(preflight, cache_choice)
    campaign_id = submit_campaign(_request_from_preflight(preflight, choice), live_root)
    manifest = read_campaign(campaign_id, live_root)
    if manifest.state == "queued":
        _start_activated_worker(campaign_id, live_root, claim=True)
    elif manifest.state != "running":
        raise ValueError("matching activated campaign is not startable")
    return campaign_id


def _policy_bound_manifest(campaign_id: str, root: Path) -> tuple[CampaignManifest, ActivatedDiscoveryPolicy, object]:
    manifest = read_campaign(campaign_id, root)
    digest = manifest.request.activation_policy_digest
    if digest is None:
        raise ValueError("activated discovery rejects a legacy campaign without an activation policy")
    policy = load_policy_by_digest(active_policy_directory(), digest)
    ticker = manifest.request.frozen_members[0] if len(manifest.request.frozen_members) == 1 else ""
    assignment = manifest.request.frontier_assignment
    seed = assignment.frontier_seed if assignment is not None else ""
    runtime = _validate_policy_scope(policy, ticker, seed)
    _validate_policy_bound_request(manifest.request, policy, runtime)
    return manifest, policy, runtime


def _validate_policy_bound_request(
    request: CampaignRequest,
    policy: ActivatedDiscoveryPolicy,
    runtime: object,
) -> None:
    assignment = request.frontier_assignment
    if (
        request.operation != "discover"
        or request.activation_policy_digest != policy.policy_digest
        or len(request.frozen_members) != 1
        or assignment is None
        or request.frozen_members[0] not in policy.allowed_tickers
        or assignment.frontier_seed not in policy.allowed_seeds
        or request.per_ticker_budget != policy.cap_attempts
        or assignment.attempt_count != policy.cap_attempts
        or request.catalog_hash != runtime.catalog.catalog_hash
        or request.engine_revision != runtime.engine_revision
        or request.execution_contract != runtime.execution_contract
        or request.runtime_budget != runtime.runtime_budget
        or request.selection_policy != runtime.selection_policy
        or request.feature_build_contract_hashes != (runtime.build_contract.feature_build_contract_hash,)
    ):
        raise ValueError("campaign does not match its activated policy contract")
    expected_plan = FeaturePlan(request.source_snapshots[0], runtime.build_contract, runtime.profile)
    if request.feature_plan_hashes != (expected_plan.feature_plan_hash,):
        raise ValueError("campaign feature plan does not match its activated policy contract")
    expected_assignment = assign_frontier(
        runtime.space,
        frontier_seed=assignment.frontier_seed,
        source_ticker=request.frozen_members[0],
        start_slot=assignment.start_slot,
        budget=SearchBudget(attempt_count=policy.cap_attempts, runtime=runtime.runtime_budget),
    )
    if assignment != expected_assignment:
        raise ValueError("campaign frontier does not match its activated policy contract")
    if request.cache_choice not in {"reuse", "rebuild"}:
        raise ValueError("campaign cache choice is unavailable")


def _resolve_activated_features(
    manifest: CampaignManifest,
    runtime: object,
    source: HistorySnapshot,
    root: Path,
) -> FeatureResolution:
    resolution = resolve_frozen_feature_bundle(
        source,
        runtime.build_contract,
        runtime.profile,
        root,
        cache_choice=manifest.request.cache_choice,
        now=datetime.now(_HCM),
    )
    expected = FeaturePlan(manifest.request.source_snapshots[0], runtime.build_contract, runtime.profile)
    if resolution.plan != expected:
        raise ValueError("worker feature resolution does not match the frozen campaign")
    return resolution


def activated_discovery_service(request: WorkerRequest) -> DiscoveryService:
    """Worker-only factory that reloads named immutable policy authority."""

    if not isinstance(request, WorkerRequest):
        raise ValueError("activated service requires a WorkerRequest")
    root = _live_root(request.root)
    manifest, _policy, runtime = _policy_bound_manifest(request.campaign_id, root)

    def resolve_verified_source(source: HistorySnapshot) -> FeatureResolution:
        return _resolve_activated_features(manifest, runtime, source, root)

    return DiscoveryService(
        root,
        candidate_space=runtime.space,
        feature_resolver=resolve_verified_source,
    )


def activated_discovery_source_loader(expected: FeatureSnapshot) -> HistorySnapshot:
    """Fresh-load one frozen source through a short-lived established DB engine."""

    from .benchmark_runner import benchmark_source_loader

    return benchmark_source_loader(expected)


def _verify_policy_anchor_from_worker(policy: ActivatedDiscoveryPolicy, ticker: str) -> None:
    expected = _anchor_snapshot(policy, ticker)
    history = activated_discovery_source_loader(expected)
    if feature_snapshot_for_history(history) != expected:
        raise ValueError("benchmark source anchor changed")
    if canonical_json(make_evaluation_split(history).to_identity_dict()) != _anchor_split(policy, ticker):
        raise ValueError("benchmark source split changed")


def resume_activated_discovery(campaign_id: str, *, root: Path, now: datetime | None = None) -> str:
    """Resume only a policy-bound campaign after historical and frozen-source proof."""

    live_root = _live_root(root)
    manifest, policy, runtime = _policy_bound_manifest(campaign_id, live_root)
    _verify_policy_anchor_from_worker(policy, manifest.request.frozen_members[0])
    resumed = resume_campaign(
        campaign_id,
        live_root,
        now=now,
        source_loader=activated_discovery_source_loader,
        receipt_resolver=lambda source: _resolve_activated_features(manifest, runtime, source, live_root).receipt,
    )
    _start_activated_worker(resumed, live_root, claim=False)
    return resumed


def continue_activated_discovery(campaign_id: str, *, root: Path) -> str:
    """Continue only the immutable policy chain and its exact frozen source."""

    live_root = _live_root(root)
    manifest, policy, runtime = _policy_bound_manifest(campaign_id, live_root)
    _verify_policy_anchor_from_worker(policy, manifest.request.frozen_members[0])
    assignment = manifest.request.frontier_assignment
    if assignment is None or manifest.next_slot is None:
        raise ValueError("activated continuation requires a contiguous discovery cursor")
    frontier_size = sum(stratum.size for stratum in assignment.strata)
    if frontier_size - manifest.next_slot < policy.cap_attempts:
        raise ValueError("activated continuation requires one full measured cap window")
    child = continue_campaign(
        campaign_id,
        live_root,
        source_loader=activated_discovery_source_loader,
        build_contract=runtime.build_contract,
    )
    _start_activated_worker(child, live_root, claim=True)
    return child


__all__ = [
    "ActivatedDiscoveryPreflight",
    "activated_discovery_service",
    "activated_discovery_source_loader",
    "continue_activated_discovery",
    "preflight_activated_discovery",
    "resume_activated_discovery",
    "submit_activated_discovery",
]
