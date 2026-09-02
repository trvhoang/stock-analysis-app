"""Measured scale and acceleration gates for Flexible Rulebook campaigns."""

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
from typing import Callable, Literal, Mapping, Sequence

from .contracts import canonical_json


_HASH = re.compile(r"^[0-9a-f]{64}$")
_TICKER = re.compile(r"^[A-Z0-9._-]+$")
_FEATURE_BUILD_HASH = re.compile(r"^frbc_[0-9a-f]{64}$")
_RECEIPT_ID = re.compile(r"^frpr_[0-9a-f]{64}$")
ADMISSION_SECONDS = 16_200
TERMINAL_SECONDS = 17_700
TERMINAL_RESERVE_SECONDS = TERMINAL_SECONDS - ADMISSION_SECONDS
PRODUCTION_BENCHMARK_SCHEMA_VERSION = 1
MIN_COLD_SAMPLE_COUNT = 100


def _hash(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _counts(value: Sequence[int], name: str) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be integer measurements")
    result = tuple(value)
    if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in result):
        raise ValueError(f"{name} must contain positive integers")
    return result


def _seconds(value: float | None, name: str, *, allow_zero: bool = False) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or (number < 0.0 if allow_zero else number <= 0.0):
        raise ValueError(f"{name} must be a finite positive duration")
    return number


def _ticker(value: object, name: str = "ticker") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    normalized = value.strip().upper()
    if not normalized or not _TICKER.fullmatch(normalized):
        raise ValueError(f"{name} must contain only persistence-safe characters")
    return normalized


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


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


def _p99(values: Sequence[float]) -> float:
    """Return the deterministic NumPy-linear-equivalent 99th percentile."""

    if not values:
        raise ValueError("p99 requires at least one sample")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * 0.99
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


