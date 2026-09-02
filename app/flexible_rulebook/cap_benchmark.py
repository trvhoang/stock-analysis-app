"""Immutable direct cap-window benchmark evidence for Flexible Rulebook."""

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
from typing import Literal, Sequence

from .benchmark import (
    ADMISSION_SECONDS,
    MIN_COLD_SAMPLE_COUNT,
    TERMINAL_SECONDS,
    BenchmarkRecord,
    decode_canonical_scalars,
)
from .contracts import canonical_json


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TICKER = re.compile(r"^[A-Z0-9._-]+$")
_SAFE_ERROR = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+$")
_TERMINAL_STATES = frozenset(
    {
        "queued",
        "running",
        "cancelling",
        "cancelled",
        "blocked",
        "interrupted",
        "completed",
        "completed_with_errors",
        "failed",
    }
)
CAP_BENCHMARK_SCHEMA_VERSION = 1


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


def _ticker(value: object, name: str = "ticker") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    normalized = value.strip().upper()
    if not normalized or not _TICKER.fullmatch(normalized):
        raise ValueError(f"{name} must be persistence-safe uppercase text")
    return normalized


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _seconds(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative duration")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds < 0.0:
        raise ValueError(f"{name} must be a finite non-negative duration")
    return seconds


def _p99(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("p99 requires at least one duration")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * 0.99
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _source_identity(value: object, ticker: str) -> str:
    material = _canonical_identity(value, "source_identity")
    decoded = json.loads(material)
    if not isinstance(decoded, dict):
        raise ValueError("source_identity must be a JSON object")
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
    if set(decoded) != required or decoded.get("ticker") != ticker:
        raise ValueError("source_identity is incomplete")
    if not isinstance(decoded["raw_history_fingerprint"], str) or not _DIGEST.fullmatch(
        decoded["raw_history_fingerprint"]
    ):
        raise ValueError("source_identity fingerprint is invalid")
    if decoded.get("quality_state") != "eligible":
        raise ValueError("source_identity must be eligible")
    if decoded.get("quality_revision") != "flexible-history-v1":
        raise ValueError("source_identity quality revision is invalid")
    try:
        for key in ("requested_start", "requested_as_of", "first_date", "as_of_date"):
            date.fromisoformat(decoded[key])
    except (TypeError, ValueError) as error:
        raise ValueError("source_identity dates are invalid") from error
    return material


@dataclass(frozen=True)
class SlotPhaseTiming:
    """One observed non-window phase for one committed global slot."""

    global_slot: int
    phase: Literal["entry_mask", "training", "test"]
    seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_slot", _non_negative_int(self.global_slot, "global_slot"))
        if self.phase not in {"entry_mask", "training", "test"}:
            raise ValueError("slot timing phase is unsupported")
        object.__setattr__(self, "seconds", _seconds(self.seconds, "slot timing seconds"))

    def to_dict(self) -> dict[str, object]:
        return {
            "global_slot": self.global_slot,
            "phase": self.phase,
            "seconds": self.seconds,
        }


@dataclass(frozen=True)
class WindowPhaseTiming:
    """One observed finalization cost for the whole cap window."""

    phase: Literal["selection", "write"]
    seconds: float

    def __post_init__(self) -> None:
        if self.phase not in {"selection", "write"}:
            raise ValueError("window timing phase is unsupported")
        object.__setattr__(self, "seconds", _seconds(self.seconds, "window timing seconds"))

    def to_dict(self) -> dict[str, object]:
        return {"phase": self.phase, "seconds": self.seconds}


@dataclass(frozen=True)
class DiscoveryCapSample:
    """One isolated cold or warm end-to-end fixed-cap discovery window."""

    ticker: str
    seed: str
    mode: Literal["cold", "warm"]
    sample_index: int
    benchmark_as_of: date
    cap_attempts: int
    start_slot: int
    assignment_hash: str
    source_identity: str | None
    split_identity: str | None
    attempted_count: int
    committed_count: int
    next_slot: int
    uncommitted_slot: int | None
    preflight_seconds: float
    cap_window_seconds: float
    total_seconds: float
    slot_timings: tuple[SlotPhaseTiming, ...]
    selection_seconds: float
    write_seconds: float
    terminal_state: str
    safe_error_code: str | None
    peak_rss_bytes: int | None
    peak_pool_checkouts: int | None
    cache_bytes: int
    artifact_bytes: int

    def __post_init__(self) -> None:
        ticker = _ticker(self.ticker)
        object.__setattr__(self, "ticker", ticker)
        object.__setattr__(self, "seed", _text(self.seed, "seed"))
        if self.mode not in {"cold", "warm"}:
            raise ValueError("mode must be cold or warm")
        object.__setattr__(self, "sample_index", _non_negative_int(self.sample_index, "sample_index"))
        if type(self.benchmark_as_of) is not date:
            raise ValueError("benchmark_as_of must be a date")
        cap = _positive_int(self.cap_attempts, "cap_attempts")
        object.__setattr__(self, "cap_attempts", cap)
        expected_start = self.sample_index * cap
        if self.start_slot != expected_start:
            raise ValueError("start_slot must equal sample_index multiplied by cap_attempts")
        object.__setattr__(self, "start_slot", _non_negative_int(self.start_slot, "start_slot"))
        if not isinstance(self.assignment_hash, str) or not _DIGEST.fullmatch(self.assignment_hash):
            raise ValueError("assignment_hash must be a SHA-256 digest")
        if self.source_identity is not None:
            object.__setattr__(
                self,
                "source_identity",
                _source_identity(self.source_identity, ticker),
            )
        if self.split_identity is not None:
            object.__setattr__(
                self,
                "split_identity",
                _canonical_identity(self.split_identity, "split_identity"),
            )
        for name in ("attempted_count", "committed_count", "next_slot"):
            object.__setattr__(self, name, _non_negative_int(getattr(self, name), name))
        if self.uncommitted_slot is not None:
            object.__setattr__(
                self,
                "uncommitted_slot",
                _non_negative_int(self.uncommitted_slot, "uncommitted_slot"),
            )
        for name in (
            "preflight_seconds",
            "cap_window_seconds",
            "total_seconds",
            "selection_seconds",
            "write_seconds",
        ):
            object.__setattr__(self, name, _seconds(getattr(self, name), name))
        if self.total_seconds < self.preflight_seconds + self.cap_window_seconds:
            raise ValueError("total_seconds is below preflight plus cap-window duration")
        try:
            timings = tuple(self.slot_timings)
        except TypeError as error:
            raise ValueError("slot_timings must be a sequence") from error
        if any(not isinstance(item, SlotPhaseTiming) for item in timings):
            raise ValueError("slot_timings must contain SlotPhaseTiming values")
        if any(
            item.global_slot < self.start_slot
            or item.global_slot >= self.start_slot + self.cap_attempts
            for item in timings
        ):
            raise ValueError("slot timing is outside its cap window")
        object.__setattr__(self, "slot_timings", timings)
        if self.terminal_state not in _TERMINAL_STATES:
            raise ValueError("terminal_state is unsupported")
        if self.safe_error_code is not None:
            code = _text(self.safe_error_code, "safe_error_code")
            if not _SAFE_ERROR.fullmatch(code):
                raise ValueError("safe_error_code is invalid")
            object.__setattr__(self, "safe_error_code", code)
        for name in ("peak_rss_bytes", "peak_pool_checkouts"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _non_negative_int(value, name))
        for name in ("cache_bytes", "artifact_bytes"):
            object.__setattr__(self, name, _non_negative_int(getattr(self, name), name))

    @property
    def identity(self) -> tuple[str, str, str, int, date, int, str]:
        return (
            self.ticker,
            self.seed,
            self.mode,
            self.sample_index,
            self.benchmark_as_of,
            self.cap_attempts,
            self.assignment_hash,
        )

    @property
    def is_complete_cold_window(self) -> bool:
        return (
            self.mode == "cold"
            and self.terminal_state == "completed"
            and self.safe_error_code is None
            and self.uncommitted_slot is None
            and self.source_identity is not None
            and self.split_identity is not None
            and self.attempted_count == self.cap_attempts
            and self.committed_count == self.cap_attempts
            and self.next_slot == self.start_slot + self.cap_attempts
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "seed": self.seed,
            "mode": self.mode,
            "sample_index": self.sample_index,
            "benchmark_as_of": self.benchmark_as_of.isoformat(),
            "cap_attempts": self.cap_attempts,
            "start_slot": self.start_slot,
            "assignment_hash": self.assignment_hash,
            "source_identity": self.source_identity,
            "split_identity": self.split_identity,
            "attempted_count": self.attempted_count,
            "committed_count": self.committed_count,
            "next_slot": self.next_slot,
            "uncommitted_slot": self.uncommitted_slot,
            "preflight_seconds": self.preflight_seconds,
            "cap_window_seconds": self.cap_window_seconds,
            "total_seconds": self.total_seconds,
            "slot_timings": [item.to_dict() for item in self.slot_timings],
            "selection_seconds": self.selection_seconds,
            "write_seconds": self.write_seconds,
            "terminal_state": self.terminal_state,
            "safe_error_code": self.safe_error_code,
            "peak_rss_bytes": self.peak_rss_bytes,
            "peak_pool_checkouts": self.peak_pool_checkouts,
            "cache_bytes": self.cache_bytes,
            "artifact_bytes": self.artifact_bytes,
        }

    @classmethod
    def from_dict(cls, value: object) -> "DiscoveryCapSample":
        if not isinstance(value, dict):
            raise ValueError("cap sample must be a JSON object")
        required = {
            "ticker",
            "seed",
            "mode",
            "sample_index",
            "benchmark_as_of",
            "cap_attempts",
            "start_slot",
            "assignment_hash",
            "source_identity",
            "split_identity",
            "attempted_count",
            "committed_count",
            "next_slot",
            "uncommitted_slot",
            "preflight_seconds",
            "cap_window_seconds",
            "total_seconds",
            "slot_timings",
            "selection_seconds",
            "write_seconds",
            "terminal_state",
            "safe_error_code",
            "peak_rss_bytes",
            "peak_pool_checkouts",
            "cache_bytes",
            "artifact_bytes",
        }
        if set(value) != required or not isinstance(value["slot_timings"], list):
            raise ValueError("cap sample schema is invalid")
        try:
            benchmark_as_of = date.fromisoformat(value["benchmark_as_of"])
        except (TypeError, ValueError) as error:
            raise ValueError("cap sample benchmark_as_of is invalid") from error
        return cls(
            ticker=value["ticker"],
            seed=value["seed"],
            mode=value["mode"],
            sample_index=value["sample_index"],
            benchmark_as_of=benchmark_as_of,
            cap_attempts=value["cap_attempts"],
            start_slot=value["start_slot"],
            assignment_hash=value["assignment_hash"],
            source_identity=value["source_identity"],
            split_identity=value["split_identity"],
            attempted_count=value["attempted_count"],
            committed_count=value["committed_count"],
            next_slot=value["next_slot"],
            uncommitted_slot=value["uncommitted_slot"],
            preflight_seconds=value["preflight_seconds"],
            cap_window_seconds=value["cap_window_seconds"],
            total_seconds=value["total_seconds"],
            slot_timings=tuple(SlotPhaseTiming(**item) for item in value["slot_timings"]),
            selection_seconds=value["selection_seconds"],
            write_seconds=value["write_seconds"],
            terminal_state=value["terminal_state"],
            safe_error_code=value["safe_error_code"],
            peak_rss_bytes=value["peak_rss_bytes"],
            peak_pool_checkouts=value["peak_pool_checkouts"],
            cache_bytes=value["cache_bytes"],
            artifact_bytes=value["artifact_bytes"],
        )


def _unique_texts(values: object, name: str, normalizer) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        result = tuple(normalizer(value) for value in values)
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    if not result or len(set(result)) != len(result):
        raise ValueError(f"{name} must be non-empty and unique")
    return result


@dataclass(frozen=True)
class DiscoveryCapBenchmarkReport:
    """Canonical direct-cap evidence; it cannot activate policy on its own."""

    benchmark_as_of: date
    tickers: tuple[str, ...]
    seeds: tuple[str, ...]
    cap_attempts: int
    runtime_contract_identity: str
    samples: tuple[DiscoveryCapSample, ...]
    ticker_elapsed_seconds_by_ticker: tuple[tuple[str, float], ...]
    schema_version: int = CAP_BENCHMARK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.benchmark_as_of) is not date:
            raise ValueError("benchmark_as_of must be a date")
        object.__setattr__(self, "tickers", _unique_texts(self.tickers, "tickers", _ticker))
        object.__setattr__(self, "seeds", _unique_texts(self.seeds, "seeds", lambda value: _text(value, "seed")))
        object.__setattr__(self, "cap_attempts", _positive_int(self.cap_attempts, "cap_attempts"))
        object.__setattr__(
            self,
            "runtime_contract_identity",
            _canonical_identity(self.runtime_contract_identity, "runtime_contract_identity"),
        )
        if self.schema_version != CAP_BENCHMARK_SCHEMA_VERSION:
            raise ValueError("cap benchmark schema version is unsupported")
        try:
            samples = tuple(self.samples)
        except TypeError as error:
            raise ValueError("samples must be a sequence") from error
        if any(not isinstance(item, DiscoveryCapSample) for item in samples):
            raise ValueError("samples must contain DiscoveryCapSample values")
        if any(
            item.benchmark_as_of != self.benchmark_as_of
            or item.cap_attempts != self.cap_attempts
            or item.ticker not in self.tickers
            or item.seed not in self.seeds
            for item in samples
        ):
            raise ValueError("sample scope does not match cap report")
        if len({item.identity for item in samples}) != len(samples):
            raise ValueError("cap report contains duplicate sample identity")
        if len({(item.ticker, item.seed, item.mode, item.sample_index) for item in samples}) != len(samples):
            raise ValueError("cap report repeats a sample window")
        ordered = tuple(
            sorted(
                samples,
                key=lambda item: (
                    self.tickers.index(item.ticker),
                    self.seeds.index(item.seed),
                    0 if item.mode == "cold" else 1,
                    item.sample_index,
                ),
            )
        )
        object.__setattr__(self, "samples", ordered)
        try:
            elapsed_items = tuple(self.ticker_elapsed_seconds_by_ticker)
        except TypeError as error:
            raise ValueError("ticker_elapsed_seconds_by_ticker must be a sequence") from error
        elapsed: dict[str, float] = {}
        for item in elapsed_items:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("ticker elapsed entry is invalid")
            ticker, seconds = _ticker(item[0], "ticker elapsed ticker"), _seconds(
                item[1], "ticker elapsed seconds"
            )
            if ticker in elapsed:
                raise ValueError("ticker elapsed entries must be unique")
            elapsed[ticker] = seconds
        if set(elapsed) != set(self.tickers):
            raise ValueError("ticker elapsed entries must cover the report ticker scope")
        for ticker, seconds in elapsed.items():
            observed = sum(sample.total_seconds for sample in samples if sample.ticker == ticker)
            if seconds < observed:
                raise ValueError("ticker elapsed seconds are below observed sample totals")
        object.__setattr__(
            self,
            "ticker_elapsed_seconds_by_ticker",
            tuple((ticker, elapsed[ticker]) for ticker in self.tickers),
        )

    def cold_samples(self, ticker: str, seed: str) -> tuple[DiscoveryCapSample, ...]:
        normalized_ticker = _ticker(ticker)
        normalized_seed = _text(seed, "seed")
        return tuple(
            item
            for item in self.samples
            if item.ticker == normalized_ticker and item.seed == normalized_seed and item.mode == "cold"
        )

    @property
    def eligibility_failures(self) -> tuple[str, ...]:
        failures: list[str] = []
        for ticker in self.tickers:
            if dict(self.ticker_elapsed_seconds_by_ticker)[ticker] > TERMINAL_SECONDS:
                failures.append(f"{ticker}: serial ticker budget exceeds {TERMINAL_SECONDS} seconds")
            ticker_completed = tuple(
                item
                for item in self.samples
                if item.ticker == ticker and item.is_complete_cold_window
            )
            for seed in self.seeds:
                cold = self.cold_samples(ticker, seed)
                completed = tuple(item for item in cold if item.is_complete_cold_window)
                if len(completed) < MIN_COLD_SAMPLE_COUNT:
                    failures.append(
                        f"{ticker}/{seed}: requires {MIN_COLD_SAMPLE_COUNT} completed cold cap windows"
                    )
                if len(cold) != len(completed):
                    failures.append(f"{ticker}/{seed}: cold evidence is not exactly complete")
                if not completed:
                    continue
                if len({item.source_identity for item in completed}) != 1:
                    failures.append(f"{ticker}/{seed}: source identity changed")
                if len({item.split_identity for item in completed}) != 1:
                    failures.append(f"{ticker}/{seed}: split identity changed")
                preflight = _p99([item.preflight_seconds for item in completed])
                window = _p99([item.cap_window_seconds for item in completed])
                total = _p99([item.total_seconds for item in completed])
                if preflight + window > ADMISSION_SECONDS:
                    failures.append(f"{ticker}/{seed}: p99 preflight plus cap window exceeds admission deadline")
                if total > TERMINAL_SECONDS:
                    failures.append(f"{ticker}/{seed}: p99 total exceeds terminal deadline")
            if ticker_completed and len(
                {item.source_identity for item in ticker_completed}
            ) != 1:
                failures.append(f"{ticker}: source identity changed across seeds")
            if ticker_completed and len(
                {item.split_identity for item in ticker_completed}
            ) != 1:
                failures.append(f"{ticker}: split identity changed across seeds")
        return tuple(failures)

    @property
    def is_eligible(self) -> bool:
        return not self.eligibility_failures

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "benchmark_as_of": self.benchmark_as_of.isoformat(),
            "tickers": list(self.tickers),
            "seeds": list(self.seeds),
            "cap_attempts": self.cap_attempts,
            "runtime_contract_identity": self.runtime_contract_identity,
            "samples": [item.to_dict() for item in self.samples],
            "ticker_elapsed_seconds_by_ticker": [
                {"ticker": ticker, "seconds": seconds}
                for ticker, seconds in self.ticker_elapsed_seconds_by_ticker
            ],
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.to_payload()).encode("utf-8")).hexdigest()

    def to_document(self) -> dict[str, object]:
        return {
            "kind": "flexible_rulebook_discovery_cap_benchmark",
            "digest": self.digest,
            "payload": self.to_payload(),
        }

    @classmethod
    def from_payload(cls, value: object) -> "DiscoveryCapBenchmarkReport":
        if not isinstance(value, dict):
            raise ValueError("cap report payload must be a JSON object")
        required = {
            "schema_version",
            "benchmark_as_of",
            "tickers",
            "seeds",
            "cap_attempts",
            "runtime_contract_identity",
            "samples",
            "ticker_elapsed_seconds_by_ticker",
        }
        if set(value) != required or not isinstance(value["samples"], list):
            raise ValueError("cap report payload schema is invalid")
        if not isinstance(value["ticker_elapsed_seconds_by_ticker"], list):
            raise ValueError("cap report ticker elapsed schema is invalid")
        try:
            benchmark_as_of = date.fromisoformat(value["benchmark_as_of"])
            elapsed = tuple(
                (item["ticker"], item["seconds"])
                for item in value["ticker_elapsed_seconds_by_ticker"]
                if isinstance(item, dict) and set(item) == {"ticker", "seconds"}
            )
        except (TypeError, ValueError, KeyError) as error:
            raise ValueError("cap report payload is invalid") from error
        if len(elapsed) != len(value["ticker_elapsed_seconds_by_ticker"]):
            raise ValueError("cap report ticker elapsed schema is invalid")
        return cls(
            schema_version=value["schema_version"],
            benchmark_as_of=benchmark_as_of,
            tickers=tuple(value["tickers"]),
            seeds=tuple(value["seeds"]),
            cap_attempts=value["cap_attempts"],
            runtime_contract_identity=value["runtime_contract_identity"],
            samples=tuple(DiscoveryCapSample.from_dict(item) for item in value["samples"]),
            ticker_elapsed_seconds_by_ticker=elapsed,
        )


