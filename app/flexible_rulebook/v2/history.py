"""Calendar-aligned, native-bar history contracts for Flexible Rulebook v2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import numbers
import os
import re
from typing import Callable, Literal

import pandas as pd

from backtest_engine.data_quality import load_lifetime_date_bounds, load_ticker_history
from backtest_engine.listing_status import load_listing_statuses
from commons.trading_calendar import align_to_vnindex_calendar

from .contracts import TRAINING_RATIOS, canonical_json, semantic_digest


_REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")
_RAW_COLUMNS = ("open", "high", "low", "close", "volume")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def get_engine_with_retry(database_url: str) -> object:
    """Use the established database retry path only when no engine is supplied."""

    from pages.data_preparation import get_engine_with_retry as create_engine_with_retry

    return create_engine_with_retry(database_url)


def _date_only(value: object, name: str) -> date:
    if type(value) is not date:
        raise ValueError(f"{name} must be a date without a time")
    return value


def _normalize_ticker(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("ticker must be text")
    ticker = value.strip().upper()
    if not ticker or not _TICKER_PATTERN.fullmatch(ticker):
        raise ValueError("ticker must contain only persistence-safe characters")
    return ticker


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True)
class HistoryRange:
    """Lifetime or explicit source bounds; lifetime is resolved from the database."""

    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("history range start_date and end_date must be paired")
        if self.start_date is not None:
            _date_only(self.start_date, "start_date")
            _date_only(self.end_date, "end_date")
            if self.start_date > self.end_date:
                raise ValueError("history range start_date must not follow end_date")

    @classmethod
    def lifetime(cls) -> "HistoryRange":
        return cls()

    @classmethod
    def bounded(cls, start_date: date, end_date: date) -> "HistoryRange":
        return cls(start_date=start_date, end_date=end_date)

    @property
    def is_lifetime(self) -> bool:
        return self.start_date is None


@dataclass(frozen=True)
class HistorySnapshot:
    """One Listed ticker's raw, calendar-aligned, fingerprinted source snapshot."""

    ticker: str
    state: Literal["available", "skipped"]
    reason: str
    history_range: HistoryRange
    start_date: date | None
    end_date: date | None
    frame: pd.DataFrame
    sessions: tuple[date, ...]
    excluded_sessions: tuple[date, ...]
    source_fingerprint: str | None
    calendar_fingerprint: str | None
    fingerprint: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        if self.state not in {"available", "skipped"}:
            raise ValueError("history state must be available or skipped")
        if not isinstance(self.reason, str):
            raise ValueError("history reason must be text")
        if not isinstance(self.history_range, HistoryRange):
            raise ValueError("history_range must be HistoryRange")
        if not isinstance(self.frame, pd.DataFrame):
            raise ValueError("history frame must be a DataFrame")
        for field in ("start_date", "end_date"):
            value = getattr(self, field)
            if value is not None:
                _date_only(value, field)
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("history snapshot bounds must be paired")
        if self.start_date is not None and self.start_date > self.end_date:
            raise ValueError("history snapshot bounds must be ordered")
        object.__setattr__(self, "sessions", tuple(self.sessions))
        object.__setattr__(self, "excluded_sessions", tuple(self.excluded_sessions))
        if self.state == "skipped":
            if any(value is not None for value in (
                self.start_date, self.end_date, self.source_fingerprint,
                self.calendar_fingerprint, self.fingerprint,
            )) or self.sessions or not self.frame.empty:
                raise ValueError("skipped history cannot expose source data")
            return
        if not self.sessions or self.start_date is None or self.end_date is None:
            raise ValueError("available history requires non-empty bounds and sessions")
        for field in ("source_fingerprint", "calendar_fingerprint", "fingerprint"):
            _require_digest(getattr(self, field), field)
        if self.sessions[0] != self.start_date or self.sessions[-1] != self.end_date:
            raise ValueError("snapshot sessions must match source bounds")

    @classmethod
    def skipped(cls, ticker: str, history_range: HistoryRange, reason: str) -> "HistorySnapshot":
        return cls(
            ticker=ticker,
            state="skipped",
            reason=reason,
            history_range=history_range,
            start_date=None,
            end_date=None,
            frame=pd.DataFrame(columns=_REQUIRED_COLUMNS),
            sessions=(),
            excluded_sessions=(),
            source_fingerprint=None,
            calendar_fingerprint=None,
            fingerprint=None,
        )


@dataclass(frozen=True)
class NativeBar:
    """One causal Daily or completed W-FRI bar with actual execution sessions."""

    ordinal: int
    bucket_label: date
    first_session: date
    last_session: date
    open: int
    high: int
    low: int
    close: int
    volume: int

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal < 0:
            raise ValueError("native-bar ordinal must be a non-negative integer")
        for field in ("bucket_label", "first_session", "last_session"):
            _date_only(getattr(self, field), field)
        if self.first_session > self.last_session or self.last_session > self.bucket_label:
            raise ValueError("native-bar sessions must be ordered inside the bucket")
        for field in ("open", "high", "low", "close", "volume"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, numbers.Integral):
                raise ValueError(f"native-bar {field} must be a raw integer")
            normalized = int(value)
            if field == "volume" and normalized < 0:
                raise ValueError("native-bar volume must be non-negative")
            if field != "volume" and normalized <= 0:
                raise ValueError(f"native-bar {field} must be positive")
            object.__setattr__(self, field, normalized)

    @property
    def ohlcv(self) -> tuple[int, int, int, int, int]:
        return self.open, self.high, self.low, self.close, self.volume


