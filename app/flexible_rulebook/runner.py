"""Durable, single-worker Flexible Rulebook campaign coordination."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Protocol

import pytz

from .campaigns import (
    CampaignManifest,
    CampaignRequest,
    continue_discovery,
    create_manifest,
    read_campaign_manifest,
    transition,
    write_campaign_manifest,
)
from .contracts import FeatureBuildContract, FeatureSnapshot
from .history import HistorySnapshot

_VIETNAM_TZ = pytz.timezone("Asia/Ho_Chi_Minh")


class FrozenSourceVerificationError(ValueError):
    """Safe worker-start failure; detailed loader errors never enter a manifest."""

    def __init__(self, safe_error_code: str) -> None:
        self.safe_error_code = safe_error_code
        super().__init__(safe_error_code)


class CampaignService(Protocol):
    """Minimal coordinator boundary; worker services return one checkpoint."""

    def run(
        self,
        manifest: CampaignManifest,
        *,
        verified_sources: tuple[HistorySnapshot, ...],
    ) -> CampaignManifest:
        """Run one persisted campaign window and return its checkpoint."""


def verify_frozen_source(
    manifest: CampaignManifest,
    *,
    source_loader: Callable[[FeatureSnapshot], HistorySnapshot],
    build_contract: FeatureBuildContract | None = None,
) -> tuple[HistorySnapshot, ...]:
    """Fresh-load and exactly prove every persisted source before worker work."""

    if not isinstance(manifest, CampaignManifest):
        raise ValueError("manifest must be a CampaignManifest")
    if not callable(source_loader):
        raise ValueError("source_loader must be callable")
    contract = FeatureBuildContract() if build_contract is None else build_contract
    if not isinstance(contract, FeatureBuildContract):
        raise ValueError("build_contract must be a FeatureBuildContract")
    if set(manifest.request.feature_build_contract_hashes) != {
        contract.feature_build_contract_hash
    }:
        raise FrozenSourceVerificationError("FEATURE.REVISION_UNAVAILABLE")

    verified: list[HistorySnapshot] = []
    for expected in manifest.request.source_snapshots:
        try:
            fresh = source_loader(expected)
        except Exception as error:
            raise FrozenSourceVerificationError("SOURCE.UNAVAILABLE") from error
        if (
            not isinstance(fresh, HistorySnapshot)
            or fresh.quality_state == "invalid"
            or fresh.fingerprint is None
            or fresh.first_date is None
            or fresh.as_of_date is None
        ):
            raise FrozenSourceVerificationError("SOURCE.UNAVAILABLE")
        if (
            fresh.ticker,
            fresh.fingerprint,
            fresh.requested_start,
            fresh.requested_as_of,
            fresh.first_date,
            fresh.as_of_date,
            fresh.quality_state,
        ) != (
            expected.ticker,
            expected.raw_history_fingerprint,
            expected.requested_start,
            expected.requested_as_of,
            expected.first_date,
            expected.as_of_date,
            expected.quality_state,
        ):
            raise FrozenSourceVerificationError("SOURCE.CHANGED")
        verified.append(fresh)
    return tuple(verified)


def _runner_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible runner root must be absolute")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _lease_path(root: Path) -> Path:
    return _runner_root(root) / "campaigns" / "active-lease.json"


def _heartbeat_time(now: datetime | None) -> datetime:
    timestamp = datetime.now(_VIETNAM_TZ) if now is None else now
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("lease heartbeat must be timezone-aware")
    return timestamp.astimezone(_VIETNAM_TZ)


def _read_lease(lease_path: Path) -> dict[str, object]:
    try:
        lease = json.loads(lease_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("active campaign lease is unavailable") from error
    if not isinstance(lease, dict):
        raise ValueError("active campaign lease is invalid")
    return lease


def _write_lease(lease_path: Path, lease: dict[str, object]) -> None:
    payload = json.dumps(lease, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=lease_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, lease_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_campaign(campaign_id: str, root: Path) -> CampaignManifest:
    """Read one validated persisted campaign without changing its state."""

    return read_campaign_manifest(root, campaign_id)


def submit_campaign(request: CampaignRequest, root: Path) -> str:
    """Persist one frozen request, attaching duplicate submission to its campaign."""

    manifest = create_manifest(request)
    manifest_path = root / "campaigns" / manifest.campaign_id / "manifest.json"
    if manifest_path.is_file():
        read_campaign_manifest(root, manifest.campaign_id)
        return manifest.campaign_id
    write_campaign_manifest(root, manifest)
    return manifest.campaign_id


def _claim_manifest(
    manifest: CampaignManifest, root: Path, *, now: datetime | None = None
) -> CampaignManifest:
    """Atomically grant the phase-one global worker lease to one legal manifest."""

    lease_path = _lease_path(root)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_at = _heartbeat_time(now)
    payload = json.dumps(
        {
            "campaign_id": manifest.campaign_id,
            "lease_epoch": manifest.lease_epoch + 1,
            "heartbeat_at": heartbeat_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        descriptor = os.open(lease_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("active campaign lease is held") from error
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        claimed = replace(
            transition(manifest, "running"),
            lease_epoch=manifest.lease_epoch + 1,
        )
        write_campaign_manifest(root, claimed)
        return claimed
    except Exception:
        try:
            lease_path.unlink()
        except FileNotFoundError:
            pass
        raise


def claim_campaign(
    campaign_id: str, root: Path, *, now: datetime | None = None
) -> CampaignManifest:
    """Atomically grant the phase-one global worker lease to one queued campaign."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state != "queued":
        raise ValueError("only a queued campaign can claim the worker lease")
    return _claim_manifest(manifest, root, now=now)