def validate_cap_report(report: DiscoveryCapBenchmarkReport) -> None:
    """Reject incomplete or deadline-unsafe direct-cap evidence."""

    if not isinstance(report, DiscoveryCapBenchmarkReport):
        raise ValueError("cap report must be DiscoveryCapBenchmarkReport")
    if report.eligibility_failures:
        raise ValueError("; ".join(report.eligibility_failures))


def benchmark_record_from_cap_report(report: DiscoveryCapBenchmarkReport) -> BenchmarkRecord:
    """Convert only eligible fixed-window evidence to a direct-cap record."""

    validate_cap_report(report)
    per_pair: list[tuple[float, float, float]] = []
    counts: list[int] = []
    for ticker in report.tickers:
        for seed in report.seeds:
            cold = report.cold_samples(ticker, seed)
            counts.append(len(cold))
            preflight_p99 = _p99([item.preflight_seconds for item in cold])
            window_p99 = _p99([item.cap_window_seconds for item in cold])
            total_p99 = _p99([item.total_seconds for item in cold])
            per_pair.append(
                (
                    preflight_p99,
                    window_p99,
                    # Independent quantiles can come from different samples;
                    # retain a conservative additive bound for activation.
                    max(total_p99, preflight_p99 + window_p99),
                )
            )
    return BenchmarkRecord(
        benchmark_report_hash=report.digest,
        scope="discovery",
        completed=True,
        measured_discovery_attempt_caps=(report.cap_attempts,),
        worker_counts=(1,),
        maximal_slot_sample_count=min(counts),
        direct_cap_window_attempt_count=report.cap_attempts,
        cold_p99_preflight_seconds=max(item[0] for item in per_pair),
        cold_p99_cap_window_seconds=max(item[1] for item in per_pair),
        cold_p99_total_seconds=max(item[2] for item in per_pair),
    )