@dataclass(frozen=True)
class NativePartition:
    """One disjoint execution partition after any indicator warm-up prefix."""

    label: Literal["training", "test"]
    start_ordinal: int
    end_ordinal: int
    start_bucket: date
    end_bucket: date
    start_session: date
    end_session: date
    row_count: int

    def __post_init__(self) -> None:
        if self.label not in {"training", "test"}:
            raise ValueError("partition label must be training or test")
        if self.start_ordinal < 0 or self.end_ordinal < self.start_ordinal:
            raise ValueError("partition ordinals must be ordered")
        if self.row_count != self.end_ordinal - self.start_ordinal + 1:
            raise ValueError("partition row_count must match ordinals")
        for field in ("start_bucket", "end_bucket", "start_session", "end_session"):
            _date_only(getattr(self, field), field)
        if self.start_session > self.end_session:
            raise ValueError("partition sessions must be ordered")


@dataclass(frozen=True)
class NativeSplit:
    """Immutable chronological split proof for one native-bar series."""

    training_ratio: Decimal
    warmup_bars: int
    training: NativePartition
    test: NativePartition

    def __post_init__(self) -> None:
        if self.training_ratio not in TRAINING_RATIOS:
            raise ValueError("training_ratio must be an approved Flexible Rulebook ratio")
        if isinstance(self.warmup_bars, bool) or not isinstance(self.warmup_bars, int) or self.warmup_bars < 0:
            raise ValueError("warmup_bars must be a non-negative integer")
        if self.training.end_ordinal >= self.test.start_ordinal:
            raise ValueError("native partitions must not overlap")