def release_campaign_lease(campaign_id: str, root: Path) -> None:
    """Release the global lease only when it still belongs to this campaign."""

    lease_path = _lease_path(root)
    lease = _read_lease(lease_path)
    if lease.get("campaign_id") != campaign_id:
        raise ValueError("active campaign lease belongs to another campaign")
    lease_path.unlink()


def heartbeat_campaign(
    campaign_id: str, root: Path, *, now: datetime | None = None
) -> None:
    """Atomically refresh the matching running campaign's global lease."""

    lease_path = _lease_path(root)
    lease = _read_lease(lease_path)
    manifest = read_campaign(campaign_id, root)
    if (
        lease.get("campaign_id") != campaign_id
        or lease.get("lease_epoch") != manifest.lease_epoch
        or manifest.state != "running"
    ):
        raise ValueError("active campaign lease does not match running manifest")
    lease["heartbeat_at"] = _heartbeat_time(now).isoformat()
    _write_lease(lease_path, lease)


def recover_stale_lease(
    root: Path, *, now: datetime | None = None, stale_after_seconds: int
) -> CampaignManifest | None:
    """Interrupt a stale running worker and release its exact global lease."""

    if (
        isinstance(stale_after_seconds, bool)
        or not isinstance(stale_after_seconds, int)
        or stale_after_seconds <= 0
    ):
        raise ValueError("stale lease threshold must be a positive integer")
    lease_path = _lease_path(root)
    if not lease_path.is_file():
        return None
    lease = _read_lease(lease_path)
    campaign_id = lease.get("campaign_id")
    lease_epoch = lease.get("lease_epoch")
    heartbeat_value = lease.get("heartbeat_at")
    if (
        not isinstance(campaign_id, str)
        or isinstance(lease_epoch, bool)
        or not isinstance(lease_epoch, int)
        or not isinstance(heartbeat_value, str)
    ):
        raise ValueError("active campaign lease is invalid")
    try:
        heartbeat_at = datetime.fromisoformat(heartbeat_value)
    except ValueError as error:
        raise ValueError("active campaign lease heartbeat is invalid") from error
    current_time = _heartbeat_time(now)
    if heartbeat_at.tzinfo is None or heartbeat_at.utcoffset() is None:
        raise ValueError("active campaign lease heartbeat is invalid")
    if (current_time - heartbeat_at.astimezone(_VIETNAM_TZ)).total_seconds() <= stale_after_seconds:
        return None
    manifest = read_campaign(campaign_id, root)
    if manifest.state != "running" or manifest.lease_epoch != lease_epoch:
        raise ValueError("active campaign lease does not match running manifest")
    interrupted = transition(manifest, "interrupted")
    write_campaign_manifest(root, interrupted)
    lease_path.unlink()
    return interrupted