@dataclass(frozen=True)
class BenchmarkRecord:
    """Immutable measurements that may justify a non-default scale policy."""

    benchmark_report_hash: str
    scope: Literal["current_scan", "discovery", "combined"] = "combined"
    completed: bool = False
    measured_current_scan_ticker_counts: tuple[int, ...] = ()
    measured_discovery_attempt_caps: tuple[int, ...] = ()
    worker_counts: tuple[int, ...] = ()
    maximal_slot_sample_count: int = 0
    direct_cap_window_attempt_count: int | None = None
    cold_p99_preflight_seconds: float | None = None
    cold_p99_cap_window_seconds: float | None = None
    cold_p99_training_seconds: float | None = None
    cold_p99_test_seconds: float | None = None
    cold_p99_selection_seconds: float | None = None
    cold_p99_write_seconds: float | None = None
    cold_p99_maximal_slot_seconds: float | None = None
    cold_p99_total_seconds: float | None = None
    reference_fast_parity: bool = False
    fast_executor_improvement: float = 0.0
    append_prefix_parity: bool = False
    append_full_rebuild_parity: bool = False
    append_extension_improvement: float = 0.0

    def __post_init__(self) -> None:
        _hash(self.benchmark_report_hash, "benchmark_report_hash")
        if self.scope not in {"current_scan", "discovery", "combined"}:
            raise ValueError("benchmark scope is invalid")
        if not isinstance(self.completed, bool):
            raise ValueError("benchmark completed must be boolean")
        object.__setattr__(self, "measured_current_scan_ticker_counts", _counts(self.measured_current_scan_ticker_counts, "current-scan measurements"))
        object.__setattr__(self, "measured_discovery_attempt_caps", _counts(self.measured_discovery_attempt_caps, "discovery measurements"))
        object.__setattr__(self, "worker_counts", _counts(self.worker_counts, "worker measurements"))
        if isinstance(self.maximal_slot_sample_count, bool) or not isinstance(self.maximal_slot_sample_count, int) or self.maximal_slot_sample_count < 0:
            raise ValueError("maximal_slot_sample_count must be a non-negative integer")
        if self.direct_cap_window_attempt_count is not None:
            object.__setattr__(
                self,
                "direct_cap_window_attempt_count",
                _counts(
                    (self.direct_cap_window_attempt_count,),
                    "direct cap-window attempt count",
                )[0],
            )
        for name in (
            "cold_p99_preflight_seconds", "cold_p99_cap_window_seconds",
            "cold_p99_training_seconds", "cold_p99_test_seconds",
            "cold_p99_selection_seconds", "cold_p99_write_seconds", "cold_p99_maximal_slot_seconds",
            "cold_p99_total_seconds",
        ):
            object.__setattr__(self, name, _seconds(getattr(self, name), name, allow_zero=name == "cold_p99_preflight_seconds"))
        for name in ("fast_executor_improvement", "append_extension_improvement"):
            number = float(getattr(self, name))
            if not math.isfinite(number) or number < 0.0:
                raise ValueError(f"{name} must be a finite non-negative number")
            object.__setattr__(self, name, number)
        for name in ("reference_fast_parity", "append_prefix_parity", "append_full_rebuild_parity"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")

    def to_identity_dict(self) -> dict[str, object]:
        """Return every immutable measurement field in canonical-digest order."""

        return {
            "benchmark_report_hash": self.benchmark_report_hash,
            "scope": self.scope,
            "completed": self.completed,
            "measured_current_scan_ticker_counts": self.measured_current_scan_ticker_counts,
            "measured_discovery_attempt_caps": self.measured_discovery_attempt_caps,
            "worker_counts": self.worker_counts,
            "maximal_slot_sample_count": self.maximal_slot_sample_count,
            "direct_cap_window_attempt_count": self.direct_cap_window_attempt_count,
            "cold_p99_preflight_seconds": self.cold_p99_preflight_seconds,
            "cold_p99_cap_window_seconds": self.cold_p99_cap_window_seconds,
            "cold_p99_training_seconds": self.cold_p99_training_seconds,
            "cold_p99_test_seconds": self.cold_p99_test_seconds,
            "cold_p99_selection_seconds": self.cold_p99_selection_seconds,
            "cold_p99_write_seconds": self.cold_p99_write_seconds,
            "cold_p99_maximal_slot_seconds": self.cold_p99_maximal_slot_seconds,
            "cold_p99_total_seconds": self.cold_p99_total_seconds,
            "reference_fast_parity": self.reference_fast_parity,
            "fast_executor_improvement": self.fast_executor_improvement,
            "append_prefix_parity": self.append_prefix_parity,
            "append_full_rebuild_parity": self.append_full_rebuild_parity,
            "append_extension_improvement": self.append_extension_improvement,
        }

    @property
    def digest(self) -> str:
        """Return a stable identity digest for report-bound policy activation."""

        return hashlib.sha256(
            canonical_json(self.to_identity_dict()).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class ScalePolicy:
    """Operational caps; defaults intentionally keep the phase-one gate closed."""

    max_current_scan_tickers: int = 15
    max_discovery_attempt_count: int = 0
    worker_count: int = 1
    benchmark_report_hash: str = "0" * 64
    enable_fast_executor: bool = False
    enable_append_extension: bool = False

    def __post_init__(self) -> None:
        for name in ("max_current_scan_tickers", "worker_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if isinstance(self.max_discovery_attempt_count, bool) or not isinstance(self.max_discovery_attempt_count, int) or self.max_discovery_attempt_count < 0:
            raise ValueError("max_discovery_attempt_count must be a non-negative integer")
        _hash(self.benchmark_report_hash, "benchmark_report_hash")
        if not isinstance(self.enable_fast_executor, bool) or not isinstance(self.enable_append_extension, bool):
            raise ValueError("acceleration flags must be boolean")


def _matching_record(policy: ScalePolicy, record: BenchmarkRecord | None) -> BenchmarkRecord:
    if record is None:
        raise ValueError("completed benchmark record is required")
    if not record.completed:
        raise ValueError("benchmark record must be completed")
    if record.benchmark_report_hash != policy.benchmark_report_hash:
        raise ValueError("benchmark report hash does not match policy")
    return record


def _validate_current_scale(policy: ScalePolicy, record: BenchmarkRecord | None) -> None:
    if policy.max_current_scan_tickers <= 15:
        return
    if record is None:
        raise ValueError("current-scan group size is limited to 15 without a completed benchmark")
    measured = _matching_record(policy, record)
    accepted_levels = (20, 100, 200)
    if measured.scope not in {"current_scan", "combined"} or not any(level >= policy.max_current_scan_tickers and level in measured.measured_current_scan_ticker_counts for level in accepted_levels):
        raise ValueError("current-scan scale requires a completed 20/100/200 ticker measurement")


def _validate_discovery_scale(policy: ScalePolicy, record: BenchmarkRecord | None) -> None:
    cap = policy.max_discovery_attempt_count
    if cap == 0:
        return
    measured = _matching_record(policy, record)
    direct_cap = measured.direct_cap_window_attempt_count
    if direct_cap is not None:
        if measured.scope != "discovery":
            raise ValueError("discovery scale requires a separate discovery benchmark record")
        if measured.worker_counts != (1,):
            raise ValueError("discovery direct-cap proof requires exactly one worker")
        if measured.measured_discovery_attempt_caps != (direct_cap,):
            raise ValueError("direct cap-window record must expose one exact measured cap")
        if cap != direct_cap:
            raise ValueError("discovery policy cap must be exactly equal to the measured direct cap")
        if measured.maximal_slot_sample_count < 100:
            raise ValueError("discovery direct-cap proof requires at least 100 completed cold windows")
        preflight = measured.cold_p99_preflight_seconds
        window = measured.cold_p99_cap_window_seconds
        total = measured.cold_p99_total_seconds
        if preflight is None or window is None or total is None:
            raise ValueError("discovery direct cap requires cold p99 window proof")
        if float(preflight) + float(window) > ADMISSION_SECONDS:
            raise ValueError("discovery direct-cap p99 cannot finish before admission deadline")
        if float(total) > TERMINAL_SECONDS:
            raise ValueError("discovery direct-cap p99 cannot finish before terminal deadline")
        if float(total) < float(preflight) + float(window):
            raise ValueError("discovery direct-cap total is below measured preflight plus cap window")
        return
    if measured.maximal_slot_sample_count < 100:
        raise ValueError("discovery p99 proof requires at least 100 maximal-slot samples")
    durations = {
        "preflight": measured.cold_p99_preflight_seconds,
        "training": measured.cold_p99_training_seconds,
        "test": measured.cold_p99_test_seconds,
        "selection": measured.cold_p99_selection_seconds,
        "write": measured.cold_p99_write_seconds,
        "maximal": measured.cold_p99_maximal_slot_seconds,
        "total": measured.cold_p99_total_seconds,
    }
    if any(value is None for value in durations.values()):
        raise ValueError("discovery cap requires cold p99 maximal-slot proof")
    preflight = float(durations["preflight"])
    maximal = float(durations["maximal"])
    components = tuple(float(durations[name]) for name in ("training", "test", "selection", "write"))
    if maximal < max(components):
        raise ValueError("discovery cap must use maximal train/test/selection/write slot")
    available = ADMISSION_SECONDS - preflight
    if available <= 0.0 or preflight + maximal > ADMISSION_SECONDS or preflight + maximal > TERMINAL_SECONDS:
        raise ValueError("discovery p99 cannot finish before admission/terminal deadline")
    if float(durations["total"]) < preflight + maximal:
        raise ValueError("discovery p99 total duration is below measured preflight plus maximal slot")
    derived_cap = math.floor(available / maximal)
    if cap > derived_cap:
        raise ValueError("discovery attempt cap exceeds deadline-safe maximal-slot cap")
    if (
        not measured.measured_discovery_attempt_caps
        or max(measured.measured_discovery_attempt_caps) < cap
    ):
        raise ValueError("discovery attempt cap lacks a matching measured record")
    if measured.scope != "discovery":
        raise ValueError("discovery scale requires a separate discovery benchmark record")


def _validate_acceleration(policy: ScalePolicy, record: BenchmarkRecord | None) -> None:
    if not policy.enable_fast_executor and not policy.enable_append_extension:
        return
    measured = _matching_record(policy, record)
    if policy.enable_fast_executor:
        if not measured.reference_fast_parity:
            raise ValueError("fast executor requires reference parity")
        if measured.fast_executor_improvement <= 0.0:
            raise ValueError("fast executor requires measured improvement")
    if policy.enable_append_extension:
        if not measured.append_prefix_parity or not measured.append_full_rebuild_parity:
            raise ValueError("append extension requires prefix and full-rebuild parity")
        if measured.append_extension_improvement <= 0.0:
            raise ValueError("append extension requires measured improvement")


def validate_scale_policy(policy: ScalePolicy, record: BenchmarkRecord | None) -> None:
    """Reject every unmeasured scale/acceleration expansion."""

    if not isinstance(policy, ScalePolicy):
        raise ValueError("policy must be ScalePolicy")
    if record is not None and not isinstance(record, BenchmarkRecord):
        raise ValueError("record must be BenchmarkRecord or None")
    _validate_current_scale(policy, record)
    _validate_discovery_scale(policy, record)
    if policy.worker_count > 1:
        measured = _matching_record(policy, record)
        if policy.worker_count not in measured.worker_counts:
            raise ValueError("worker count lacks a matching completed benchmark measurement")
    _validate_acceleration(policy, record)


def safe_default_scale_policy() -> ScalePolicy:
    """Return the intentionally conservative phase-one policy."""

    return ScalePolicy()


_CAMPAIGN_STATES = frozenset({
    "queued", "running", "cancelling", "cancelled", "blocked", "interrupted",
    "completed", "completed_with_errors", "failed",
})
_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+$")


def _digest_payload(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _optional_bytes(value: object, name: str) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value, name)


def decode_canonical_scalars(value: object) -> object:
    """Decode only scalar wrappers which ``canonical_json`` writes itself."""

    if isinstance(value, list):
        return [decode_canonical_scalars(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$float"} and isinstance(value["$float"], str):
        number = float(value["$float"])
        if not math.isfinite(number):
            raise ValueError("report contains a non-finite float")
        return number
    return {key: decode_canonical_scalars(item) for key, item in value.items()}


def _require_mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be a JSON object")
    return value


@dataclass(frozen=True)
class BenchmarkSample:
    """One isolated cold or warm benchmark sample, including safe failure truth."""

    ticker: str
    seed: str
    global_slot: int
    canonical_index: int
    mode: Literal["cold", "warm"]
    source_fingerprint: str | None
    preflight_seconds: float | None
    training_seconds: float | None
    test_seconds: float | None
    selection_seconds: float | None
    write_seconds: float | None
    maximal_slot_seconds: float | None
    terminal_state: str
    safe_error_code: str | None
    peak_rss_bytes: int | None
    peak_pool_checkouts: int | None
    cache_bytes: int
    artifact_bytes: int
    frontier_stratum: str = "canonical"
    reached_maximal_path: bool = True
    feature_receipt_id: str | None = None
    split_identity: str = "{}"

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _ticker(self.ticker))
        object.__setattr__(self, "seed", _text(self.seed, "seed"))
        object.__setattr__(self, "global_slot", _non_negative_int(self.global_slot, "global_slot"))
        object.__setattr__(self, "canonical_index", _non_negative_int(self.canonical_index, "canonical_index"))
        if self.mode not in {"cold", "warm"}:
            raise ValueError("mode must be cold or warm")
        if self.source_fingerprint is not None:
            _hash(self.source_fingerprint, "source_fingerprint")
        object.__setattr__(self, "frontier_stratum", _text(self.frontier_stratum, "frontier_stratum"))
        object.__setattr__(self, "split_identity", _canonical_identity(self.split_identity, "split_identity"))
        if not isinstance(self.reached_maximal_path, bool):
            raise ValueError("reached_maximal_path must be boolean")
        if self.terminal_state not in _CAMPAIGN_STATES:
            raise ValueError("terminal_state is unsupported")
        if self.safe_error_code is not None:
            code = _text(self.safe_error_code, "safe_error_code")
            if not _SAFE_ERROR_CODE.fullmatch(code):
                raise ValueError("safe_error_code is not persistence-safe")
            object.__setattr__(self, "safe_error_code", code)
        if self.terminal_state == "completed" and self.safe_error_code is not None:
            raise ValueError("completed sample cannot contain a safe error code")
        for name in (
            "preflight_seconds", "training_seconds", "test_seconds", "selection_seconds",
            "write_seconds", "maximal_slot_seconds",
        ):
            object.__setattr__(self, name, _seconds(getattr(self, name), name, allow_zero=True))
        components = tuple(
            getattr(self, name) for name in (
                "training_seconds", "test_seconds", "selection_seconds", "write_seconds",
            )
        )
        if self.maximal_slot_seconds is not None and all(item is not None for item in components):
            if self.maximal_slot_seconds < sum(float(item) for item in components):
                raise ValueError("maximal_slot_seconds is below measured phase durations")
        if self.terminal_state == "completed" and (
            self.preflight_seconds is None
            or self.maximal_slot_seconds is None
            or any(item is None for item in components)
        ):
            raise ValueError("completed sample must retain every measured phase duration")
        object.__setattr__(self, "peak_rss_bytes", _optional_bytes(self.peak_rss_bytes, "peak_rss_bytes"))
        object.__setattr__(
            self,
            "peak_pool_checkouts",
            _optional_bytes(self.peak_pool_checkouts, "peak_pool_checkouts"),
        )
        object.__setattr__(self, "cache_bytes", _non_negative_int(self.cache_bytes, "cache_bytes"))
        object.__setattr__(self, "artifact_bytes", _non_negative_int(self.artifact_bytes, "artifact_bytes"))
        if self.feature_receipt_id is not None:
            receipt = _text(self.feature_receipt_id, "feature_receipt_id")
            if not _RECEIPT_ID.fullmatch(receipt):
                raise ValueError("feature_receipt_id is invalid")
            object.__setattr__(self, "feature_receipt_id", receipt)

    @property
    def identity(self) -> tuple[str, str, str, int]:
        """Return the unique scheduling identity of this measured sample."""

        return (self.ticker, self.seed, self.mode, self.global_slot)

    @property
    def is_complete(self) -> bool:
        return (
            self.terminal_state == "completed"
            and self.safe_error_code is None
            and self.reached_maximal_path
            and self.source_fingerprint is not None
            and self.preflight_seconds is not None
            and self.maximal_slot_seconds is not None
            and all(
                getattr(self, name) is not None
                for name in (
                    "training_seconds", "test_seconds", "selection_seconds", "write_seconds",
                )
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "seed": self.seed,
            "global_slot": self.global_slot,
            "canonical_index": self.canonical_index,
            "frontier_stratum": self.frontier_stratum,
            "split_identity": self.split_identity,
            "mode": self.mode,
            "source_fingerprint": self.source_fingerprint,
            "feature_receipt_id": self.feature_receipt_id,
            "preflight_seconds": self.preflight_seconds,
            "training_seconds": self.training_seconds,
            "test_seconds": self.test_seconds,
            "selection_seconds": self.selection_seconds,
            "write_seconds": self.write_seconds,
            "maximal_slot_seconds": self.maximal_slot_seconds,
            "terminal_state": self.terminal_state,
            "safe_error_code": self.safe_error_code,
            "reached_maximal_path": self.reached_maximal_path,
            # This is the fresh benchmark-child process high-water mark, not
            # a per-phase allocation and not a container-wide value.
            "peak_child_rss_bytes": self.peak_rss_bytes,
            # This is client-side SQLAlchemy checkout observation only.
            "peak_client_pool_checkouts": self.peak_pool_checkouts,
            "cache_bytes": self.cache_bytes,
            "artifact_bytes": self.artifact_bytes,
        }

    @classmethod
    def from_dict(cls, value: object) -> "BenchmarkSample":
        payload = _require_mapping(value, "benchmark sample")
        required = {
            "ticker", "seed", "global_slot", "canonical_index", "frontier_stratum", "split_identity", "mode",
            "source_fingerprint", "feature_receipt_id", "preflight_seconds", "training_seconds",
            "test_seconds", "selection_seconds", "write_seconds", "maximal_slot_seconds",
            "terminal_state", "safe_error_code", "reached_maximal_path", "peak_child_rss_bytes",
            "peak_client_pool_checkouts", "cache_bytes", "artifact_bytes",
        }
        if set(payload) != required:
            raise ValueError("benchmark sample schema is invalid")
        return cls(
            ticker=payload["ticker"], seed=payload["seed"], global_slot=payload["global_slot"],
            canonical_index=payload["canonical_index"], frontier_stratum=payload["frontier_stratum"], split_identity=payload["split_identity"],
            mode=payload["mode"], source_fingerprint=payload["source_fingerprint"],
            feature_receipt_id=payload["feature_receipt_id"],
            preflight_seconds=payload["preflight_seconds"], training_seconds=payload["training_seconds"],
            test_seconds=payload["test_seconds"], selection_seconds=payload["selection_seconds"],
            write_seconds=payload["write_seconds"], maximal_slot_seconds=payload["maximal_slot_seconds"],
            terminal_state=payload["terminal_state"], safe_error_code=payload["safe_error_code"],
            reached_maximal_path=payload["reached_maximal_path"],
            peak_rss_bytes=payload["peak_child_rss_bytes"],
            peak_pool_checkouts=payload["peak_client_pool_checkouts"], cache_bytes=payload["cache_bytes"],
            artifact_bytes=payload["artifact_bytes"],
        )


def _unique_texts(
    value: object,
    name: str,
    *,
    normalizer: Callable[[object], str],
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        items = tuple(normalizer(item) for item in value)  # type: ignore[arg-type]
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    if not items or len(set(items)) != len(items):
        raise ValueError(f"{name} must be non-empty and unique")
    return items


@dataclass(frozen=True)
class ProductionBenchmarkReport:
    """Canonical, immutable measurement evidence; it cannot authorize policy by itself."""

    as_of: date
    tickers: tuple[str, ...]
    seeds: tuple[str, ...]
    catalog_hash: str
    feature_build_contract_hash: str
    candidate_space_hash: str
    split_identity: str
    execution_contract_identity: str
    samples: tuple[BenchmarkSample, ...]
    schema_version: int = PRODUCTION_BENCHMARK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.as_of) is not date:
            raise ValueError("as_of must be a date without a time")
        object.__setattr__(self, "tickers", _unique_texts(self.tickers, "tickers", normalizer=_ticker))
        object.__setattr__(self, "seeds", _unique_texts(self.seeds, "seeds", normalizer=lambda item: _text(item, "seed")))
        _hash(self.catalog_hash, "catalog_hash")
        if not isinstance(self.feature_build_contract_hash, str) or not _FEATURE_BUILD_HASH.fullmatch(self.feature_build_contract_hash):
            raise ValueError("feature_build_contract_hash is invalid")
        _hash(self.candidate_space_hash, "candidate_space_hash")
        object.__setattr__(self, "split_identity", _canonical_identity(self.split_identity, "split_identity"))
        object.__setattr__(
            self,
            "execution_contract_identity",
            _canonical_identity(self.execution_contract_identity, "execution_contract_identity"),
        )
        if self.schema_version != PRODUCTION_BENCHMARK_SCHEMA_VERSION:
            raise ValueError("production benchmark schema version is unsupported")
        if isinstance(self.samples, (str, bytes)):
            raise ValueError("samples must be a sequence")
        try:
            samples = tuple(self.samples)
        except TypeError as error:
            raise ValueError("samples must be a sequence") from error
        if any(not isinstance(sample, BenchmarkSample) for sample in samples):
            raise ValueError("samples must contain BenchmarkSample values")
        if any(sample.ticker not in self.tickers for sample in samples):
            raise ValueError("sample ticker is outside the frozen corpus")
        if any(sample.seed not in self.seeds for sample in samples):
            raise ValueError("sample seed is outside the frozen seed list")
        if len({sample.identity for sample in samples}) != len(samples):
            raise ValueError("benchmark samples contain a duplicate scheduling identity")
        mode_order = {"cold": 0, "warm": 1}
        ordered = tuple(sorted(samples, key=lambda item: (
            self.tickers.index(item.ticker), mode_order[item.mode], self.seeds.index(item.seed),
            item.global_slot,
        )))
        object.__setattr__(self, "samples", ordered)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "as_of": self.as_of.isoformat(),
            "tickers": list(self.tickers),
            "seeds": list(self.seeds),
            "catalog_hash": self.catalog_hash,
            "feature_build_contract_hash": self.feature_build_contract_hash,
            "candidate_space_hash": self.candidate_space_hash,
            "split_identity": self.split_identity,
            "execution_contract_identity": self.execution_contract_identity,
            "samples": [sample.to_dict() for sample in self.samples],
        }

    @property
    def digest(self) -> str:
        return _digest_payload(self.to_payload())

    def to_document(self) -> dict[str, object]:
        return {"digest": self.digest, "kind": "flexible_rulebook_production_benchmark", "payload": self.to_payload()}

    @property
    def eligibility_failures(self) -> tuple[str, ...]:
        failures: list[str] = []
        for ticker in self.tickers:
            ticker_samples = tuple(sample for sample in self.samples if sample.ticker == ticker)
            fingerprints = {sample.source_fingerprint for sample in ticker_samples}
            if len(fingerprints) != 1 or None in fingerprints:
                failures.append(f"{ticker}: source fingerprint is missing or changed")
            for seed in self.seeds:
                cold = tuple(
                    sample for sample in ticker_samples
                    if sample.mode == "cold" and sample.seed == seed
                )
                completed = tuple(sample for sample in cold if sample.is_complete)
                if len(completed) < MIN_COLD_SAMPLE_COUNT:
                    failures.append(
                        f"{ticker}/{seed}: requires {MIN_COLD_SAMPLE_COUNT} completed cold maximal samples"
                    )
                if len(cold) != len(completed):
                    failures.append(f"{ticker}/{seed}: contains incomplete cold evidence")
            if any(not sample.is_complete for sample in ticker_samples):
                failures.append(f"{ticker}: contains incomplete warm or cold evidence")
        return tuple(failures)

    @property
    def is_discovery_eligible(self) -> bool:
        return not self.eligibility_failures

    @classmethod
    def from_payload(cls, value: object) -> "ProductionBenchmarkReport":
        payload = _require_mapping(value, "benchmark report payload")
        required = {
            "schema_version", "as_of", "tickers", "seeds", "catalog_hash",
            "feature_build_contract_hash", "candidate_space_hash", "split_identity",
            "execution_contract_identity", "samples",
        }
        if set(payload) != required:
            raise ValueError("benchmark report payload schema is invalid")
        try:
            as_of = date.fromisoformat(payload["as_of"])
        except (TypeError, ValueError) as error:
            raise ValueError("benchmark report as_of is invalid") from error
        if not isinstance(payload["samples"], list):
            raise ValueError("benchmark report samples are invalid")
        return cls(
            schema_version=payload["schema_version"], as_of=as_of, tickers=tuple(payload["tickers"]),
            seeds=tuple(payload["seeds"]), catalog_hash=payload["catalog_hash"],
            feature_build_contract_hash=payload["feature_build_contract_hash"],
            candidate_space_hash=payload["candidate_space_hash"], split_identity=payload["split_identity"],
            execution_contract_identity=payload["execution_contract_identity"],
            samples=tuple(BenchmarkSample.from_dict(item) for item in payload["samples"]),
        )


def _report_path(value: Path | str, *, create_parent: bool) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.exists() and path.is_dir():
        raise ValueError("benchmark report path must be an absolute file path")
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def write_production_benchmark_report(
    path: Path | str,
    report: ProductionBenchmarkReport,
) -> Path:
    """Atomically write canonical benchmark evidence without policy side effects."""

    if not isinstance(report, ProductionBenchmarkReport):
        raise ValueError("report must be ProductionBenchmarkReport")
    target = _report_path(path, create_parent=True)
    material = canonical_json(report.to_document())
    with tempfile.NamedTemporaryFile(
        dir=target.parent, mode="w", encoding="utf-8", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def read_production_benchmark_report(path: Path | str) -> ProductionBenchmarkReport:
    """Read only an untampered canonical benchmark document."""

    target = _report_path(path, create_parent=False)
    try:
        material = target.read_text(encoding="utf-8")
        encoded = json.loads(material)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("benchmark report is unreadable") from error
    if canonical_json(encoded) != material:
        raise ValueError("benchmark report must use canonical JSON")
    document = _require_mapping(encoded, "benchmark report document")
    if set(document) != {"digest", "kind", "payload"}:
        raise ValueError("benchmark report document schema is invalid")
    if document["kind"] != "flexible_rulebook_production_benchmark":
        raise ValueError("benchmark report kind is invalid")
    digest = document["digest"]
    _hash(digest, "benchmark report digest")
    payload = _require_mapping(document["payload"], "benchmark report payload")
    if _digest_payload(payload) != digest:
        raise ValueError("benchmark report digest does not match canonical payload")
    decoded = decode_canonical_scalars(payload)
    report = ProductionBenchmarkReport.from_payload(decoded)
    if report.digest != digest:
        raise ValueError("benchmark report digest does not match validated report")
    return report


def benchmark_record_from_report(report: ProductionBenchmarkReport) -> BenchmarkRecord:
    """Derive conservative timing evidence only from an eligible report.

    One-slot samples prove a per-slot timing envelope, not an end-to-end fixed
    attempt cap.  Therefore ``measured_discovery_attempt_caps`` remains empty.
    A separate review/approval step is still required before policy changes.
    """

    if not isinstance(report, ProductionBenchmarkReport):
        raise ValueError("report must be ProductionBenchmarkReport")
    if not report.is_discovery_eligible:
        detail = "; ".join(report.eligibility_failures)
        raise ValueError(f"benchmark report is ineligible: {detail}")

    per_ticker: list[dict[str, float]] = []
    cold_counts: list[int] = []
    for ticker in report.tickers:
        cold = tuple(sample for sample in report.samples if sample.ticker == ticker and sample.mode == "cold")
        cold_counts.append(len(cold))
        def p99(name: str) -> float:
            values = [getattr(sample, name) for sample in cold]
            assert all(value is not None for value in values)
            return _p99([float(value) for value in values])
        per_ticker.append({
            "preflight": p99("preflight_seconds"),
            "training": p99("training_seconds"),
            "test": p99("test_seconds"),
            "selection": p99("selection_seconds"),
            "write": p99("write_seconds"),
            "maximal": p99("maximal_slot_seconds"),
        })
    worst = {name: max(values[name] for values in per_ticker) for name in per_ticker[0]}
    return BenchmarkRecord(
        benchmark_report_hash=report.digest,
        scope="discovery",
        completed=True,
        measured_current_scan_ticker_counts=(),
        # Timing one slot cannot prove a whole multi-slot cap.
        measured_discovery_attempt_caps=(),
        worker_counts=(1,),
        maximal_slot_sample_count=min(cold_counts),
        cold_p99_preflight_seconds=worst["preflight"],
        cold_p99_training_seconds=worst["training"],
        cold_p99_test_seconds=worst["test"],
        cold_p99_selection_seconds=worst["selection"],
        cold_p99_write_seconds=worst["write"],
        cold_p99_maximal_slot_seconds=worst["maximal"],
        # Conservative cross-sample bound required by the existing policy gate.
        cold_p99_total_seconds=worst["preflight"] + worst["maximal"],
    )


__all__ = [
    "ADMISSION_SECONDS", "TERMINAL_SECONDS", "BenchmarkRecord", "BenchmarkSample",
    "MIN_COLD_SAMPLE_COUNT", "PRODUCTION_BENCHMARK_SCHEMA_VERSION",
    "ProductionBenchmarkReport", "ScalePolicy", "benchmark_record_from_report",
    "decode_canonical_scalars",
    "read_production_benchmark_report", "safe_default_scale_policy",
    "validate_scale_policy", "write_production_benchmark_report",
]
