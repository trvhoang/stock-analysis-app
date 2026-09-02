"""Frozen Flexible Rulebook campaign identities and state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Literal

from .contracts import (
    EvaluationSplit,
    EvaluationPartition,
    ExecutionContract,
    FeatureResolutionReceipt,
    FeatureSnapshot,
    RuntimeBudget,
    SelectionPolicy,
    canonical_json,
)
from .history import HistorySnapshot
from .metrics import rank_qualified, select_timing_distinct_top_three
from .search import FrontierAssignment, StratumAssignment
from .storage import write_selection_snapshot


CampaignState = Literal["queued", "running", "cancelling", "cancelled", "blocked", "interrupted", "completed", "completed_with_errors", "failed"]
HistoricalItemState = Literal["queued", "running", "retry_pending", "qualified", "no_qualified_candidate_within_budget", "time_budget_exhausted", "frontier_exhausted_no_qualified_candidate", "data_ineligible", "source_changed", "failed", "cancelled", "not_started_budget_limited", "current_setup_found", "no_current_setup", "no_historically_qualified_rulebook", "blocked_common_as_of", "data_stale", "data_invalid", "current_evaluation_failed", "not_evaluated"]
_OPERATIONS = frozenset({"discover", "qualify", "current_scan"})
_ITEM_STATES = frozenset({"queued", "running", "retry_pending", "qualified", "no_qualified_candidate_within_budget", "time_budget_exhausted", "frontier_exhausted_no_qualified_candidate", "data_ineligible", "source_changed", "failed", "cancelled", "not_started_budget_limited", "current_setup_found", "no_current_setup", "no_historically_qualified_rulebook", "blocked_common_as_of", "data_stale", "data_invalid", "current_evaluation_failed", "not_evaluated"})
_HASH = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_ID = re.compile(r"^frpr_[0-9a-f]{64}$")
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
_MANIFEST_SCHEMA_VERSION = 1


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


def _receipt_ids(value: object, *, require_nonempty: bool) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError("feature receipt IDs must be an ordered tuple")
    try:
        receipt_ids = tuple(value)
    except TypeError as error:
        raise ValueError("feature receipt IDs must be an ordered tuple") from error
    if (
        (require_nonempty and not receipt_ids)
        or len(set(receipt_ids)) != len(receipt_ids)
        or any(not isinstance(item, str) or not _RECEIPT_ID.fullmatch(item) for item in receipt_ids)
    ):
        raise ValueError("feature receipt IDs are invalid")
    return receipt_ids


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
    activation_policy_digest: str | None = None
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
        if self.activation_policy_digest is not None:
            object.__setattr__(
                self,
                "activation_policy_digest",
                _hash(self.activation_policy_digest, "activation_policy_digest"),
            )
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
        identity: dict[str, object] = {
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
        # Existing manifests were hashed before activation policy authority
        # existed.  Keep an absent optional field absent so those immutable
        # campaign IDs remain readable; a non-empty digest is identity-bound.
        if self.activation_policy_digest is not None:
            identity["activation_policy_digest"] = self.activation_policy_digest
        return identity


@dataclass(frozen=True)
class CampaignItem:
    ticker: str
    state: HistoricalItemState = "queued"
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ticker, str) or not self.ticker or self.ticker != self.ticker.upper() or self.state not in _ITEM_STATES:
            raise ValueError("historical item state or ticker is invalid")
        if self.artifact_id is not None and (
            not isinstance(self.artifact_id, str) or not self.artifact_id
        ):
            raise ValueError("historical item artifact_id is invalid")


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
        if self.campaign_id != f"fcmp_{request_hash(self.request)}":
            raise ValueError("manifest campaign_id does not match its frozen request")
        if tuple(item.ticker for item in self.items) != self.request.frozen_members or any(not isinstance(item, CampaignItem) for item in self.items):
            raise ValueError("manifest items must preserve frozen member order")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (self.lease_epoch, self.chain_attempted_count, self.unsearched_count)):
            raise ValueError("manifest counters must be non-negative integers")
        object.__setattr__(
            self,
            "feature_receipt_ids",
            _receipt_ids(self.feature_receipt_ids, require_nonempty=False),
        )
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

    @property
    def selection_snapshot_id(self) -> str:
        """Return the content address written for this immutable selection."""

        return hashlib.sha256(canonical_json(self.to_dict()).encode("utf-8")).hexdigest()


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


def continue_discovery(
    parent: CampaignManifest,
    *,
    verified_source: HistorySnapshot,
    verified_feature_receipt_ids: tuple[str, ...],
) -> CampaignRequest:
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
    parent_receipt_ids = _receipt_ids(parent.feature_receipt_ids, require_nonempty=True)
    if _receipt_ids(verified_feature_receipt_ids, require_nonempty=True) != parent_receipt_ids:
        raise ValueError("cannot continue mismatched feature receipt")
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
        # Legacy/isolated continuations retain their existing no-cache state.
        # A policy-bound worker must receive the explicitly chosen cache
        # treatment again; otherwise its immutable continuation cannot run.
        cache_choice=(
            parent.request.cache_choice
            if parent.request.activation_policy_digest is not None
            else None
        ),
        cache_path=(
            parent.request.cache_path
            if parent.request.activation_policy_digest is not None
            else None
        ),
        cache_age_seconds=None,
    )


def _contained_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible storage root must be absolute")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _campaign_path(root: Path, campaign_id: str, *parts: str) -> Path:
    if not isinstance(campaign_id, str) or not re.fullmatch(r"fcmp_[0-9a-f]{64}", campaign_id):
        raise ValueError("campaign_id is invalid")
    base = _contained_root(root)
    path = (base / "campaigns" / campaign_id).joinpath(*parts).resolve()
    if base not in path.parents:
        raise ValueError("campaign path escapes Flexible root")
    return path


def _write_atomic(path: Path, payload: dict[str, object]) -> Path:
    material = canonical_json(payload)
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
    return path


def _write_immutable(path: Path, payload: dict[str, object]) -> Path:
    material = canonical_json(payload)
    if path.exists():
        if path.read_text(encoding="utf-8") != material:
            raise ValueError("immutable campaign item already differs")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, mode="w", encoding="utf-8", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != material:
            raise ValueError("immutable campaign item already differs")
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _decode_canonical(value: object) -> object:
    if isinstance(value, list):
        return [_decode_canonical(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$date"} and isinstance(value["$date"], str):
        return date.fromisoformat(value["$date"])
    if set(value) == {"$decimal"} and isinstance(value["$decimal"], str):
        return Decimal(value["$decimal"])
    if set(value) == {"$float"} and isinstance(value["$float"], str):
        return float(value["$float"])
    return {key: _decode_canonical(item) for key, item in value.items()}


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} is invalid")
    return value


def _snapshot_from_dict(value: object) -> FeatureSnapshot:
    payload = _mapping(value, "source snapshot")
    return FeatureSnapshot(**payload)


def _partition_from_dict(value: object) -> EvaluationPartition:
    return EvaluationPartition(**_mapping(value, "evaluation partition"))


def _assignment_from_dict(value: object) -> FrontierAssignment | None:
    if value is None:
        return None
    payload = _mapping(value, "frontier assignment")
    strata = tuple(
        StratumAssignment(**_mapping(item, "frontier stratum"))
        for item in payload.pop("strata", [])
    )
    expected_hash = payload.pop("assignment_hash", None)
    assignment = FrontierAssignment(strata=strata, **payload)
    if expected_hash != assignment.assignment_hash:
        raise ValueError("frontier assignment hash is invalid")
    return assignment


def _request_from_payload(value: object) -> CampaignRequest:
    payload = _mapping(value, "campaign request")
    identity = _mapping(payload.get("identity"), "campaign request identity")
    runtime = _mapping(payload.get("runtime_provenance"), "campaign runtime provenance")
    split_payload = _mapping(identity.pop("split", None), "evaluation split")
    selection_payload = _mapping(identity.pop("selection_policy", None), "selection policy")
    return CampaignRequest(
        operation=identity.pop("operation"),
        frozen_members=tuple(identity.pop("frozen_members")),
        source_snapshots=tuple(
            _snapshot_from_dict(item) for item in identity.pop("source_snapshots")
        ),
        catalog_hash=identity.pop("catalog_hash"),
        engine_revision=identity.pop("engine_revision"),
        rulebook_ids=tuple(identity.pop("rulebook_ids")),
        feature_build_contract_hashes=tuple(identity.pop("feature_build_contract_hashes")),
        feature_plan_hashes=tuple(identity.pop("feature_plan_hashes")),
        execution_contract=ExecutionContract(**_mapping(
            identity.pop("execution_contract"), "execution contract"
        )),
        split=EvaluationSplit(
            method=split_payload["method"],
            requested_test_cutoff=split_payload["requested_test_cutoff"],
            training=_partition_from_dict(split_payload["training"]),
            test=_partition_from_dict(split_payload["test"]),
        ),
        runtime_budget=RuntimeBudget(**_mapping(
            identity.pop("runtime_budget"), "runtime budget"
        )),
        selection_policy=SelectionPolicy(**selection_payload),
        per_ticker_budget=identity.pop("per_ticker_budget"),
        activation_policy_digest=identity.pop("activation_policy_digest", None),
        frontier_assignment=_assignment_from_dict(identity.pop("frontier_assignment")),
        qualification_revision=identity.pop("qualification_revision"),
        group_snapshot=tuple(identity.pop("group_snapshot")),
        parent_campaign_id=identity.pop("parent_campaign_id"),
        execution_window_id=identity.pop("execution_window_id"),
        submitted_at=runtime.get("submitted_at"),
        cache_choice=runtime.get("cache_choice"),
        cache_path=runtime.get("cache_path"),
        cache_age_seconds=runtime.get("cache_age_seconds"),
    )


def _manifest_payload(manifest: CampaignManifest) -> dict[str, object]:
    return {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "flexible_campaign_manifest",
        "manifest": {
            "campaign_id": manifest.campaign_id,
            "request": {
                "identity": manifest.request.to_identity_dict(),
                "runtime_provenance": {
                    "submitted_at": manifest.request.submitted_at,
                    "cache_choice": manifest.request.cache_choice,
                    "cache_path": manifest.request.cache_path,
                    "cache_age_seconds": manifest.request.cache_age_seconds,
                },
            },
            "state": manifest.state,
            "items": [item.__dict__ for item in manifest.items],
            "lease_epoch": manifest.lease_epoch,
            "next_slot": manifest.next_slot,
            "uncommitted_slot": manifest.uncommitted_slot,
            "chain_attempted_count": manifest.chain_attempted_count,
            "unsearched_count": manifest.unsearched_count,
            "feature_receipt_ids": list(manifest.feature_receipt_ids),
            "selection_snapshot_id": manifest.selection_snapshot_id,
            "safe_error_code": manifest.safe_error_code,
            "safe_error_message": manifest.safe_error_message,
        },
    }


def write_campaign_manifest(root: Path, manifest: CampaignManifest) -> Path:
    """Atomically checkpoint one mutable manifest around immutable request data."""

    if not isinstance(manifest, CampaignManifest):
        raise ValueError("manifest must be CampaignManifest")
    return _write_atomic(
        _campaign_path(root, manifest.campaign_id, "manifest.json"),
        _manifest_payload(manifest),
    )


def read_campaign_manifest(root: Path, campaign_id: str) -> CampaignManifest:
    """Read and validate a versioned Flexible campaign checkpoint."""

    try:
        payload = _decode_canonical(json.loads(
            _campaign_path(root, campaign_id, "manifest.json").read_text(encoding="utf-8")
        ))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("campaign manifest is unreadable") from error
    document = _mapping(payload, "campaign manifest")
    if (
        document.get("schema_version") != _MANIFEST_SCHEMA_VERSION
        or document.get("artifact_kind") != "flexible_campaign_manifest"
    ):
        raise ValueError("campaign manifest version is invalid")
    data = _mapping(document.get("manifest"), "campaign manifest body")
    if data.get("campaign_id") != campaign_id:
        raise ValueError("campaign manifest identity is invalid")
    items = tuple(
        CampaignItem(**_mapping(item, "campaign item")) for item in data.get("items", [])
    )
    return CampaignManifest(
        request=_request_from_payload(data.get("request")),
        campaign_id=campaign_id,
        state=data.get("state"),
        items=items,
        lease_epoch=data.get("lease_epoch"),
        next_slot=data.get("next_slot"),
        uncommitted_slot=data.get("uncommitted_slot"),
        chain_attempted_count=data.get("chain_attempted_count"),
        unsearched_count=data.get("unsearched_count"),
        feature_receipt_ids=tuple(data.get("feature_receipt_ids", [])),
        selection_snapshot_id=data.get("selection_snapshot_id"),
        safe_error_code=data.get("safe_error_code"),
        safe_error_message=data.get("safe_error_message"),
    )


def _item_path(root: Path, manifest: CampaignManifest, ticker: str) -> Path:
    try:
        ordinal = manifest.request.frozen_members.index(ticker)
    except ValueError as error:
        raise ValueError("campaign item ticker is not frozen") from error
    return _campaign_path(root, manifest.campaign_id, "items", f"{ordinal:04d}-{ticker}.json")


def write_campaign_item(root: Path, manifest: CampaignManifest, item: CampaignItem) -> Path:
    """Write one immutable worker-owned item artifact before a manifest checkpoint."""

    if not isinstance(manifest, CampaignManifest) or not isinstance(item, CampaignItem):
        raise ValueError("campaign item requires a manifest and CampaignItem")
    return _write_immutable(
        _item_path(root, manifest, item.ticker),
        {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "artifact_kind": "flexible_campaign_item",
            "campaign_id": manifest.campaign_id,
            "item": item.__dict__,
        },
    )


def write_campaign_selection_snapshot(
    root: Path,
    manifest: CampaignManifest,
    snapshot: SelectionSnapshot,
) -> CampaignManifest:
    """Write immutable terminal selection evidence before its manifest reference."""

    if (
        not isinstance(manifest, CampaignManifest)
        or manifest.request.operation != "discover"
        or manifest.state not in {"completed", "completed_with_errors"}
        or manifest.uncommitted_slot is not None
    ):
        raise ValueError("selection snapshot requires terminal discovery")
    if not isinstance(snapshot, SelectionSnapshot):
        raise ValueError("selection snapshot is invalid")
    snapshot_payload = snapshot.to_dict()
    snapshot_id = snapshot.selection_snapshot_id
    if manifest.selection_snapshot_id is not None:
        if manifest.selection_snapshot_id != snapshot_id:
            raise ValueError("terminal discovery already has a selection snapshot")
        if not _selection_snapshot_is_verified(root, manifest):
            raise ValueError("existing selection snapshot is unavailable")
        return manifest
    snapshot_path = write_selection_snapshot(
        root,
        manifest.campaign_id,
        snapshot_payload,
    )
    updated = replace(manifest, selection_snapshot_id=snapshot_path.stem)
    write_campaign_manifest(root, updated)
    return updated


def _read_campaign_item(root: Path, manifest: CampaignManifest, ticker: str) -> CampaignItem | None:
    path = _item_path(root, manifest, ticker)
    if not path.is_file():
        return None
    try:
        payload = _decode_canonical(json.loads(path.read_text(encoding="utf-8")))
        document = _mapping(payload, "campaign item artifact")
        if (
            document.get("schema_version") != _MANIFEST_SCHEMA_VERSION
            or document.get("artifact_kind") != "flexible_campaign_item"
            or document.get("campaign_id") != manifest.campaign_id
        ):
            raise ValueError("campaign item artifact is invalid")
        item = CampaignItem(**_mapping(document.get("item"), "campaign item"))
        if item.ticker != ticker:
            raise ValueError("campaign item ticker is invalid")
        return item
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("campaign item artifact is invalid") from error


def _selection_snapshot_is_verified(root: Path, manifest: CampaignManifest) -> bool:
    """Return whether a manifest's claimed immutable selection evidence exists."""

    selection_snapshot_id = manifest.selection_snapshot_id
    if selection_snapshot_id is None:
        return True
    if not isinstance(selection_snapshot_id, str) or not _HASH.fullmatch(selection_snapshot_id):
        return False
    try:
        document = _decode_canonical(json.loads(
            _campaign_path(
                root,
                manifest.campaign_id,
                "selections",
                f"{selection_snapshot_id}.json",
            ).read_text(encoding="utf-8")
        ))
        payload = _mapping(document, "selection snapshot artifact")
        snapshot = _mapping(payload.get("snapshot"), "selection snapshot")
        return (
            payload.get("schema_version") == _MANIFEST_SCHEMA_VERSION
            and payload.get("artifact_kind") == "flexible_selection_snapshot"
            and payload.get("selection_snapshot_id") == selection_snapshot_id
            and hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()
            == selection_snapshot_id
        )
    except (OSError, json.JSONDecodeError, ValueError):
        return False