def _canonical_raw_frame(frame: object, *, start: date, end: date) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("history loader did not return a DataFrame")
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError("history is missing required columns: " + ", ".join(missing))
    working = frame.loc[:, _REQUIRED_COLUMNS].copy(deep=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if working.empty or working["date"].isna().any():
        raise ValueError("history contains no usable dates")
    if working["date"].duplicated().any() or not working["date"].is_monotonic_increasing:
        raise ValueError("history dates must be unique and ascending")
    actual_dates = working["date"].dt.date
    if actual_dates.iloc[0] < start or actual_dates.iloc[-1] > end:
        raise ValueError("history loader returned rows outside the requested range")
    for column in _RAW_COLUMNS:
        if not working[column].map(
            lambda value: isinstance(value, numbers.Integral) and not isinstance(value, bool)
        ).all():
            raise ValueError(f"raw {column} must contain integers")
        working[column] = working[column].map(int)
    if (working[["open", "high", "low", "close"]] <= 0).any().any() or (working["volume"] < 0).any():
        raise ValueError("raw OHLCV values must be positive prices and non-negative volume")
    return working


def _source_fingerprint(ticker: str, frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    for row in frame.itertuples(index=False):
        record = (ticker, row.date.date().isoformat(), *(int(getattr(row, name)) for name in _RAW_COLUMNS))
        digest.update(canonical_json(record).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _snapshot_fingerprint(source_fingerprint: str, calendar_fingerprint: str) -> str:
    return semantic_digest({
        "history_revision": "flexible-rulebook-v2-history-v1",
        "source_fingerprint": source_fingerprint,
        "calendar_fingerprint": calendar_fingerprint,
    })


def _resolve_engine(
    engine: object | None,
    database_url: str | None,
    engine_factory: Callable[[str], object] | None,
) -> object:
    if engine is not None:
        return engine
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is required when no engine is supplied")
    return (engine_factory or get_engine_with_retry)(url)


def load_history(
    ticker: str,
    history_range: HistoryRange,
    *,
    engine: object | None = None,
    database_url: str | None = None,
    engine_factory: Callable[[str], object] | None = None,
) -> HistorySnapshot:
    """Load one live Listed source once, then align it before any indicator work."""

    if not isinstance(history_range, HistoryRange):
        raise ValueError("history_range must be HistoryRange")
    normalized = _normalize_ticker(ticker)
    active_engine = _resolve_engine(engine, database_url, engine_factory)
    listing = load_listing_statuses((normalized,), active_engine)[normalized]
    if not listing.is_listed:
        return HistorySnapshot.skipped(normalized, history_range, listing.reason)
    if history_range.is_lifetime:
        start, end = load_lifetime_date_bounds((normalized,), active_engine)
    else:
        assert history_range.start_date is not None and history_range.end_date is not None
        start, end = history_range.start_date, history_range.end_date
    raw_ticker = _canonical_raw_frame(load_ticker_history(normalized, start, end, active_engine), start=start, end=end)
    raw_vnindex = _canonical_raw_frame(load_ticker_history("VNINDEX", start, end, active_engine), start=start, end=end)
    aligned, calendar, excluded = align_to_vnindex_calendar(
        raw_ticker,
        raw_vnindex,
        start=start,
        end=end,
    )
    aligned = _canonical_raw_frame(aligned, start=start, end=end)
    sessions = tuple(value.date() for value in pd.to_datetime(aligned["date"]))
    source_fingerprint = _source_fingerprint(normalized, raw_ticker)
    return HistorySnapshot(
        ticker=normalized,
        state="available",
        reason="",
        history_range=history_range,
        start_date=sessions[0],
        end_date=sessions[-1],
        frame=aligned,
        sessions=sessions,
        excluded_sessions=tuple(excluded),
        source_fingerprint=source_fingerprint,
        calendar_fingerprint=calendar.fingerprint,
        fingerprint=_snapshot_fingerprint(source_fingerprint, calendar.fingerprint),
    )


def build_native_bars(
    frame: pd.DataFrame,
    horizon: Literal["swing", "midterm"],
    *,
    completed_as_of: date,
) -> tuple[NativeBar, ...]:
    """Convert calendar-aligned daily raw integers to Daily or completed W-FRI bars."""

    if horizon not in {"swing", "midterm"}:
        raise ValueError("horizon must be swing or midterm")
    cutoff = _date_only(completed_as_of, "completed_as_of")
    working = _canonical_raw_frame(frame, start=date.min, end=cutoff)
    if horizon == "swing":
        return tuple(
            NativeBar(
                ordinal=ordinal,
                bucket_label=row.date.date(),
                first_session=row.date.date(),
                last_session=row.date.date(),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for ordinal, row in enumerate(working.itertuples(index=False))
        )
    working["bucket_label"] = working["date"].dt.to_period("W-FRI").dt.end_time.dt.date
    completed = working.loc[working["bucket_label"] <= cutoff]
    bars: list[NativeBar] = []
    for ordinal, (_, bucket) in enumerate(completed.groupby("bucket_label", sort=True)):
        bars.append(NativeBar(
            ordinal=ordinal,
            bucket_label=bucket["bucket_label"].iloc[0],
            first_session=bucket["date"].iloc[0].date(),
            last_session=bucket["date"].iloc[-1].date(),
            open=int(bucket["open"].iloc[0]),
            high=int(bucket["high"].max()),
            low=int(bucket["low"].min()),
            close=int(bucket["close"].iloc[-1]),
            volume=int(bucket["volume"].sum()),
        ))
    return tuple(bars)


def make_native_split(
    bars: tuple[NativeBar, ...] | list[NativeBar],
    training_ratio: Decimal,
    *,
    warmup_bars: int = 0,
) -> NativeSplit:
    """Split completed native bars chronologically after a causal warm-up prefix."""

    native = tuple(bars)
    if not native or any(not isinstance(bar, NativeBar) for bar in native):
        raise ValueError("bars must be a non-empty NativeBar sequence")
    if [bar.ordinal for bar in native] != list(range(len(native))):
        raise ValueError("native bars must use contiguous ascending ordinals")
    if training_ratio not in TRAINING_RATIOS:
        raise ValueError("training_ratio must be an approved Flexible Rulebook ratio")
    if isinstance(warmup_bars, bool) or not isinstance(warmup_bars, int) or warmup_bars < 0:
        raise ValueError("warmup_bars must be a non-negative integer")
    usable = native[warmup_bars:]
    if len(usable) < 2:
        raise ValueError("at least two native bars are required after warm-up")
    training_count = int(len(usable) * training_ratio)
    if not 1 <= training_count < len(usable):
        raise ValueError("training ratio must leave at least one native bar in each partition")

    def partition(label: Literal["training", "test"], selection: tuple[NativeBar, ...]) -> NativePartition:
        return NativePartition(
            label=label,
            start_ordinal=selection[0].ordinal,
            end_ordinal=selection[-1].ordinal,
            start_bucket=selection[0].bucket_label,
            end_bucket=selection[-1].bucket_label,
            start_session=selection[0].first_session,
            end_session=selection[-1].last_session,
            row_count=len(selection),
        )

    training = usable[:training_count]
    test = usable[training_count:]
    return NativeSplit(
        training_ratio=training_ratio,
        warmup_bars=warmup_bars,
        training=partition("training", training),
        test=partition("test", test),
    )


def trade_dates_belong_to_partition(
    signal_date: date,
    entry_date: date,
    exit_date: date | None,
    partition: NativePartition,
) -> bool:
    """Keep only completed trades whose signal, entry, and exit share one split."""

    if not isinstance(partition, NativePartition):
        raise ValueError("partition must be NativePartition")
    if exit_date is None:
        return False
    dates = (
        _date_only(signal_date, "signal_date"),
        _date_only(entry_date, "entry_date"),
        _date_only(exit_date, "exit_date"),
    )
    return all(partition.start_session <= value <= partition.end_session for value in dates)


__all__ = [
    "HistoryRange",
    "HistorySnapshot",
    "NativeBar",
    "NativePartition",
    "NativeSplit",
    "build_native_bars",
    "load_history",
    "make_native_split",
    "trade_dates_belong_to_partition",
]
