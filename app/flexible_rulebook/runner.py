"""Durable, single-worker Flexible Rulebook campaign coordination."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from typing import Callable, Literal, Protocol

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


@dataclass(frozen=True)
class WorkerFault:
    """Safe classification used by coordinator retry/terminal decisions."""

    kind: Literal["source", "shared", "item_transient", "invariant", "watchdog"]
    safe_error_code: str
    retryable: bool
    campaign_blocking: bool


class WorkerWatchdogError(RuntimeError):
    """Raised by an outer watchdog when the worker outlives its hard limit."""


class SharedInfrastructureError(ConnectionError):
    """Explicit shared DB/storage failure; never fan out as item invalidity."""


class TransientItemError(TimeoutError):
    """Explicit one-ticker transient failure eligible for one retry."""


def classify_worker_fault(error: BaseException, *, shared_scope: bool = False) -> WorkerFault:
    """Map internal exceptions to credential-safe, deterministic fault classes."""

    if isinstance(error, FrozenSourceVerificationError):
        return WorkerFault("source", error.safe_error_code, False, True)
    if isinstance(error, WorkerWatchdogError):
        return WorkerFault("watchdog", "INFRA.WATCHDOG_TIMEOUT", False, False)
    if isinstance(error, SharedInfrastructureError):
        return WorkerFault("shared", "INFRA.SHARED_UNAVAILABLE", False, True)
    if isinstance(error, TransientItemError):
        return WorkerFault("item_transient", "INFRA.ITEM_TRANSIENT", True, False)
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        if shared_scope:
            return WorkerFault("shared", "INFRA.SHARED_UNAVAILABLE", False, True)
        return WorkerFault("item_transient", "INFRA.ITEM_TRANSIENT", True, False)
    return WorkerFault("invariant", "INFRA.WORKER_CONTRACT", False, False)


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
    campaign_id: str,
    root: Path,
    *,
    now: datetime | None = None,
    source_loader: Callable[[FeatureSnapshot], HistorySnapshot] | None = None,
    receipt_resolver: Callable[[HistorySnapshot], object] | None = None,
) -> str:
    """Reclaim a recoverable window after proving its frozen source/receipt."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state not in {"interrupted", "cancelled", "blocked"}:
        raise ValueError("campaign is not in a resumable state")
    if manifest.feature_receipt_ids:
        if not callable(source_loader) or not callable(receipt_resolver):
            raise ValueError("receipt-bound Resume requires source_loader and receipt_resolver")
        verified_sources = verify_frozen_source(
            manifest,
            source_loader=source_loader,
        )
        # The checkpoint service validates the plan/source/build identity and
        # refuses to replace an already-persisted receipt.  No lease or cursor
        # is changed until this proof succeeds.
        from .service import ReceiptCheckpointService

        ReceiptCheckpointService(
            root,
            receipt_resolver=receipt_resolver,
        ).run(manifest, verified_sources=verified_sources)
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
    if manifest.state not in {"running", "cancelling"}:
        raise ValueError("only a running campaign can execute")
    if manifest.state == "cancelling":
        cancelled = transition(manifest, "cancelled")
        write_campaign_manifest(root, cancelled)
        release_campaign_lease(campaign_id, root)
        return cancelled
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
    result: CampaignManifest | None = None
    for attempt in range(2):
        try:
            result = service.run(manifest, verified_sources=verified_sources)
            break
        except Exception as error:
            fault = classify_worker_fault(error)
            if fault.retryable and attempt == 0:
                continue
            target = "blocked" if fault.campaign_blocking else (
                "failed" if fault.kind == "invariant" else "interrupted"
            )
            failed = replace(
                transition(manifest, target),
                safe_error_code=fault.safe_error_code,
                safe_error_message="Worker stopped before a safe campaign checkpoint.",
            )
            write_campaign_manifest(root, failed)
            release_campaign_lease(campaign_id, root)
            return failed
    assert result is not None
    if (
        not isinstance(result, CampaignManifest)
        or result.campaign_id != manifest.campaign_id
        or result.request != manifest.request
        or result.lease_epoch != manifest.lease_epoch
    ):
        # A worker cannot choose its own manifest identity.  Treat a malformed
        # checkpoint as an invariant fault and release the lease so the queue
        # cannot be wedged behind an untrusted return value.
        fault = classify_worker_fault(ValueError("service returned an incompatible campaign checkpoint"))
        failed = replace(
            transition(manifest, "failed"),
            safe_error_code=fault.safe_error_code,
            safe_error_message="Worker stopped before a safe campaign checkpoint.",
        )
        write_campaign_manifest(root, failed)
        release_campaign_lease(campaign_id, root)
        return failed
    write_campaign_manifest(root, result)
    if result.state in {"cancelled", "completed", "completed_with_errors", "failed"}:
        release_campaign_lease(campaign_id, root)
    return result