def _is_linked_continuation(parent: CampaignManifest, child: CampaignManifest) -> bool:
    """Return whether a child preserves every frozen parent semantic field."""

    parent_request = parent.request
    child_request = child.request
    parent_assignment = parent_request.frontier_assignment
    child_assignment = child_request.frontier_assignment
    if (
        parent_request.operation != "discover"
        or child_request.operation != "discover"
        or child_request.parent_campaign_id != parent.campaign_id
        or parent_assignment is None
        or child_assignment is None
        or parent.next_slot is None
        or parent.uncommitted_slot is not None
        or child_assignment.start_slot != parent.next_slot
    ):
        return False
    frozen_fields = (
        "frozen_members",
        "source_snapshots",
        "catalog_hash",
        "engine_revision",
        "rulebook_ids",
        "feature_build_contract_hashes",
        "feature_plan_hashes",
        "execution_contract",
        "split",
        "runtime_budget",
        "selection_policy",
        "per_ticker_budget",
        "activation_policy_digest",
        "qualification_revision",
        "group_snapshot",
    )
    assignment_fields = (
        "candidate_space_hash",
        "candidate_space_algorithm_version",
        "frontier_seed",
        "source_ticker",
        "strata",
        "stratum_multiplier",
        "stratum_offset",
        "algorithm_version",
        "stratification_revision",
    )
    return (
        all(
            getattr(parent_request, field_name) == getattr(child_request, field_name)
            for field_name in frozen_fields
        )
        and all(
            getattr(parent_assignment, field_name) == getattr(child_assignment, field_name)
            for field_name in assignment_fields
        )
        and (
            (
                child_request.cache_choice is None
                and child_request.cache_path is None
            )
            if parent_request.activation_policy_digest is None
            else (
                child_request.cache_choice == parent_request.cache_choice
                and child_request.cache_path == parent_request.cache_path
            )
        )
        and child_request.cache_age_seconds is None
    )


