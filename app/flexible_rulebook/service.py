"""Concrete, receipt-first services for Flexible Rulebook campaigns."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
from typing import Callable

from .campaigns import CampaignItem, CampaignManifest, write_campaign_item
from .contracts import FeatureResolutionReceipt
from .history import HistorySnapshot
from .storage import append_ledger_chunk, write_feature_resolution_receipt
from .search import CandidateSpace, DiscoveryResult, FrontierAssignment, scheduled_candidates


def discovery_ledger_rows(
    space: CandidateSpace,
    assignment: FrontierAssignment,
    result: DiscoveryResult,
    *,
    feature_receipt_id: str,
) -> tuple[dict[str, object], ...]:
    """Turn committed frozen discovery outcomes into compact immutable ledger rows."""

    if not isinstance(space, CandidateSpace) or not isinstance(assignment, FrontierAssignment) or not isinstance(result, DiscoveryResult):
        raise ValueError("ledger conversion requires frozen discovery inputs")
    scheduled = tuple(scheduled_candidates(space, assignment))
    outcomes = dict(result.outcomes)
    rows: list[dict[str, object]] = []
    strata = {item.stratum_id: item for item in assignment.strata}
    seen_per_stratum: dict[str, int] = {}
    for slot, stratum_id, canonical, _definition in scheduled:
        if slot not in outcomes:
            continue
        stratum_slot = seen_per_stratum.get(stratum_id, 0)
        seen_per_stratum[stratum_id] = stratum_slot + 1
        stratum = strata[stratum_id]
        rows.append({"candidate_space_hash": space.candidate_space_hash, "candidate_space_size": space.size, "candidate_space_algorithm_version": space.candidate_space_algorithm_version, "canonical_index": canonical, "global_slot": slot, "stratum_id": stratum_id, "stratum_slot": stratum_slot, "assignment_hash": assignment.assignment_hash, "frontier_algorithm_version": assignment.algorithm_version, "stratification_revision": assignment.stratification_revision, "stratum_multiplier": assignment.stratum_multiplier, "stratum_offset": assignment.stratum_offset, "stratum_quota": stratum.quota, "seed_fingerprint": hashlib.sha256(assignment.frontier_seed.encode("utf-8")).hexdigest(), "feature_receipt_id": feature_receipt_id, "outcome": outcomes[slot], "unsearched_count": result.unsearched_count})
    return tuple(rows)


def persist_discovery_ledger(
    root: Path, *, campaign_id: str, ticker: str, rows: tuple[dict[str, object], ...]
) -> Path:
    """Persist only receipt-bound, frozen discovery rows as one immutable chunk."""

    return append_ledger_chunk(root, campaign_id, ticker, rows)


def checkpoint_campaign_item(
    root: Path, manifest: CampaignManifest, item: CampaignItem
) -> CampaignManifest:
    """Write the worker-owned item first, then return its coordinator checkpoint."""

    if not isinstance(manifest, CampaignManifest) or not isinstance(item, CampaignItem):
        raise ValueError("item checkpoint requires campaign manifest and item")
    write_campaign_item(root, manifest, item)
    items = tuple(item if current.ticker == item.ticker else current for current in manifest.items)
    return replace(manifest, items=items)


class ReceiptCheckpointService:
    """Persist exact feature bytes proof before any discovery slot can commit."""

    def __init__(
        self,
        root: Path,
        *,
        receipt_resolver: Callable[[HistorySnapshot], FeatureResolutionReceipt],
    ) -> None:
        if not isinstance(root, Path) or not root.is_absolute():
            raise ValueError("Flexible service root must be absolute")
        if not callable(receipt_resolver):
            raise ValueError("receipt_resolver must be callable")
        self._root = root
        self._receipt_resolver = receipt_resolver

    def run(
        self,
        manifest: CampaignManifest,
        *,
        verified_sources: tuple[HistorySnapshot, ...],
    ) -> CampaignManifest:
        if (
            not isinstance(manifest, CampaignManifest)
            or manifest.request.operation != "discover"
            or len(verified_sources) != 1
            or len(manifest.request.source_snapshots) != 1
        ):
            raise ValueError("receipt checkpoint requires one discovery source")
        receipt = self._receipt_resolver(verified_sources[0])
        if (
            not isinstance(receipt, FeatureResolutionReceipt)
            or receipt.plan.snapshot != manifest.request.source_snapshots[0]
            or receipt.plan.feature_plan_hash not in manifest.request.feature_plan_hashes
            or receipt.plan.build_contract.feature_build_contract_hash
            not in manifest.request.feature_build_contract_hashes
        ):
            raise ValueError("resolved receipt does not match frozen campaign request")
        if manifest.feature_receipt_ids and manifest.feature_receipt_ids != (receipt.receipt_id,):
            raise ValueError("resolved receipt differs from persisted campaign receipt")
        write_feature_resolution_receipt(
            self._root,
            manifest.campaign_id,
            verified_sources[0].ticker,
            receipt,
        )
        return replace(manifest, feature_receipt_ids=(receipt.receipt_id,))


__all__ = ["ReceiptCheckpointService", "checkpoint_campaign_item", "discovery_ledger_rows", "persist_discovery_ledger"]
