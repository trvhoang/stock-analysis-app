"""Canonical request and status contracts for UI-triggered scope expansion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Literal

from .benchmark import decode_canonical_scalars
from .contracts import canonical_json


SCOPE_EXPANSION_SCHEMA_VERSION = 1
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TICKER = re.compile(r"^[A-Z0-9._-]+$")
_SEED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_STATES = frozenset({"queued", "running", "completed", "failed", "cancelled", "interrupted"})


def _decode_scope_scalars(value: object) -> object:
    if isinstance(value, list):
        return [_decode_scope_scalars(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"$date"} and isinstance(value["$date"], str):
            return date.fromisoformat(value["$date"])
        return {key: _decode_scope_scalars(item) for key, item in value.items()}
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _non_negative_float(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return number


def parse_scope_values(value: str, kind: Literal["ticker", "seed"]) -> tuple[str, ...]:
    """Parse comma/space-separated UI scope values into sorted unique tokens."""

    if kind not in {"ticker", "seed"}:
        raise ValueError("scope value kind must be ticker or seed")
    if not isinstance(value, str):
        raise ValueError(f"{kind} input must be text")
    tokens = [token for token in re.split(r"[\s,]+", value.strip()) if token]
    normalized: set[str] = set()
    for token in tokens:
        item = token.upper() if kind == "ticker" else token
        pattern = _TICKER if kind == "ticker" else _SEED
        if not pattern.fullmatch(item):
            raise ValueError(f"{kind} contains an invalid value")
        normalized.add(item)
    return tuple(sorted(normalized))


def _scope_values(values: object, kind: Literal["ticker", "seed"], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        items = tuple(values)  # type: ignore[arg-type]
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    parsed = parse_scope_values(" ".join(str(item) for item in items), kind)
    if len(parsed) != len(items):
        raise ValueError(f"{name} must contain unique values")
    return parsed


@dataclass(frozen=True)
class ScopeExpansionRequest:
    """Immutable additive benchmark scope and operator approval metadata."""

    policy_digest: str
    benchmark_as_of: date
    tickers: tuple[str, ...]
    seeds: tuple[str, ...]
    cap_attempts: int
    cold_samples: int
    worker_count: int
    approved_by: str
    approval_note: str
    schema_version: int = SCOPE_EXPANSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _digest(self.policy_digest, "policy_digest")
        if type(self.benchmark_as_of) is not date:
            raise ValueError("benchmark_as_of must be a date without a time")
        object.__setattr__(self, "tickers", _scope_values(self.tickers, "ticker", "tickers"))
        object.__setattr__(self, "seeds", _scope_values(self.seeds, "seed", "seeds"))
        if not self.tickers or not self.seeds:
            raise ValueError("tickers and seeds must be non-empty")
        _positive_int(self.cap_attempts, "cap_attempts")
        if self.cold_samples != 100:
            raise ValueError("cold_samples must be exactly 100")
        if self.worker_count != 1:
            raise ValueError("worker_count must be exactly 1")
        _text(self.approved_by, "approved_by")
        _text(self.approval_note, "approval_note")
        if self.schema_version != SCOPE_EXPANSION_SCHEMA_VERSION:
            raise ValueError("scope expansion schema version is unsupported")

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "policy_digest": self.policy_digest,
            "benchmark_as_of": self.benchmark_as_of,
            "tickers": self.tickers,
            "seeds": self.seeds,
            "cap_attempts": self.cap_attempts,
            "cold_samples": self.cold_samples,
            "worker_count": self.worker_count,
            "approved_by": self.approved_by,
            "approval_note": self.approval_note,
            "schema_version": self.schema_version,
        }

    @property
    def job_id(self) -> str:
        return "fse_" + hashlib.sha256(canonical_json(self.to_identity_dict()).encode("utf-8")).hexdigest()

    def to_document(self) -> dict[str, object]:
        return {
            "kind": "flexible_rulebook_scope_expansion_request",
            "job_id": self.job_id,
            "payload": self.to_identity_dict(),
        }

    @classmethod
    def from_document(cls, value: object) -> "ScopeExpansionRequest":
        if not isinstance(value, dict) or set(value) != {"kind", "job_id", "payload"}:
            raise ValueError("scope expansion request document is invalid")
        if value["kind"] != "flexible_rulebook_scope_expansion_request" or not isinstance(value["payload"], dict):
            raise ValueError("scope expansion request document is invalid")
        payload = _decode_scope_scalars(decode_canonical_scalars(value["payload"]))
        required = {"policy_digest", "benchmark_as_of", "tickers", "seeds", "cap_attempts", "cold_samples", "worker_count", "approved_by", "approval_note", "schema_version"}
        if set(payload) != required:
            raise ValueError("scope expansion request payload is invalid")
        request = cls(**payload)
        if value["job_id"] != request.job_id:
            raise ValueError("scope expansion request job ID does not match payload")
        return request


def build_scope_expansion_request(
    policy: object,
    *,
    benchmark_as_of: date,
    additional_tickers: str,
    additional_seeds: str,
    approved_by: str,
    approval_note: str,
) -> ScopeExpansionRequest:
    """Build an additive request from the current immutable active policy."""

    policy_digest = _digest(getattr(policy, "policy_digest", None), "policy_digest")
    current_tickers = _scope_values(getattr(policy, "allowed_tickers", ()), "ticker", "allowed_tickers")
    current_seeds = _scope_values(getattr(policy, "allowed_seeds", ()), "seed", "allowed_seeds")
    additions_tickers = parse_scope_values(additional_tickers, "ticker")
    additions_seeds = parse_scope_values(additional_seeds, "seed")
    tickers = tuple(sorted(set(current_tickers).union(additions_tickers)))
    seeds = tuple(sorted(set(current_seeds).union(additions_seeds)))
    if set(tickers) == set(current_tickers) and set(seeds) == set(current_seeds):
        raise ValueError("scope expansion requires at least one new ticker or seed")
    cap_attempts = _positive_int(getattr(policy, "cap_attempts", None), "cap_attempts")
    if getattr(policy, "worker_count", None) != 1:
        raise ValueError("active policy worker_count must be exactly 1")
    return ScopeExpansionRequest(
        policy_digest=policy_digest,
        benchmark_as_of=benchmark_as_of,
        tickers=tickers,
        seeds=seeds,
        cap_attempts=cap_attempts,
        cold_samples=100,
        worker_count=1,
        approved_by=_text(approved_by, "approved_by"),
        approval_note=_text(approval_note, "approval_note"),
    )


@dataclass(frozen=True)
class ProgressEvent:
    """Optional progress telemetry that cannot change operation outcomes."""

    phase: str
    completed: int
    total: int
    label: str
    safe_error: str | None = None

    def __post_init__(self) -> None:
        _text(self.phase, "phase")
        _non_negative_int(self.completed, "completed")
        _positive_int(self.total, "total")
        if self.completed > self.total:
            raise ValueError("completed cannot exceed total")
        _text(self.label, "label")
        if self.safe_error is not None:
            _text(self.safe_error, "safe_error")


@dataclass(frozen=True)
class ScopeExpansionStatus:
    """Durable progress snapshot for one scope-expansion job."""

    job_id: str
    state: Literal["queued", "running", "completed", "failed", "cancelled", "interrupted"]
    phase: str
    completed_pairs: int
    total_pairs: int
    completed_windows: int
    required_windows: int
    current_ticker: str | None = None
    current_seed: str | None = None
    elapsed_seconds: float = 0.0
    report_digest: str | None = None
    policy_digest: str | None = None
    safe_error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not self.job_id.startswith("fse_") or not _DIGEST.fullmatch(self.job_id[4:]):
            raise ValueError("job_id is invalid")
        if self.state not in _STATES:
            raise ValueError("status state is invalid")
        _text(self.phase, "phase")
        _non_negative_int(self.completed_pairs, "completed_pairs")
        _positive_int(self.total_pairs, "total_pairs")
        if self.completed_pairs > self.total_pairs:
            raise ValueError("completed_pairs cannot exceed total_pairs")
        _non_negative_int(self.completed_windows, "completed_windows")
        _positive_int(self.required_windows, "required_windows")
        if self.completed_windows > self.required_windows:
            raise ValueError("completed_windows cannot exceed required_windows")
        if self.current_ticker is not None:
            parse_scope_values(self.current_ticker, "ticker")
        if self.current_seed is not None:
            parse_scope_values(self.current_seed, "seed")
        _non_negative_float(self.elapsed_seconds, "elapsed_seconds")
        if self.report_digest is not None:
            _digest(self.report_digest, "report_digest")
        if self.policy_digest is not None:
            _digest(self.policy_digest, "policy_digest")
        if self.safe_error is not None:
            _text(self.safe_error, "safe_error")

    def to_document(self) -> dict[str, object]:
        return {
            "kind": "flexible_rulebook_scope_expansion_status",
            "payload": {
                "job_id": self.job_id,
                "state": self.state,
                "phase": self.phase,
                "completed_pairs": self.completed_pairs,
                "total_pairs": self.total_pairs,
                "completed_windows": self.completed_windows,
                "required_windows": self.required_windows,
                "current_ticker": self.current_ticker,
                "current_seed": self.current_seed,
                "elapsed_seconds": self.elapsed_seconds,
                "report_digest": self.report_digest,
                "policy_digest": self.policy_digest,
                "safe_error": self.safe_error,
            },
        }

    @classmethod
    def from_document(cls, value: object) -> "ScopeExpansionStatus":
        if not isinstance(value, dict) or set(value) != {"kind", "payload"} or value["kind"] != "flexible_rulebook_scope_expansion_status" or not isinstance(value["payload"], dict):
            raise ValueError("scope expansion status document is invalid")
        payload = _decode_scope_scalars(decode_canonical_scalars(value["payload"]))
        required = {"job_id", "state", "phase", "completed_pairs", "total_pairs", "completed_windows", "required_windows", "current_ticker", "current_seed", "elapsed_seconds", "report_digest", "policy_digest", "safe_error"}
        if set(payload) != required:
            raise ValueError("scope expansion status payload is invalid")
        return cls(**payload)


def _path(path: Path | str) -> Path:
    target = Path(path)
    if not target.is_absolute() or target.exists() and target.is_dir():
        raise ValueError("scope expansion path must be an absolute file path")
    return target.resolve()


def write_scope_request(path: Path | str, request: ScopeExpansionRequest) -> Path:
    if not isinstance(request, ScopeExpansionRequest):
        raise ValueError("request must be ScopeExpansionRequest")
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    material = canonical_json(request.to_document())
    if target.exists():
        if target.read_text(encoding="utf-8") != material:
            raise ValueError("scope expansion request is immutable")
        return target
    with tempfile.NamedTemporaryFile(dir=target.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, target)
    except FileExistsError:
        if target.read_text(encoding="utf-8") != material:
            raise ValueError("scope expansion request is immutable")
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def write_scope_status(path: Path | str, status: ScopeExpansionStatus) -> Path:
    if not isinstance(status, ScopeExpansionStatus):
        raise ValueError("status must be ScopeExpansionStatus")
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    material = canonical_json(status.to_document())
    with tempfile.NamedTemporaryFile(dir=target.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    return target


def _read(path: Path | str) -> dict[str, object]:
    target = _path(path)
    material = target.read_text(encoding="utf-8")
    try:
        decoded = json.loads(material)
    except json.JSONDecodeError as error:
        raise ValueError("scope expansion document is invalid") from error
    if canonical_json(decoded) != material:
        raise ValueError("scope expansion document is not canonical")
    return decoded


def read_scope_request(path: Path | str) -> ScopeExpansionRequest:
    return ScopeExpansionRequest.from_document(_read(path))


def read_scope_status(path: Path | str) -> ScopeExpansionStatus:
    return ScopeExpansionStatus.from_document(_read(path))


__all__ = [
    "SCOPE_EXPANSION_SCHEMA_VERSION",
    "ProgressEvent",
    "ScopeExpansionRequest",
    "ScopeExpansionStatus",
    "build_scope_expansion_request",
    "parse_scope_values",
    "read_scope_request",
    "read_scope_status",
    "write_scope_request",
    "write_scope_status",
]