def read_campaign_chain(root: Path, campaign_id: str) -> tuple[CampaignManifest, ...]:
    """Read a child and its verified, immutable discovery-parent chain."""

    current = read_campaign_manifest(root, campaign_id)
    chain = [current]
    seen = {current.campaign_id}
    while current.request.parent_campaign_id is not None:
        parent_id = current.request.parent_campaign_id
        if parent_id in seen:
            raise ValueError("campaign parent chain is cyclic")
        parent = read_campaign_manifest(root, parent_id)
        if parent.state not in {"completed", "completed_with_errors"}:
            raise ValueError("campaign parent is not terminal")
        if not _is_linked_continuation(parent, current):
            raise ValueError("campaign parent continuation is incompatible")
        if not _selection_snapshot_is_verified(root, parent):
            raise ValueError("campaign parent selection snapshot is unavailable")
        chain.append(parent)
        seen.add(parent.campaign_id)
        current = parent
    return tuple(reversed(chain))


def build_campaign_selection_snapshot(
    chain: tuple[CampaignManifest, ...],
    evaluations: tuple[object, ...],
    *,
    ledger_digest: str,
    evaluation_digest: str,
) -> SelectionSnapshot:
    """Recompute one terminal snapshot from all verified chain evaluations."""

    if (
        isinstance(chain, (str, bytes))
        or not chain
        or any(not isinstance(manifest, CampaignManifest) for manifest in chain)
    ):
        raise ValueError("selection chain must contain campaign manifests")
    if isinstance(evaluations, (str, bytes)) or not isinstance(evaluations, tuple):
        raise ValueError("selection evaluations must be an immutable tuple")
    _hash(ledger_digest, "ledger_digest")
    _hash(evaluation_digest, "evaluation_digest")
    for parent, child in zip(chain, chain[1:]):
        if (
            parent.state not in {"completed", "completed_with_errors"}
            or parent.selection_snapshot_id is None
            or not _is_linked_continuation(parent, child)
        ):
            raise ValueError("selection chain parent is invalid")
    latest = chain[-1]
    if (
        latest.request.operation != "discover"
        or latest.state not in {"completed", "completed_with_errors"}
        or latest.uncommitted_slot is not None
    ):
        raise ValueError("selection snapshot requires terminal discovery")
    source = latest.request.source_snapshots[0]
    if any(
        getattr(evaluation, "ticker", None) != source.ticker
        or getattr(
            getattr(evaluation, "source_snapshot", None),
            "raw_history_fingerprint",
            getattr(evaluation, "source_fingerprint", None),
        ) != source.raw_history_fingerprint
        for evaluation in evaluations
    ):
        raise ValueError("selection evidence is outside frozen campaign scope")
    scope = canonical_json({
        "ticker": source.ticker,
        "source_fingerprint": source.raw_history_fingerprint,
        "split": latest.request.split.to_identity_dict(),
        "execution_revision": latest.request.execution_contract.execution_revision,
    })
    ranked = rank_qualified(evaluations)
    selection = select_timing_distinct_top_three(
        evaluations,
        latest.request.selection_policy,
    )
    blockers = tuple(
        {
            "blocked_rulebook_id": blocked_id,
            "representative_rulebook_id": representative_id,
            "overlap_numerator": evidence.overlap_numerator,
            "overlap_denominator": evidence.overlap_denominator,
        }
        for blocked_id, representative_id, evidence in selection.blockers
    )
    return SelectionSnapshot(
        "frontier_exhausted"
        if latest.unsearched_count == 0
        else "complete_assigned_window",
        ledger_digest,
        evaluation_digest,
        scope,
        latest.request.selection_policy.policy_revision,
        latest.request.selection_policy.pairing_algorithm_revision,
        tuple(item.rulebook_id for item in ranked),
        tuple(item.rulebook_id for item in selection.selected),
        blockers,
    )