def resume_campaign(
    campaign_id: str, root: Path, *, now: datetime | None = None
) -> str:
    """Reclaim a recoverable persisted window without changing its frozen request."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state not in {"interrupted", "cancelled", "blocked"}:
        raise ValueError("campaign is not in a resumable state")
    _claim_manifest(manifest, root, now=now)
    return campaign_id


def continue_campaign(
    parent_campaign_id: str,
    root: Path,
    *,
    source_loader: Callable[[FeatureSnapshot], HistorySnapshot],
    build_contract: FeatureBuildContract | None = None,
) -> str:
    """Persist the next discovery window from its exact verified parent only."""

    parent = read_campaign(parent_campaign_id, root)
    verified_sources = verify_frozen_source(
        parent,
        source_loader=source_loader,
        build_contract=build_contract,
    )
    if len(verified_sources) != 1:
        raise ValueError("discovery continuation requires one verified source")
    child_request = continue_discovery(
        parent,
        verified_source=verified_sources[0],
        verified_feature_receipt_ids=parent.feature_receipt_ids,
    )
    return submit_campaign(child_request, root)


def run_campaign(
    campaign_id: str,
    root: Path,
    service: CampaignService,
    *,
    source_loader: Callable[[FeatureSnapshot], HistorySnapshot],
    build_contract: FeatureBuildContract | None = None,
) -> CampaignManifest:
    """Prove frozen sources, persist a service checkpoint, and release terminal work."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state != "running":
        raise ValueError("only a running campaign can execute")
    try:
        verified_sources = verify_frozen_source(
            manifest,
            source_loader=source_loader,
            build_contract=build_contract,
        )
    except FrozenSourceVerificationError as error:
        blocked = replace(
            transition(manifest, "blocked"),
            safe_error_code=error.safe_error_code,
            safe_error_message="Frozen source or feature revision is unavailable.",
        )
        write_campaign_manifest(root, blocked)
        release_campaign_lease(campaign_id, root)
        return blocked
    result = service.run(manifest, verified_sources=verified_sources)
    if (
        not isinstance(result, CampaignManifest)
        or result.campaign_id != manifest.campaign_id
        or result.request != manifest.request
        or result.lease_epoch != manifest.lease_epoch
    ):
        raise ValueError("service returned an incompatible campaign checkpoint")
    write_campaign_manifest(root, result)
    if result.state in {"cancelled", "completed", "completed_with_errors", "failed"}:
        release_campaign_lease(campaign_id, root)
    return result


def request_cancel(campaign_id: str, root: Path) -> None:
    """Request cancellation without skipping work already under a worker claim."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state == "queued":
        write_campaign_manifest(root, transition(manifest, "cancelled"))
    elif manifest.state == "running":
        write_campaign_manifest(root, transition(manifest, "cancelling"))
    elif manifest.state not in {"cancelling", "cancelled"}:
        raise ValueError("campaign cannot be cancelled from its terminal state")


__all__ = ["CampaignService", "FrozenSourceVerificationError", "claim_campaign", "continue_campaign", "heartbeat_campaign", "read_campaign", "recover_stale_lease", "release_campaign_lease", "request_cancel", "resume_campaign", "run_campaign", "submit_campaign", "verify_frozen_source"]
