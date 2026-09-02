"""Isolated Flexible Rulebook core public API."""

from importlib import import_module

from .contracts import (
    ANIMAL_POOL_V1,
    EvaluationPartition,
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    FeatureResolutionReceipt,
    FeatureSnapshot,
    PartitionMetrics,
    PredicateSpec,
    PrimitiveKey,
    PrimitiveSpec,
    RulebookDefinition,
    RulebookEvaluation,
    RuntimeBudget,
    SelectionPolicy,
    animal_alias,
    canonical_json,
    rulebook_id,
)
from .history import (
    EvidenceSourceAnchor,
    HistorySnapshot,
    load_flexible_history,
    make_evaluation_split,
    make_evidence_source_anchor,
    trade_dates_belong_to_partition,
    verify_evidence_source_anchor,
)
from .features import (
    CacheOffer,
    FeaturePreflight,
    FeatureResolution,
    FeatureStore,
    build_feature_store,
    compose_entry_mask,
    compose_technical_exit_mask,
    current_feature_build_contract,
    feature_snapshot_for_history,
    inspect_primitive_cache,
    primitive_mask,
    resolve_feature_store,
)
from .primitive_cache import (
    BuildLease,
    CachedComponent,
    CacheWriteResult,
    acquire_build_lease,
    component_digest,
    read_component,
    safe_read_component,
    try_write_component,
    write_component,
)
from .execution import (
    CompletedTrade,
    EventExitPlan,
    ExecutionInterrupted,
    build_event_exit_plan,
    event_plan_is_compatible,
    execute_rulebook,
    execute_rulebook_reference,
)
from .search import (
    CandidateSpace,
    DiscoveryResult,
    FrontierAssignment,
    SearchBudget,
    StratumAssignment,
    assign_frontier,
    candidate_space,
    discover_and_evaluate,
    scheduled_candidates,
)
from .storage import (
    append_ledger_chunk,
    iter_signal_set_paths,
    read_signal_set,
    resolve_flexible_root,
    write_feature_resolution_receipt,
    write_rulebook_definition,
    write_selection_snapshot,
    write_signal_set,
)
from .campaigns import (
    CampaignItem,
    CampaignManifest,
    CampaignRequest,
    CampaignState,
    HistoricalItemState,
    SelectionSnapshot,
    continue_discovery,
    create_manifest,
    request_hash,
    transition,
)
from .service import (
    DiscoveryService,
    ReceiptCheckpointService,
    checkpoint_campaign_item,
    discovery_ledger_rows,
    preflight_feature_components,
    preflight_group_feature_components,
    persist_discovery_ledger,
    qualify_rulebook_for_ticker,
    qualify_rulebooks_for_group,
    reusable_rulebooks,
    resolve_frozen_feature_bundle,
)
from .runner import (
    WorkerFault,
    WorkerWatchdogError,
    classify_worker_fault,
    start_campaign_worker,
    watch_campaign_worker,
)
from .group_adapter import FrozenGroup, resolve_named_group_dir, snapshot_named_group
from .current_scan import CommonAsOfPreflight, CurrentScanState, QualifiedCurrentPair, preflight_common_as_of, preflight_current_scan_features, scan_current_setup
from .benchmark import BenchmarkRecord, ScalePolicy, safe_default_scale_policy, validate_scale_policy
from .scope_expansion import (
    ProgressEvent,
    ScopeExpansionRequest,
    ScopeExpansionStatus,
    build_scope_expansion_request,
    parse_scope_values,
    read_scope_request,
    read_scope_status,
    write_scope_request,
    write_scope_status,
)
def submit_scope_expansion(*args, **kwargs):
    """Lazily load the scope coordinator to keep module CLI imports clean."""

    from .scope_expansion_runner import submit_scope_expansion as _submit

    return _submit(*args, **kwargs)


def run_scope_expansion_job(*args, **kwargs):
    """Lazily load the scope coordinator to keep module CLI imports clean."""

    from .scope_expansion_runner import run_scope_expansion_job as _run

    return _run(*args, **kwargs)


_ACTIVATION_EXPORTS = frozenset(
    {
        "ActivatedDiscoveryPolicy",
        "active_policy_directory",
        "activate_cap_report",
        "load_active_policy",
        "load_policy_by_digest",
    }
)
_WORKER_EXPORTS = frozenset({"WorkerRequest", "read_worker_request", "resolve_callable", "run_worker_request"})