def reconcile_campaign_manifest(root: Path, campaign_id: str) -> CampaignManifest:
    """Adopt verified worker artifacts and fail manifest claims missing their artifact."""

    manifest = read_campaign_manifest(root, campaign_id)
    reconciled: list[CampaignItem] = []
    for item in manifest.items:
        try:
            persisted = _read_campaign_item(root, manifest, item.ticker)
        except ValueError:
            persisted = None
        if persisted is not None:
            reconciled.append(persisted)
        elif item.artifact_id is not None:
            reconciled.append(CampaignItem(item.ticker, "failed"))
        else:
            reconciled.append(item)
    updated = replace(manifest, items=tuple(reconciled))
    if not _selection_snapshot_is_verified(root, updated):
        updated = replace(
            updated,
            state="failed",
            safe_error_code="ARTIFACT.SELECTION_SNAPSHOT_UNAVAILABLE",
            safe_error_message="selection snapshot unavailable",
        )
    if updated != manifest:
        write_campaign_manifest(root, updated)
    return updated


__all__ = ["CampaignItem", "CampaignManifest", "CampaignRequest", "CampaignState", "FeatureResolutionReceipt", "HistoricalItemState", "SelectionSnapshot", "build_campaign_selection_snapshot", "continue_discovery", "create_manifest", "read_campaign_chain", "read_campaign_manifest", "reconcile_campaign_manifest", "request_hash", "transition", "write_campaign_item", "write_campaign_manifest", "write_campaign_selection_snapshot"]
