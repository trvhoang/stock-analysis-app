"""Fresh bounded raw-history contracts for Flexible Rulebook only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from typing import Literal

import pandas as pd
import pytz

# Flexible may reuse this bounded parameterized raw loader, but owns every
# validation, audit, fingerprint, split, and evidence decision below.
from backtest_engine.data_quality import load_ticker_history as _load_ticker_history

from .contracts import EvaluationPartition, EvaluationSplit


_REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")
_PRICE_COLUMNS = ("open", "high", "low", "close")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
_QUALITY_STATES = ("eligible", "display_only", "invalid")
_FULL_WINDOW_START_TOLERANCE = timedelta(days=7)
_MAX_OHLC_ORDERING_MISMATCH = 0.01
_CLOSE_DISCONTINUITY_THRESHOLD = 0.15
_WARNING_CLOSE_MOVE_THRESHOLD = 0.07
_WARNING_DATE_GAP_DAYS = 7
_HCM = pytz.timezone("Asia/Ho_Chi_Minh")


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


def _require_hash(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _subtract_calendar_years(value: date, years: int) -> date:
    """Move a date back by whole calendar years, mapping leap day to Feb 28."""

    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, month=2, day=28)


def _normalized_raw_number(value: object) -> str:
    """Give raw numeric database values one dtype-independent hash spelling."""

    if isinstance(value, bool):
        raise ValueError("raw OHLCV numbers must be numeric")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("raw OHLCV numbers must be finite") from error
    if not decimal.is_finite():
        raise ValueError("raw OHLCV numbers must be finite")
    normalized = decimal.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _parsed_dates(frame: pd.DataFrame) -> pd.Series | None:
    """Return ordered date-only timestamps only when their daily shape is valid."""

    parsed = pd.to_datetime(frame["date"], errors="coerce")
    if parsed.isna().any() or not isinstance(parsed, pd.Series):
        return None
    if getattr(parsed.dt, "tz", None) is not None:
        return None
    if (parsed != parsed.dt.normalize()).any():
        return None
    return parsed


def _assess_raw_ohlcv(
    frame: object,
) -> tuple[pd.DataFrame, pd.Series | None, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Classify a raw frame without ever normalizing its caller-owned values."""

    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame(), None, ("OHLCV loader did not return a DataFrame",), (), ()

    raw = frame.copy(deep=True)
    missing = [column for column in _REQUIRED_COLUMNS if column not in raw.columns]
    if missing:
        return raw, None, (f"missing required columns: {', '.join(missing)}",), (), ()
    if raw.empty:
        return raw, None, ("history contains no rows",), (), ()

    errors: list[str] = []
    warnings: list[str] = []
    concerns: list[str] = []
    dates = _parsed_dates(raw)
    if dates is None:
        errors.append("date values must be ordered, unique daily dates")
    elif dates.duplicated().any():
        errors.append("date contains duplicate values")
    elif not dates.is_monotonic_increasing:
        errors.append("date values must be in ascending order")

    numeric: dict[str, pd.Series] = {}
    for column in (*_PRICE_COLUMNS, "volume"):
        values = pd.to_numeric(raw[column], errors="coerce")
        numeric[column] = values
        if values.isna().any() or not values.map(lambda item: math.isfinite(float(item))).all():
            errors.append(f"{column} contains missing or non-finite values")
            continue
        if column in _PRICE_COLUMNS and (values <= 0).any():
            errors.append(f"{column} contains non-positive prices")
        if column == "volume" and (values < 0).any():
            errors.append("volume contains negative values")

    if errors or dates is None:
        return raw, dates, tuple(errors), tuple(warnings), tuple(concerns)

    gaps = dates.diff().dt.days.dropna()
    for position in gaps[gaps > _WARNING_DATE_GAP_DAYS].index:
        warnings.append(
            f"date gap of {int(gaps.loc[position])} calendar days before "
            f"{dates.loc[position].date().isoformat()}"
        )
    if (numeric["volume"] == 0).any():
        warnings.append("zero volume rows present")

    body_high = pd.concat([numeric["open"], numeric["close"]], axis=1).max(axis=1)
    body_low = pd.concat([numeric["open"], numeric["close"]], axis=1).min(axis=1)
    mismatch = pd.concat(
        [
            body_high - numeric["high"],
            numeric["low"] - body_low,
            numeric["low"] - numeric["high"],
        ],
        axis=1,
    ).clip(lower=0).max(axis=1)
    bar_maximum = pd.concat(list(numeric.values()), axis=1).max(axis=1)
    if (mismatch.div(bar_maximum) > _MAX_OHLC_ORDERING_MISMATCH).any():
        concerns.append("OHLC ordering mismatch exceeds 1%")

    close_moves = numeric["close"].pct_change().abs()
    if (close_moves >= _CLOSE_DISCONTINUITY_THRESHOLD).any():
        concerns.append("close discontinuity reaches 15%")
    elif (close_moves > _WARNING_CLOSE_MOVE_THRESHOLD).any():
        warnings.append("close move exceeds 7%")

    return raw, dates, (), tuple(warnings), tuple(concerns)