def _report_path(path: Path | str, *, create_parent: bool) -> Path:
    target = Path(path)
    if not target.is_absolute() or target.exists() and target.is_dir():
        raise ValueError("cap report path must be an absolute file path")
    if create_parent:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target.resolve()


def write_cap_benchmark_report(path: Path | str, report: DiscoveryCapBenchmarkReport) -> Path:
    """Write immutable canonical direct-cap evidence atomically."""

    if not isinstance(report, DiscoveryCapBenchmarkReport):
        raise ValueError("report must be DiscoveryCapBenchmarkReport")
    target = _report_path(path, create_parent=True)
    material = canonical_json(report.to_document())
    if target.exists():
        if target.read_text(encoding="utf-8") != material:
            raise ValueError("immutable cap report already differs")
        return target
    with tempfile.NamedTemporaryFile(
        dir=target.parent, mode="w", encoding="utf-8", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, target)
    except FileExistsError:
        if target.read_text(encoding="utf-8") != material:
            raise ValueError("immutable cap report already differs")
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def read_cap_benchmark_report(path: Path | str) -> DiscoveryCapBenchmarkReport:
    """Read only canonical digest-matching cap evidence."""

    target = _report_path(path, create_parent=False)
    try:
        material = target.read_text(encoding="utf-8")
        document = json.loads(material)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("cap report is unreadable") from error
    if canonical_json(document) != material or not isinstance(document, dict):
        raise ValueError("cap report must use canonical JSON")
    if set(document) != {"kind", "digest", "payload"}:
        raise ValueError("cap report document schema is invalid")
    if document["kind"] != "flexible_rulebook_discovery_cap_benchmark":
        raise ValueError("cap report kind is invalid")
    if not isinstance(document["digest"], str) or not _DIGEST.fullmatch(document["digest"]):
        raise ValueError("cap report digest is invalid")
    payload = document["payload"]
    if not isinstance(payload, dict) or hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest() != document["digest"]:
        raise ValueError("cap report digest does not match canonical payload")
    decoded = decode_canonical_scalars(payload)
    report = DiscoveryCapBenchmarkReport.from_payload(decoded)
    if report.digest != document["digest"]:
        raise ValueError("cap report digest does not match validated report")
    return report


__all__ = [
    "CAP_BENCHMARK_SCHEMA_VERSION",
    "DiscoveryCapBenchmarkReport",
    "DiscoveryCapSample",
    "SlotPhaseTiming",
    "WindowPhaseTiming",
    "benchmark_record_from_cap_report",
    "read_cap_benchmark_report",
    "validate_cap_report",
    "write_cap_benchmark_report",
]
