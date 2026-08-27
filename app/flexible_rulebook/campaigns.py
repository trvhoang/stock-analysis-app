"""Frozen Flexible Rulebook campaign identities and state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import re
from typing import Literal

from .contracts import (
    EvaluationSplit,
    ExecutionContract,
    FeatureResolutionReceipt,
    FeatureSnapshot,
    RuntimeBudget,
    SelectionPolicy,
    canonical_json,
)
from .history import HistorySnapshot
from .search import FrontierAssignment


CampaignState = Literal["queued", "running", "cancelling", "cancelled", "blocked", "interrupted", "completed", "completed_with_errors", "failed"]
HistoricalItemState = Literal["queued", "running", "retry_pending", "qualified", "no_qualified_candidate_within_budget", "time_budget_exhausted", "frontier_exhausted_no_qualified_candidate", "data_ineligible", "source_changed", "failed", "cancelled", "not_started_budget_limited"]
_OPERATIONS = frozenset({"discover", "qualify", "current_scan"})
_ITEM_STATES = frozenset({"queued", "running", "retry_pending", "qualified", "no_qualified_candidate_within_budget", "time_budget_exhausted", "frontier_exhausted_no_qualified_candidate", "data_ineligible", "source_changed", "failed", "cancelled", "not_started_budget_limited"})
_HASH = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL = frozenset({"cancelled", "completed", "completed_with_errors", "failed"})
_TRANSITIONS = {
    "queued": frozenset({"running", "cancelled", "blocked", "failed"}),
    "running": frozenset({"cancelling", "cancelled", "blocked", "interrupted", "completed", "completed_with_errors", "failed"}),
    "cancelling": frozenset({"cancelled", "failed"}),
    "cancelled": frozenset({"running"}),
    "blocked": frozenset({"running", "cancelled", "failed"}),
    "interrupted": frozenset({"running", "cancelled", "failed"}),
    "completed": frozenset(),
    "completed_with_errors": frozenset(),
    "failed": frozenset(),
}


def _hash(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _members(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError("frozen_members must be an ordered ticker tuple")
    try:
        members = tuple(value)
    except TypeError as error:
        raise ValueError("frozen_members must be an ordered ticker tuple") from error
    if not members or any(not isinstance(item, str) or not item or item != item.upper() for item in members) or len(set(members)) != len(members):
        raise ValueError("frozen_members must be unique uppercase tickers")
    return members


@dataclass(frozen=True)
class CampaignRequest:
    """All semantic inputs frozen before a campaign can receive an ID."""

    operation: Literal["discover", "qualify", "current_scan"]
    frozen_members: tuple[str, ...]
    source_snapshots: tuple[FeatureSnapshot, ...]
    catalog_hash: str
    engine_revision: str
    rulebook_ids: tuple[str, ...]
    feature_build_contract_hashes: tuple[str, ...]
    feature_plan_hashes: tuple[str, ...]
    execution_contract: ExecutionContract
    split: EvaluationSplit
    runtime_budget: RuntimeBudget
    selection_policy: SelectionPolicy
    per_ticker_budget: int
    frontier_assignment: FrontierAssignment | None = None
    qualification_revision: str = "both-partitions-12-65-15-v1"
    group_snapshot: tuple[str, ...] = ()
    parent_campaign_id: str | None = None
    execution_window_id: str = "initial"
    submitted_at: str | None = None
    cache_choice: str | None = None
    cache_path: str | None = None
    cache_age_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.operation not in _OPERATIONS:
            raise ValueError("operation is unsupported")
        members = _members(self.frozen_members)
        sources = tuple(self.source_snapshots)
        if len(sources) != len(members) or any(not isinstance(item, FeatureSnapshot) for item in sources) or tuple(item.ticker for item in sources) != members:
            raise ValueError("source snapshots must exactly match frozen members")
        object.__setattr__(self, "frozen_members", members)
        object.__setattr__(self, "source_snapshots", sources)
        object.__setattr__(self, "catalog_hash", _hash(self.catalog_hash, "catalog_hash"))
        if not isinstance(self.engine_revision, str) or not self.engine_revision or not isinstance(self.qualification_revision, str) or not self.qualification_revision:
            raise ValueError("campaign revisions must be non-blank")
        for name in ("rulebook_ids", "feature_build_contract_hashes", "feature_plan_hashes"):
            values = tuple(getattr(self, name))
            if len(set(values)) != len(values) or any(not isinstance(item, str) or not item for item in values):
                raise ValueError(f"{name} must be a unique immutable tuple")
            object.__setattr__(self, name, values)
        if not isinstance(self.execution_contract, ExecutionContract) or not isinstance(self.split, EvaluationSplit) or not isinstance(self.runtime_budget, RuntimeBudget) or not isinstance(self.selection_policy, SelectionPolicy):
            raise ValueError("campaign requires frozen core contracts")
        if isinstance(self.per_ticker_budget, bool) or not isinstance(self.per_ticker_budget, int) or self.per_ticker_budget <= 0:
            raise ValueError("per_ticker_budget must be positive")
        if self.operation == "discover":
            assignment = self.frontier_assignment
            if not isinstance(assignment, FrontierAssignment) or len(members) != 1 or assignment.source_ticker != members[0]:
                raise ValueError("discovery requires one matching frozen frontier assignment")
        elif self.frontier_assignment is not None:
            raise ValueError("frontier assignment is discovery-only")
        if self.parent_campaign_id is not None:
            if not isinstance(self.parent_campaign_id, str) or not re.fullmatch(r"fcmp_[0-9a-f]{64}", self.parent_campaign_id):
                raise ValueError("parent_campaign_id must be a campaign ID")
        if not isinstance(self.execution_window_id, str) or not self.execution_window_id:
            raise ValueError("execution_window_id must be non-blank")
        object.__setattr__(self, "group_snapshot", tuple(self.group_snapshot))

    def to_identity_dict(self) -> dict[str, object]:
        assignment = self.frontier_assignment
        return {
            "operation": self.operation, "frozen_members": self.frozen_members,
            "source_snapshots": [item.to_identity_dict() for item in self.source_snapshots],
            "catalog_hash": self.catalog_hash, "engine_revision": self.engine_revision,
            "rulebook_ids": self.rulebook_ids, "feature_build_contract_hashes": self.feature_build_contract_hashes,
            "feature_plan_hashes": self.feature_plan_hashes,
            "execution_contract": self.execution_contract.to_identity_dict(), "split": self.split.to_identity_dict(),
            "runtime_budget": self.runtime_budget.to_identity_dict(), "selection_policy": self.selection_policy.to_identity_dict(),
            "per_ticker_budget": self.per_ticker_budget, "qualification_revision": self.qualification_revision,
            "group_snapshot": self.group_snapshot, "parent_campaign_id": self.parent_campaign_id,
            "execution_window_id": self.execution_window_id,
            "frontier_assignment": None if assignment is None else {
                "candidate_space_hash": assignment.candidate_space_hash,
                "candidate_space_algorithm_version": assignment.candidate_space_algorithm_version,
                "frontier_seed": assignment.frontier_seed, "source_ticker": assignment.source_ticker,
                "start_slot": assignment.start_slot, "attempt_count": assignment.attempt_count,
                "strata": [item.__dict__ for item in assignment.strata],
                "stratum_multiplier": assignment.stratum_multiplier, "stratum_offset": assignment.stratum_offset,
                "algorithm_version": assignment.algorithm_version, "stratification_revision": assignment.stratification_revision,
                "assignment_hash": assignment.assignment_hash,
            },
        }


@dataclass(frozen=True)
class CampaignItem:
    ticker: str
    state: HistoricalItemState = "queued"
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ticker, str) or not self.ticker or self.ticker != self.ticker.upper() or self.state not in _ITEM_STATES:
            raise ValueError("historical item state or ticker is invalid")


@dataclass(frozen=True)
class CampaignManifest:
    """Mutable runtime checkpoint around immutable CampaignRequest semantics."""

    request: CampaignRequest
    campaign_id: str
    state: CampaignState = "queued"
    items: tuple[CampaignItem, ...] = ()
    lease_epoch: int = 0
    next_slot: int | None = None
    uncommitted_slot: int | None = None
    chain_attempted_count: int = 0
    unsearched_count: int = 0
    feature_receipt_ids: tuple[str, ...] = ()
    selection_snapshot_id: str | None = None
    safe_error_code: str | None = None
    safe_error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, CampaignRequest) or self.state not in _TRANSITIONS:
            raise ValueError("manifest requires a valid request and state")
        if not isinstance(self.campaign_id, str) or not re.fullmatch(r"fcmp_[0-9a-f]{64}", self.campaign_id):
            raise ValueError("manifest campaign_id is invalid")
        if tuple(item.ticker for item in self.items) != self.request.frozen_members or any(not isinstance(item, CampaignItem) for item in self.items):
            raise ValueError("manifest items must preserve frozen member order")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (self.lease_epoch, self.chain_attempted_count, self.unsearched_count)):
            raise ValueError("manifest counters must be non-negative integers")
        assignment = self.request.frontier_assignment
        if assignment is not None:
            frontier_size = sum(item.size for item in assignment.strata)
            if self.next_slot is None or not assignment.start_slot <= self.next_slot <= frontier_size or self.chain_attempted_count != self.next_slot or self.unsearched_count != frontier_size - self.next_slot:
                raise ValueError("manifest discovery cursor must stay contiguous")
            if self.uncommitted_slot is not None and self.uncommitted_slot != self.next_slot:
                raise ValueError("manifest uncommitted slot must be the next cursor")


@dataclass(frozen=True)
class SelectionSnapshot:
    """Typed terminal-selection evidence; storage serializes its dictionary."""

    searched_window_truth: Literal["partial_window", "complete_assigned_window", "frontier_exhausted"]
    input_ledger_digest: str
    input_evaluation_digest: str
    selection_scope: str
    selection_policy_revision: str
    pairing_algorithm_revision: str
    ranked_rulebook_ids: tuple[str, ...]
    selected_rulebook_ids: tuple[str, ...]
    blocker_relations: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "searched_window_truth": self.searched_window_truth,
            "input_ledger_digest": self.input_ledger_digest,
            "input_evaluation_digest": self.input_evaluation_digest,
            "selection_scope": self.selection_scope,
            "selection_policy_revision": self.selection_policy_revision,
            "pairing_algorithm_revision": self.pairing_algorithm_revision,
            "ranked_rulebook_ids": list(self.ranked_rulebook_ids),
            "selected_rulebook_ids": list(self.selected_rulebook_ids),
            "blocker_relations": list(self.blocker_relations),
        }


def request_hash(request: CampaignRequest) -> str:
    """Return canonical semantic campaign identity; omit operational diagnostics."""

    if not isinstance(request, CampaignRequest):
        raise ValueError("request must be CampaignRequest")
    return hashlib.sha256(canonical_json(request.to_identity_dict()).encode("utf-8")).hexdigest()


def create_manifest(request: CampaignRequest) -> CampaignManifest:
    """Create the only allowed initial queued checkpoint for a frozen request."""

    identifier = request_hash(request)
    assignment = request.frontier_assignment
    return CampaignManifest(
        request=request, campaign_id=f"fcmp_{identifier}",
        items=tuple(CampaignItem(ticker) for ticker in request.frozen_members),
        next_slot=None if assignment is None else assignment.start_slot,
        chain_attempted_count=0 if assignment is None else assignment.start_slot,
        unsearched_count=0 if assignment is None else sum(item.size for item in assignment.strata) - assignment.start_slot,
    )


def transition(manifest: CampaignManifest, target: CampaignState) -> CampaignManifest:
    """Apply one legal campaign lifecycle transition without changing its request."""

    if not isinstance(manifest, CampaignManifest) or target not in _TRANSITIONS.get(manifest.state, frozenset()):
        raise ValueError("campaign transition is invalid")
    return replace(manifest, state=target)


def continue_discovery(parent: CampaignManifest, *, verified_source: HistorySnapshot) -> CampaignRequest:
    """Create a linked, source-identical next discovery window from its cursor."""

    if not isinstance(parent, CampaignManifest) or parent.request.operation != "discover" or parent.state not in {"completed", "completed_with_errors"}:
        raise ValueError("only terminal discovery may continue")
    if parent.uncommitted_slot is not None or parent.next_slot is None or parent.chain_attempted_count != parent.next_slot:
        raise ValueError("cannot continue unresolved discovery work")
    if not isinstance(verified_source, HistorySnapshot):
        raise ValueError("verified_source must be HistorySnapshot")
    source = parent.request.source_snapshots[0]
    if (verified_source.ticker, verified_source.fingerprint, verified_source.requested_start, verified_source.requested_as_of, verified_source.first_date, verified_source.as_of_date) != (source.ticker, source.raw_history_fingerprint, source.requested_start, source.requested_as_of, source.first_date, source.as_of_date):
        raise ValueError("cannot continue changed frozen source")
    assignment = parent.request.frontier_assignment
    assert assignment is not None
    frontier_size = sum(item.size for item in assignment.strata)
    if parent.next_slot >= frontier_size:
        raise ValueError("discovery frontier is already exhausted")
    count = min(parent.request.per_ticker_budget, frontier_size - parent.next_slot)
    next_assignment = replace(assignment, start_slot=parent.next_slot, attempt_count=count)
    return replace(
        parent.request, frontier_assignment=next_assignment,
        parent_campaign_id=parent.campaign_id,
        execution_window_id=f"continue-{request_hash(parent.request)}-{parent.next_slot}",
        cache_choice=None, cache_path=None, cache_age_seconds=None,
    )


__all__ = ["CampaignItem", "CampaignManifest", "CampaignRequest", "CampaignState", "FeatureResolutionReceipt", "HistoricalItemState", "SelectionSnapshot", "continue_discovery", "create_manifest", "request_hash", "transition"]