def _fingerprint_ordered_ohlcv(ticker: str, frame: pd.DataFrame, dates: pd.Series) -> str:
    """Hash every ordered raw OHLCV row, independent of pandas integer dtype."""

    digest = hashlib.sha256()
    for position in range(len(frame)):
        record = (
            ticker,
            dates.iloc[position].date().isoformat(),
            *(_normalized_raw_number(frame[column].iloc[position]) for column in _PRICE_COLUMNS),
            _normalized_raw_number(frame["volume"].iloc[position]),
        )
        digest.update(json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


@dataclass(frozen=True)
class HistorySnapshot:
    """One fresh raw-history load and its Flexible-owned quality evidence."""

    ticker: str
    frame: pd.DataFrame
    fingerprint: str | None
    quality_state: Literal["eligible", "display_only", "invalid"]
    requested_start: date
    requested_as_of: date
    first_date: date | None
    as_of_date: date | None
    evidence_prefix_fingerprint: str | None
    quality_reasons: tuple[str, ...] = ()
    quality_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        if not isinstance(self.frame, pd.DataFrame):
            raise ValueError("frame must be a pandas DataFrame")
        _date_only(self.requested_start, "requested_start")
        _date_only(self.requested_as_of, "requested_as_of")
        if self.requested_start > self.requested_as_of:
            raise ValueError("requested history bounds must be ordered")
        if self.quality_state not in _QUALITY_STATES:
            raise ValueError(f"quality_state must be one of {_QUALITY_STATES}")
        for name in ("first_date", "as_of_date"):
            value = getattr(self, name)
            if value is not None:
                _date_only(value, name)
        if (self.first_date is None) != (self.as_of_date is None):
            raise ValueError("actual history bounds must be both present or absent")
        if self.first_date is not None and self.first_date > self.as_of_date:
            raise ValueError("actual history bounds must be ordered")
        if (
            self.first_date is not None
            and (self.first_date < self.requested_start or self.as_of_date > self.requested_as_of)
        ):
            raise ValueError("actual history bounds must remain inside requested bounds")
        if self.fingerprint is not None:
            object.__setattr__(self, "fingerprint", _require_hash(self.fingerprint, "fingerprint"))
        if self.evidence_prefix_fingerprint is not None:
            object.__setattr__(
                self,
                "evidence_prefix_fingerprint",
                _require_hash(self.evidence_prefix_fingerprint, "evidence_prefix_fingerprint"),
            )
        if self.quality_state == "invalid":
            if self.fingerprint is not None or self.evidence_prefix_fingerprint is not None:
                raise ValueError("invalid history must not expose a reusable fingerprint")
        elif (
            self.fingerprint is None
            or self.evidence_prefix_fingerprint is None
            or self.first_date is None
            or self.as_of_date is None
        ):
            raise ValueError("usable history must have actual bounds and fingerprints")
        if self.quality_state != "invalid":
            native_dates = _parsed_dates(self.frame)
            if (
                native_dates is None
                or native_dates.duplicated().any()
                or not native_dates.is_monotonic_increasing
                or native_dates.iloc[0].date() != self.first_date
                or native_dates.iloc[-1].date() != self.as_of_date
            ):
                raise ValueError("actual history bounds must match ordered frame dates")
        object.__setattr__(self, "quality_reasons", tuple(self.quality_reasons))
        object.__setattr__(self, "quality_warnings", tuple(self.quality_warnings))


@dataclass(frozen=True)
class EvidenceSourceAnchor:
    """Immutable historical-prefix proof; durable persistence arrives later."""

    ticker: str
    requested_start: date
    requested_as_of: date
    first_date: date
    as_of_date: date
    prefix_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        for name in ("requested_start", "requested_as_of", "first_date", "as_of_date"):
            _date_only(getattr(self, name), name)
        if self.requested_start > self.requested_as_of or self.first_date > self.as_of_date:
            raise ValueError("evidence source bounds must be ordered")
        object.__setattr__(self, "prefix_fingerprint", _require_hash(
            self.prefix_fingerprint,
            "prefix_fingerprint",
        ))


def load_flexible_history(
    engine: object,
    ticker: str,
    as_of: date | None = None,
) -> HistorySnapshot:
    """Fresh-load one calendar 15-year raw range before any cache inspection."""

    requested_as_of = _date_only(as_of, "as_of") if as_of is not None else datetime.now(_HCM).date()
    requested_start = _subtract_calendar_years(requested_as_of, 15)
    normalized_ticker = _normalize_ticker(ticker)
    raw = _load_ticker_history(normalized_ticker, requested_start, requested_as_of, engine)
    frame, dates, errors, warnings, concerns = _assess_raw_ohlcv(raw)
    if dates is None:
        first_date = None
        as_of_date = None
    else:
        first_date = dates.iloc[0].date()
        as_of_date = dates.iloc[-1].date()
    if errors:
        return HistorySnapshot(
            ticker=normalized_ticker,
            frame=frame,
            fingerprint=None,
            quality_state="invalid",
            requested_start=requested_start,
            requested_as_of=requested_as_of,
            first_date=first_date,
            as_of_date=as_of_date,
            evidence_prefix_fingerprint=None,
            quality_reasons=errors,
            quality_warnings=warnings,
        )

    fingerprint = _fingerprint_ordered_ohlcv(normalized_ticker, frame, dates)
    return HistorySnapshot(
        ticker=normalized_ticker,
        frame=frame,
        fingerprint=fingerprint,
        quality_state="display_only" if concerns else "eligible",
        requested_start=requested_start,
        requested_as_of=requested_as_of,
        first_date=first_date,
        as_of_date=as_of_date,
        evidence_prefix_fingerprint=fingerprint,
        quality_reasons=concerns,
        quality_warnings=warnings,
    )


def _snapshot_dates(snapshot: HistorySnapshot) -> tuple[date, ...]:
    dates = _parsed_dates(snapshot.frame)
    if dates is None or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("history snapshot does not contain ordered native dates")
    return tuple(value.date() for value in dates)


def make_evaluation_split(snapshot: HistorySnapshot) -> EvaluationSplit:
    """Create the one deterministic native-bar split for a usable snapshot."""

    if not isinstance(snapshot, HistorySnapshot):
        raise ValueError("snapshot must be a HistorySnapshot")
    if snapshot.quality_state == "invalid":
        raise ValueError("invalid history cannot create an evaluation split")
    dates = _snapshot_dates(snapshot)
    if len(dates) < 2:
        raise ValueError("evaluation split requires at least two native bars")

    full_window_start = _subtract_calendar_years(snapshot.requested_as_of, 15)
    full_window = dates[0] <= full_window_start + _FULL_WINDOW_START_TOLERANCE
    if full_window:
        cutoff = _subtract_calendar_years(snapshot.requested_as_of, 5)
        test_start_ordinal = next((
            ordinal for ordinal, native_date in enumerate(dates) if native_date >= cutoff
        ), None)
        if test_start_ordinal is None:
            raise ValueError("full calendar window has no native bar on or after cutoff")
        if test_start_ordinal == 0:
            raise ValueError("full calendar window has no native training bar before cutoff")
        return EvaluationSplit(
            method="calendar_10y_5y",
            requested_test_cutoff=cutoff,
            training=EvaluationPartition(
                label="training",
                start=dates[0],
                end=dates[test_start_ordinal - 1],
                start_ordinal=0,
                end_ordinal=test_start_ordinal - 1,
                row_count=test_start_ordinal,
            ),
            test=EvaluationPartition(
                label="test",
                start=dates[test_start_ordinal],
                end=dates[-1],
                start_ordinal=test_start_ordinal,
                end_ordinal=len(dates) - 1,
                row_count=len(dates) - test_start_ordinal,
            ),
        )

    training_count = math.floor(len(dates) * 0.65)
    if training_count < 1 or training_count >= len(dates):
        raise ValueError("short history cannot form a 65%/35% native split")
    return EvaluationSplit(
        method="chronological_65_35",
        requested_test_cutoff=None,
        training=EvaluationPartition(
            label="training",
            start=dates[0],
            end=dates[training_count - 1],
            start_ordinal=0,
            end_ordinal=training_count - 1,
            row_count=training_count,
        ),
        test=EvaluationPartition(
            label="test",
            start=dates[training_count],
            end=dates[-1],
            start_ordinal=training_count,
            end_ordinal=len(dates) - 1,
            row_count=len(dates) - training_count,
        ),
    )


def trade_dates_belong_to_partition(
    signal_date: date,
    entry_date: date,
    exit_date: date,
    partition: EvaluationPartition,
) -> bool:
    """Keep a completed trade only when all three causal dates share one split."""

    if not isinstance(partition, EvaluationPartition):
        raise ValueError("partition must be an EvaluationPartition")
    dates = (
        _date_only(signal_date, "signal_date"),
        _date_only(entry_date, "entry_date"),
        _date_only(exit_date, "exit_date"),
    )
    return all(partition.start <= value <= partition.end for value in dates)


def make_evidence_source_anchor(snapshot: HistorySnapshot) -> EvidenceSourceAnchor:
    """Capture immutable source bounds and prefix digest for later append proof."""

    if not isinstance(snapshot, HistorySnapshot):
        raise ValueError("snapshot must be a HistorySnapshot")
    if (
        snapshot.quality_state == "invalid"
        or snapshot.first_date is None
        or snapshot.as_of_date is None
        or snapshot.evidence_prefix_fingerprint is None
    ):
        raise ValueError("invalid history cannot create an evidence source anchor")
    return EvidenceSourceAnchor(
        ticker=snapshot.ticker,
        requested_start=snapshot.requested_start,
        requested_as_of=snapshot.requested_as_of,
        first_date=snapshot.first_date,
        as_of_date=snapshot.as_of_date,
        prefix_fingerprint=snapshot.evidence_prefix_fingerprint,
    )


def verify_evidence_source_anchor(
    engine: object,
    anchor: EvidenceSourceAnchor,
) -> Literal["match", "changed", "unavailable"]:
    """Reload an exact old range; appended data never substitutes its evidence."""

    if not isinstance(anchor, EvidenceSourceAnchor):
        raise ValueError("anchor must be an EvidenceSourceAnchor")
    try:
        snapshot = load_flexible_history(engine, anchor.ticker, as_of=anchor.requested_as_of)
    except Exception:
        return "unavailable"
    if (
        snapshot.quality_state == "invalid"
        or snapshot.first_date != anchor.first_date
        or snapshot.as_of_date != anchor.as_of_date
        or snapshot.requested_start != anchor.requested_start
        or snapshot.evidence_prefix_fingerprint is None
    ):
        return "unavailable"
    if snapshot.evidence_prefix_fingerprint != anchor.prefix_fingerprint:
        return "changed"
    return "match"