def __getattr__(name: str):
    """Load activation helpers lazily so ``python -m`` starts a clean module."""

    if name in _ACTIVATION_EXPORTS:
        activation = import_module(".activation", __name__)
        return getattr(activation, name)
    if name in _WORKER_EXPORTS:
        worker = import_module(".worker", __name__)
        return getattr(worker, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ANIMAL_POOL_V1",
    "BuildLease",
    "CachedComponent",
    "CacheOffer",
    "CacheWriteResult",
    "CandidateSpace",
    "CampaignItem",
    "CampaignManifest",
    "CampaignRequest",
    "CampaignState",
    "EvaluationPartition",
    "EvaluationSplit",
    "EvidenceSourceAnchor",
    "CompletedTrade",
    "EventExitPlan",
    "DiscoveryResult",
    "DiscoveryService",
    "WorkerRequest",
    "WorkerFault",
    "WorkerWatchdogError",
    "ExecutionInterrupted",
    "ExecutionContract",
    "FeatureBuildContract",
    "FeaturePlan",
    "FeatureProfile",
    "FeatureResolution",
    "FeaturePreflight",
    "FeatureResolutionReceipt",
    "FrozenGroup",
    "FeatureSnapshot",
    "FeatureStore",
    "FrontierAssignment",
    "HistorySnapshot",
    "HistoricalItemState",
    "PartitionMetrics",
    "PredicateSpec",
    "PrimitiveKey",
    "PrimitiveSpec",
    "RulebookDefinition",
    "RulebookEvaluation",
    "ReceiptCheckpointService",
    "RuntimeBudget",
    "SearchBudget",
    "SelectionPolicy",
    "SelectionSnapshot",
    "StratumAssignment",
    "animal_alias",
    "assign_frontier",
    "append_ledger_chunk",
    "iter_signal_set_paths",
    "acquire_build_lease",
    "build_event_exit_plan",
    "event_plan_is_compatible",
    "build_feature_store",
    "canonical_json",
    "component_digest",
    "continue_discovery",
    "candidate_space",
    "checkpoint_campaign_item",
    "compose_entry_mask",
    "compose_technical_exit_mask",
    "current_feature_build_contract",
    "feature_snapshot_for_history",
    "create_manifest",
    "execute_rulebook",
    "execute_rulebook_reference",
    "discovery_ledger_rows",
    "discover_and_evaluate",
    "load_flexible_history",
    "make_evaluation_split",
    "make_evidence_source_anchor",
    "inspect_primitive_cache",
    "primitive_mask",
    "persist_discovery_ledger",
    "preflight_feature_components",
    "preflight_group_feature_components",
    "qualify_rulebook_for_ticker",
    "qualify_rulebooks_for_group",
    "reusable_rulebooks",
    "read_component",
    "read_signal_set",
    "resolve_flexible_root",
    "resolve_named_group_dir",
    "resolve_feature_store",
    "resolve_frozen_feature_bundle",
    "request_hash",
    "rulebook_id",
    "safe_read_component",
    "scheduled_candidates",
    "trade_dates_belong_to_partition",
    "transition",
    "verify_evidence_source_anchor",
    "try_write_component",
    "write_component",
    "write_feature_resolution_receipt",
    "write_rulebook_definition",
    "write_selection_snapshot",
    "write_signal_set",
    "classify_worker_fault",
    "start_campaign_worker",
    "watch_campaign_worker",
    "read_worker_request",
    "resolve_callable",
    "run_worker_request",
    "snapshot_named_group",
    "CommonAsOfPreflight",
    "CurrentScanState",
    "QualifiedCurrentPair",
    "preflight_common_as_of",
    "preflight_current_scan_features",
    "scan_current_setup",
    "BenchmarkRecord",
    "ScalePolicy",
    "safe_default_scale_policy",
    "validate_scale_policy",
    "ScopeExpansionRequest",
    "ScopeExpansionStatus",
    "ProgressEvent",
    "build_scope_expansion_request",
    "parse_scope_values",
    "read_scope_request",
    "read_scope_status",
    "write_scope_request",
    "write_scope_status",
    "run_scope_expansion_job",
    "submit_scope_expansion",
    "ActivatedDiscoveryPolicy",
    "active_policy_directory",
    "activate_cap_report",
    "load_active_policy",
    "load_policy_by_digest",
]