def start_campaign_worker(
    campaign_id: str,
    root: Path,
    *,
    service_ref: str,
    source_loader_ref: str,
    python_executable: str | None = None,
    process_group: bool = False,
) -> subprocess.Popen[bytes]:
    """Persist a tiny request and start exactly one module worker process."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state != "running":
        raise ValueError("only a running campaign can start a worker")
    from .worker import WorkerRequest

    request = WorkerRequest(
        campaign_id=campaign_id,
        root=_runner_root(root),
        service_ref=service_ref,
        source_loader_ref=source_loader_ref,
    )
    request_path = _runner_root(root) / "campaigns" / campaign_id / "worker-request.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=request_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, request_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    executable = sys.executable if python_executable is None else python_executable
    if not isinstance(executable, str) or not executable:
        raise ValueError("python_executable must be non-empty text")
    if not isinstance(process_group, bool):
        raise ValueError("process_group must be boolean")
    return subprocess.Popen(
        [executable, "-m", "flexible_rulebook.worker", str(request_path)],
        stdin=subprocess.DEVNULL,
        # Inherit process streams so a noisy worker cannot deadlock on an
        # undrained PIPE; the worker traceback stays in the process log.
        stdout=None,
        stderr=None,
        start_new_session=process_group and os.name == "posix",
    )


def _interrupt_dead_worker(campaign_id: str, root: Path) -> CampaignManifest:
    """Mark only a still-running campaign interrupted after worker loss."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state != "running":
        return manifest
    interrupted = transition(manifest, "interrupted")
    write_campaign_manifest(root, interrupted)
    lease_path = _lease_path(root)
    try:
        lease = _read_lease(lease_path)
    except (OSError, ValueError):
        return interrupted
    if lease.get("campaign_id") == campaign_id and lease.get("lease_epoch") == manifest.lease_epoch:
        try:
            lease_path.unlink()
        except FileNotFoundError:
            pass
    return interrupted


def watch_campaign_worker(
    process: subprocess.Popen[bytes],
    campaign_id: str,
    root: Path,
    *,
    watchdog_seconds: int = 18_000,
    terminate_process_group: bool = False,
) -> CampaignManifest:
    """Wait for a worker; timeout/death yields resumable interruption only."""

    if not all(callable(getattr(process, name, None)) for name in ("wait", "terminate", "kill")):
        raise ValueError("process must provide wait, terminate, and kill")
    if (
        isinstance(watchdog_seconds, bool)
        or not isinstance(watchdog_seconds, int)
        or watchdog_seconds <= 0
    ):
        raise ValueError("watchdog_seconds must be a positive integer")
    if not isinstance(terminate_process_group, bool):
        raise ValueError("terminate_process_group must be boolean")
    try:
        process.wait(timeout=watchdog_seconds)
    except subprocess.TimeoutExpired:
        if terminate_process_group and os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (AttributeError, ProcessLookupError):
                process.terminate()
        else:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if terminate_process_group and os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (AttributeError, ProcessLookupError):
                    process.kill()
            else:
                process.kill()
            process.wait()
        return _interrupt_dead_worker(campaign_id, root)
    manifest = read_campaign(campaign_id, root)
    if manifest.state == "running":
        return _interrupt_dead_worker(campaign_id, root)
    return manifest


def request_cancel(campaign_id: str, root: Path) -> None:
    """Request cancellation without skipping work already under a worker claim."""

    manifest = read_campaign(campaign_id, root)
    if manifest.state == "queued":
        write_campaign_manifest(root, transition(manifest, "cancelled"))
    elif manifest.state == "running":
        write_campaign_manifest(root, transition(manifest, "cancelling"))
    elif manifest.state not in {"cancelling", "cancelled"}:
        raise ValueError("campaign cannot be cancelled from its terminal state")


__all__ = ["CampaignService", "FrozenSourceVerificationError", "SharedInfrastructureError", "TransientItemError", "WorkerFault", "WorkerWatchdogError", "claim_campaign", "classify_worker_fault", "continue_campaign", "heartbeat_campaign", "read_campaign", "recover_stale_lease", "release_campaign_lease", "request_cancel", "resume_campaign", "run_campaign", "start_campaign_worker", "submit_campaign", "verify_frozen_source", "watch_campaign_worker"]
