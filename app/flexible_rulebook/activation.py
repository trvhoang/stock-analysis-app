"""Immutable, operator-authored activation policy for fixed-cap discovery."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable, Sequence

import pytz

from .benchmark import ScalePolicy, validate_scale_policy
from .cap_benchmark import (
    DiscoveryCapBenchmarkReport,
    benchmark_record_from_cap_report,
    read_cap_benchmark_report,
    write_cap_benchmark_report,
)
from .cap_benchmark_runner import (
    discovery_runtime_contract_identity,
    production_cap_runtime,
)
from .contracts import canonical_json
from .storage import resolve_flexible_root


_HCM = pytz.timezone("Asia/Ho_Chi_Minh")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TICKER = re.compile(r"^[A-Z0-9._-]+$")
_POLICY_SCHEMA_VERSION = 1
_POLICY_KIND = "flexible_rulebook_activated_discovery_policy"
_POINTER_KIND = "flexible_rulebook_active_discovery_policy"
_DEFAULT_POINTER = Path("/data/flexible-benchmark/active-policy.json")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _ticker(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("ticker must be text")
    normalized = value.strip().upper()
    if not normalized or not _TICKER.fullmatch(normalized):
        raise ValueError("ticker must contain only persistence-safe characters")
    return normalized


def _unique(values: object, name: str, normalizer: Callable[[object], str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        result = tuple(normalizer(value) for value in values)
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    if not result or len(set(result)) != len(result):
        raise ValueError(f"{name} must be non-empty and unique")
    return result


def _contained(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def _benchmark_directory(value: Path | str, *, create: bool) -> Path:
    directory = Path(value)
    if not directory.is_absolute():
        raise ValueError("benchmark directory must be absolute")
    resolved = directory.resolve()
    live_root = resolve_flexible_root().resolve()
    if _contained(resolved, live_root):
        raise ValueError("benchmark directory cannot be inside the Flexible Rulebook evidence root")
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    if resolved.exists() and not resolved.is_dir():
        raise ValueError("benchmark directory must be a directory")
    return resolved


def _relative_report_path(digest: str) -> str:
    if not _DIGEST.fullmatch(digest):
        raise ValueError("report digest is invalid")
    return f"reports/{digest}.json"


def _relative_policy_path(digest: str) -> str:
    if not _DIGEST.fullmatch(digest):
        raise ValueError("policy digest is invalid")
    return f"policies/{digest}.json"


def _contained_relative_path(directory: Path, value: object, *, prefix: str, digest: str) -> Path:
    expected = f"{prefix}/{digest}.json"
    if not isinstance(value, str) or value != expected:
        raise ValueError("policy relative path is invalid")
    relpath = Path(value)
    if relpath.is_absolute() or ".." in relpath.parts or relpath.parts[:1] != (prefix,):
        raise ValueError("policy relative path escapes benchmark directory")
    target = (directory / relpath).resolve()
    if not _contained(target, directory):
        raise ValueError("policy relative path escapes benchmark directory")
    return target


def _canonical_identity(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be canonical JSON text")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{name} must be canonical JSON text") from error
    if canonical_json(decoded) != value:
        raise ValueError(f"{name} must be canonical JSON text")
    return value


def _activation_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("activated_at must be non-empty text")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("activated_at must be ISO datetime text") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("activated_at must be timezone-aware")
    return timestamp.astimezone(_HCM).isoformat()


@dataclass(frozen=True)
class ActivatedDiscoveryPolicy:
    """Canonical immutable authority for one reviewed direct-cap report."""

    report_digest: str
    benchmark_record_digest: str
    report_relpath: str
    allowed_tickers: tuple[str, ...]
    allowed_seeds: tuple[str, ...]
    runtime_contract_identity: str
    source_anchors: tuple[tuple[str, str], ...]
    benchmark_splits: tuple[tuple[str, str], ...]
    cap_attempts: int
    worker_count: int
    approved_by: str
    approval_note: str
    activated_at: str
    schema_version: int = _POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.report_digest, str) or not _DIGEST.fullmatch(self.report_digest):
            raise ValueError("report_digest is invalid")
        if (
            not isinstance(self.benchmark_record_digest, str)
            or not _DIGEST.fullmatch(self.benchmark_record_digest)
        ):
            raise ValueError("benchmark_record_digest is invalid")
        if self.report_relpath != _relative_report_path(self.report_digest):
            raise ValueError("policy relative path is invalid")
        object.__setattr__(self, "allowed_tickers", _unique(self.allowed_tickers, "allowed_tickers", _ticker))
        object.__setattr__(self, "allowed_seeds", _unique(self.allowed_seeds, "allowed_seeds", lambda value: _text(value, "seed")))
        object.__setattr__(
            self,
            "runtime_contract_identity",
            _canonical_identity(self.runtime_contract_identity, "runtime_contract_identity"),
        )
        for name in ("source_anchors", "benchmark_splits"):
            try:
                entries = tuple(getattr(self, name))
            except TypeError as error:
                raise ValueError(f"{name} must be a sequence") from error
            if (
                len(entries) != len(self.allowed_tickers)
                or any(
                    not isinstance(entry, tuple)
                    or len(entry) != 2
                    or entry[0] not in self.allowed_tickers
                    for entry in entries
                )
                or tuple(entry[0] for entry in entries) != self.allowed_tickers
            ):
                raise ValueError(f"{name} must exactly cover allowed tickers in order")
            object.__setattr__(
                self,
                name,
                tuple((ticker, _canonical_identity(identity, name)) for ticker, identity in entries),
            )
        if isinstance(self.cap_attempts, bool) or not isinstance(self.cap_attempts, int) or self.cap_attempts <= 0:
            raise ValueError("cap_attempts must be a positive integer")
        if self.worker_count != 1:
            raise ValueError("activated discovery policy requires exactly one worker")
        object.__setattr__(self, "approved_by", _text(self.approved_by, "approved_by"))
        object.__setattr__(self, "approval_note", _text(self.approval_note, "approval_note"))
        object.__setattr__(self, "activated_at", _activation_timestamp(self.activated_at))
        if self.schema_version != _POLICY_SCHEMA_VERSION:
            raise ValueError("activation policy schema version is unsupported")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "report_digest": self.report_digest,
            "benchmark_record_digest": self.benchmark_record_digest,
            "report_relpath": self.report_relpath,
            "allowed_tickers": list(self.allowed_tickers),
            "allowed_seeds": list(self.allowed_seeds),
            "runtime_contract_identity": self.runtime_contract_identity,
            "source_anchors": [
                {"ticker": ticker, "source_identity": identity}
                for ticker, identity in self.source_anchors
            ],
            "benchmark_splits": [
                {"ticker": ticker, "split_identity": identity}
                for ticker, identity in self.benchmark_splits
            ],
            "cap_attempts": self.cap_attempts,
            "worker_count": self.worker_count,
            "approved_by": self.approved_by,
            "approval_note": self.approval_note,
            "activated_at": self.activated_at,
        }

    @property
    def policy_digest(self) -> str:
        return hashlib.sha256(canonical_json(self.to_payload()).encode("utf-8")).hexdigest()

    def to_document(self) -> dict[str, object]:
        return {
            "kind": _POLICY_KIND,
            "digest": self.policy_digest,
            "payload": self.to_payload(),
        }

    @classmethod
    def from_payload(cls, value: object) -> "ActivatedDiscoveryPolicy":
        if not isinstance(value, dict):
            raise ValueError("activation policy payload must be a JSON object")
        required = {
            "schema_version",
            "report_digest",
            "benchmark_record_digest",
            "report_relpath",
            "allowed_tickers",
            "allowed_seeds",
            "runtime_contract_identity",
            "source_anchors",
            "benchmark_splits",
            "cap_attempts",
            "worker_count",
            "approved_by",
            "approval_note",
            "activated_at",
        }
        if (
            set(value) != required
            or not isinstance(value["allowed_tickers"], list)
            or not isinstance(value["allowed_seeds"], list)
            or not isinstance(value["source_anchors"], list)
            or not isinstance(value["benchmark_splits"], list)
        ):
            raise ValueError("activation policy payload schema is invalid")

        def entries(values: list[object], key: str) -> tuple[tuple[object, object], ...]:
            if any(not isinstance(item, dict) or set(item) != {"ticker", key} for item in values):
                raise ValueError("activation policy anchor schema is invalid")
            return tuple((item["ticker"], item[key]) for item in values)

        return cls(
            schema_version=value["schema_version"],
            report_digest=value["report_digest"],
            benchmark_record_digest=value["benchmark_record_digest"],
            report_relpath=value["report_relpath"],
            allowed_tickers=tuple(value["allowed_tickers"]),
            allowed_seeds=tuple(value["allowed_seeds"]),
            runtime_contract_identity=value["runtime_contract_identity"],
            source_anchors=entries(value["source_anchors"], "source_identity"),
            benchmark_splits=entries(value["benchmark_splits"], "split_identity"),
            cap_attempts=value["cap_attempts"],
            worker_count=value["worker_count"],
            approved_by=value["approved_by"],
            approval_note=value["approval_note"],
            activated_at=value["activated_at"],
        )


def _atomic_write(path: Path, material: str) -> None:
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


def _write_immutable(path: Path, material: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != material:
            raise ValueError("immutable activation document already differs")
        return path
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
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != material:
                raise ValueError("immutable activation document already differs")
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _report_anchor_maps(
    report: DiscoveryCapBenchmarkReport,
    allowed_tickers: tuple[str, ...],
    allowed_seeds: tuple[str, ...],
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    source_anchors: list[tuple[str, str]] = []
    benchmark_splits: list[tuple[str, str]] = []
    for ticker in allowed_tickers:
        completed = tuple(
            sample
            for sample in report.samples
            if (
                sample.ticker == ticker
                and sample.seed in allowed_seeds
                and sample.is_complete_cold_window
            )
        )
        if not completed:
            raise ValueError("activation policy requires a completed historical anchor")
        source_values = {sample.source_identity for sample in completed}
        split_values = {sample.split_identity for sample in completed}
        if None in source_values or len(source_values) != 1:
            raise ValueError("activation policy requires one stable historical anchor per ticker")
        if None in split_values or len(split_values) != 1:
            raise ValueError("activation policy requires one stable benchmark split per ticker")
        source_anchors.append((ticker, next(iter(source_values))))
        benchmark_splits.append((ticker, next(iter(split_values))))
    return tuple(source_anchors), tuple(benchmark_splits)


def _current_runtime_identity() -> str:
    return discovery_runtime_contract_identity(production_cap_runtime())


def _validate_policy_against_report(
    policy: ActivatedDiscoveryPolicy,
    report: DiscoveryCapBenchmarkReport,
) -> None:
    if report.digest != policy.report_digest:
        raise ValueError("activation policy report digest does not match report")
    if report.runtime_contract_identity != policy.runtime_contract_identity:
        raise ValueError("activation policy runtime contract does not match report")
    if policy.runtime_contract_identity != _current_runtime_identity():
        raise ValueError("activation policy runtime contract does not match the current implementation")
    if not set(policy.allowed_tickers).issubset(report.tickers):
        raise ValueError("activation policy ticker scope is not in the cap report")
    if not set(policy.allowed_seeds).issubset(report.seeds):
        raise ValueError("activation policy seed scope is not in the cap report")
    if policy.cap_attempts != report.cap_attempts:
        raise ValueError("activation policy cap does not match cap report")
    if policy.worker_count != 1:
        raise ValueError("activation policy requires exactly one worker")
    record = benchmark_record_from_cap_report(report)
    if record.digest != policy.benchmark_record_digest:
        raise ValueError("activation policy benchmark record digest does not match cap report")
    validate_scale_policy(
        ScalePolicy(
            max_discovery_attempt_count=policy.cap_attempts,
            worker_count=policy.worker_count,
            benchmark_report_hash=report.digest,
        ),
        record,
    )
    expected_sources, expected_splits = _report_anchor_maps(
        report,
        policy.allowed_tickers,
        policy.allowed_seeds,
    )
    if policy.source_anchors != expected_sources or policy.benchmark_splits != expected_splits:
        raise ValueError("activation policy historical anchors do not match cap report")


def _read_policy_document(path: Path) -> ActivatedDiscoveryPolicy:
    try:
        material = path.read_text(encoding="utf-8")
        document = json.loads(material)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("activation policy is unreadable") from error
    if canonical_json(document) != material or not isinstance(document, dict):
        raise ValueError("activation policy must use canonical JSON")
    if set(document) != {"kind", "digest", "payload"} or document["kind"] != _POLICY_KIND:
        raise ValueError("activation policy document schema is invalid")
    digest = document["digest"]
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ValueError("activation policy digest is invalid")
    payload = document["payload"]
    if not isinstance(payload, dict) or hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest() != digest:
        raise ValueError("activation policy digest does not match canonical payload")
    policy = ActivatedDiscoveryPolicy.from_payload(payload)
    if policy.policy_digest != digest:
        raise ValueError("activation policy digest does not match validated policy")
    return policy


def load_policy_by_digest(directory: Path, policy_digest: str) -> ActivatedDiscoveryPolicy:
    """Load one immutable policy and fail closed on report or contract drift."""

    root = _benchmark_directory(directory, create=False)
    if not isinstance(policy_digest, str) or not _DIGEST.fullmatch(policy_digest):
        raise ValueError("policy digest is invalid")
    policy_path = _contained_relative_path(
        root,
        _relative_policy_path(policy_digest),
        prefix="policies",
        digest=policy_digest,
    )
    policy = _read_policy_document(policy_path)
    if policy.policy_digest != policy_digest:
        raise ValueError("policy document digest does not match requested digest")
    report_path = _contained_relative_path(
        root,
        policy.report_relpath,
        prefix="reports",
        digest=policy.report_digest,
    )
    report = read_cap_benchmark_report(report_path)
    _validate_policy_against_report(policy, report)
    return policy


def _active_pointer_path(path: Path | None, *, create: bool) -> Path:
    raw = Path(os.getenv("FLEXIBLE_BENCHMARK_ACTIVE_POLICY_PATH", str(_DEFAULT_POINTER))) if path is None else Path(path)
    if not raw.is_absolute():
        raise ValueError("active policy pointer path must be absolute")
    resolved = raw.resolve()
    live_root = resolve_flexible_root().resolve()
    if _contained(resolved, live_root):
        raise ValueError("active policy pointer cannot be inside the Flexible Rulebook evidence root")
    if create:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists() and resolved.is_dir():
        raise ValueError("active policy pointer must name a file")
    return resolved


def active_policy_directory(path: Path | None = None) -> Path:
    """Return the immutable-policy directory selected by the configured pointer."""

    return _active_pointer_path(path, create=False).parent


def load_active_policy(path: Path | None = None) -> tuple[ActivatedDiscoveryPolicy | None, str]:
    """Return the current valid authority, otherwise an explicit safe reason."""

    try:
        pointer_path = _active_pointer_path(path, create=False)
        material = pointer_path.read_text(encoding="utf-8")
        pointer = json.loads(material)
        if (
            canonical_json(pointer) != material
            or not isinstance(pointer, dict)
            or set(pointer) != {"kind", "policy_relpath", "policy_digest"}
            or pointer["kind"] != _POINTER_KIND
            or not isinstance(pointer["policy_digest"], str)
            or not _DIGEST.fullmatch(pointer["policy_digest"])
        ):
            raise ValueError("active policy pointer is invalid")
        directory = pointer_path.parent.resolve()
        policy_path = _contained_relative_path(
            directory,
            pointer["policy_relpath"],
            prefix="policies",
            digest=pointer["policy_digest"],
        )
        policy = load_policy_by_digest(directory, pointer["policy_digest"])
        if policy_path != (directory / _relative_policy_path(policy.policy_digest)).resolve():
            raise ValueError("active policy pointer path does not match policy digest")
        return policy, "active"
    except (OSError, ValueError) as error:
        return None, str(error)


def activate_cap_report(
    report_path: Path,
    benchmark_directory: Path,
    *,
    allowed_tickers: Sequence[str],
    allowed_seeds: Sequence[str],
    approved_by: str,
    approval_note: str,
) -> ActivatedDiscoveryPolicy:
    """Review one eligible direct-cap report and atomically activate its policy."""

    root = _benchmark_directory(benchmark_directory, create=True)
    source_path = Path(report_path)
    if not source_path.is_absolute():
        raise ValueError("cap report path must be absolute")
    if _contained(source_path.resolve(), resolve_flexible_root().resolve()):
        raise ValueError("cap report path cannot be inside the Flexible Rulebook evidence root")
    report = read_cap_benchmark_report(source_path.resolve())
    allowed_ticker_values = _unique(allowed_tickers, "allowed_tickers", _ticker)
    allowed_seed_values = _unique(allowed_seeds, "allowed_seeds", lambda value: _text(value, "seed"))
    if not set(allowed_ticker_values).issubset(report.tickers):
        raise ValueError("allowed tickers must be within cap report scope")
    if not set(allowed_seed_values).issubset(report.seeds):
        raise ValueError("allowed seeds must be within cap report scope")
    runtime_identity = _current_runtime_identity()
    if report.runtime_contract_identity != runtime_identity:
        raise ValueError("cap report runtime contract does not match the current implementation")
    record = benchmark_record_from_cap_report(report)
    source_anchors, benchmark_splits = _report_anchor_maps(
        report,
        allowed_ticker_values,
        allowed_seed_values,
    )
    policy = ActivatedDiscoveryPolicy(
        report_digest=report.digest,
        benchmark_record_digest=record.digest,
        report_relpath=_relative_report_path(report.digest),
        allowed_tickers=allowed_ticker_values,
        allowed_seeds=allowed_seed_values,
        runtime_contract_identity=report.runtime_contract_identity,
        source_anchors=source_anchors,
        benchmark_splits=benchmark_splits,
        cap_attempts=report.cap_attempts,
        worker_count=1,
        approved_by=approved_by,
        approval_note=approval_note,
        activated_at=datetime.now(_HCM).isoformat(),
    )
    _validate_policy_against_report(policy, report)
    report_target = _contained_relative_path(
        root,
        policy.report_relpath,
        prefix="reports",
        digest=report.digest,
    )
    write_cap_benchmark_report(report_target, report)
    policy_target = _contained_relative_path(
        root,
        _relative_policy_path(policy.policy_digest),
        prefix="policies",
        digest=policy.policy_digest,
    )
    _write_immutable(policy_target, canonical_json(policy.to_document()))
    pointer_target = _active_pointer_path(root / "active-policy.json", create=True)
    _atomic_write(
        pointer_target,
        canonical_json(
            {
                "kind": _POINTER_KIND,
                "policy_relpath": _relative_policy_path(policy.policy_digest),
                "policy_digest": policy.policy_digest,
            }
        ),
    )
    return policy


def main(argv: list[str] | None = None) -> int:
    """Activate one reviewed cap report; benchmark execution stays separate."""

    parser = argparse.ArgumentParser(
        description="Create an immutable Flexible Rulebook discovery activation policy."
    )
    parser.add_argument("--report", required=True, help="Absolute cap report path")
    parser.add_argument("--benchmark-directory", required=True, help="Absolute policy directory")
    parser.add_argument("--ticker", action="append", required=True, help="Allowed ticker; repeatable")
    parser.add_argument("--seed", action="append", required=True, help="Allowed seed; repeatable")
    parser.add_argument("--approved-by", required=True, help="Operator identity")
    parser.add_argument("--approval-note", required=True, help="Independent review note")
    arguments = parser.parse_args(argv)
    try:
        policy = activate_cap_report(
            Path(arguments.report),
            Path(arguments.benchmark_directory),
            allowed_tickers=arguments.ticker,
            allowed_seeds=arguments.seed,
            approved_by=arguments.approved_by,
            approval_note=arguments.approval_note,
        )
    except ValueError as error:
        parser.error(str(error))
    print(f"Activated discovery policy: {policy.policy_digest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "ActivatedDiscoveryPolicy",
    "active_policy_directory",
    "activate_cap_report",
    "load_active_policy",
    "load_policy_by_digest",
    "main",
]
