"""VN-Index-defined trading sessions for production technical inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from typing import Final

import numpy as np
import pandas as pd
from sqlalchemy import text


_RAW_COLUMNS: Final = ("open", "high", "low", "close", "volume")
_REQUIRED_COLUMNS: Final = ("date", *_RAW_COLUMNS)
_CALENDAR_REVISION: Final = "vnindex-session-calendar-v1"


class VNIndexCalendarUnavailable(ValueError):
    """Fail-closed error with exact, bounded missing VN-Index weekdays."""

    def __init__(
        self,
        reason: str,
        missing_sessions: tuple[date, ...] = (),
    ) -> None:
        self.reason = reason
        self.missing_sessions = missing_sessions
        dates = ", ".join(value.isoformat() for value in missing_sessions)
        detail = f" Missing weekday VN-Index sessions: {dates}." if dates else ""
        super().__init__(f"VN-Index session calendar unavailable: {reason}.{detail}")


@dataclass(frozen=True)
class VNIndexCalendar:
    """Immutable source-backed session set for one requested date interval."""

    sessions: tuple[date, ...]
    assumed_non_sessions: tuple[date, ...]
    first_date: date
    last_date: date
    fingerprint: str


def _date_only(value: object, name: str) -> date:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"{name} must be a valid date")
    return pd.Timestamp(parsed).date()


def _weekday_dates(start: date, end: date) -> tuple[date, ...]:
    if start > end:
        return ()
    return tuple(
        value.date()
        for value in pd.bdate_range(pd.Timestamp(start), pd.Timestamp(end))
    )


def _canonical_vnindex_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate raw VN-Index rows without mutating a caller-owned frame."""

    if not isinstance(frame, pd.DataFrame):
        raise VNIndexCalendarUnavailable("invalid_vnindex_source")
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame]
    if missing:
        raise VNIndexCalendarUnavailable("invalid_vnindex_source")
    working = frame.loc[:, _REQUIRED_COLUMNS].copy(deep=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if working["date"].isna().any() or working["date"].duplicated().any():
        raise VNIndexCalendarUnavailable("invalid_vnindex_source")
    for column in _RAW_COLUMNS:
        values = pd.to_numeric(working[column], errors="coerce")
        numeric = values.to_numpy(dtype=float)
        if not np.isfinite(numeric).all() or not np.equal(numeric, np.floor(numeric)).all():
            raise VNIndexCalendarUnavailable("invalid_vnindex_source")
        working[column] = values.map(int)
    if (working[["open", "high", "low", "close"]] <= 0).any().any() or (working["volume"] < 0).any():
        raise VNIndexCalendarUnavailable("invalid_vnindex_source")
    return working.sort_values("date").reset_index(drop=True)


def _calendar_fingerprint(sessions: tuple[date, ...]) -> str:
    digest = hashlib.sha256()
    digest.update((_CALENDAR_REVISION + "\n").encode("utf-8"))
    for session in sessions:
        digest.update((session.isoformat() + "\n").encode("utf-8"))
    return digest.hexdigest()


def build_vnindex_calendar(
    vnindex_raw: pd.DataFrame,
    *,
    start: object,
    end: object,
) -> VNIndexCalendar:
    """Build the sole weekday session calendar from usable VN-Index rows."""

    requested_start = _date_only(start, "start")
    requested_end = _date_only(end, "end")
    if requested_start > requested_end:
        raise ValueError("start must not be after end")
    working = _canonical_vnindex_rows(vnindex_raw)
    bounded = working.loc[
        working["date"].between(pd.Timestamp(requested_start), pd.Timestamp(requested_end))
    ].copy()
    if bounded.empty:
        raise VNIndexCalendarUnavailable(
            "missing_vnindex_history",
            _weekday_dates(requested_start, requested_end),
        )
    weekend = bounded.loc[bounded["date"].dt.weekday.ge(5), "date"]
    if not weekend.empty:
        raise VNIndexCalendarUnavailable("invalid_vnindex_weekend_row")
    sessions = tuple(value.date() for value in bounded["date"])
    first_date, last_date = sessions[0], sessions[-1]
    session_set = set(sessions)
    assumed_non_sessions = tuple(
        value
        for value in _weekday_dates(max(requested_start, first_date), min(requested_end, last_date))
        if value not in session_set
    )
    return VNIndexCalendar(
        sessions=sessions,
        assumed_non_sessions=assumed_non_sessions,
        first_date=first_date,
        last_date=last_date,
        fingerprint=_calendar_fingerprint(sessions),
    )


def restrict_to_vnindex_sessions(
    ticker_raw: pd.DataFrame,
    calendar: VNIndexCalendar,
) -> tuple[pd.DataFrame, tuple[date, ...]]:
    """Return sorted ticker rows on the canonical sessions plus excluded dates."""

    if not isinstance(ticker_raw, pd.DataFrame) or "date" not in ticker_raw:
        raise ValueError("ticker history requires a date column")
    if not isinstance(calendar, VNIndexCalendar):
        raise ValueError("calendar must be a VNIndexCalendar")
    working = ticker_raw.copy(deep=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if working["date"].isna().any():
        raise ValueError("ticker history contains an invalid date")
    sessions = set(calendar.sessions)
    dates = working["date"].dt.date
    outside = tuple(sorted(set(dates.loc[~dates.isin(sessions)])))
    filtered = working.loc[dates.isin(sessions)].copy()
    return filtered.sort_values("date").reset_index(drop=True), outside


def align_to_vnindex_calendar(
    ticker_raw: pd.DataFrame,
    vnindex_raw: pd.DataFrame,
    *,
    start: object,
    end: object,
) -> tuple[pd.DataFrame, VNIndexCalendar, tuple[date, ...]]:
    """Filter one ticker to the usable VN-Index calendar or fail closed."""

    requested_start = _date_only(start, "start")
    requested_end = _date_only(end, "end")
    calendar = build_vnindex_calendar(
        vnindex_raw,
        start=requested_start,
        end=requested_end,
    )
    filtered, outside = restrict_to_vnindex_sessions(ticker_raw, calendar)
    if filtered.empty:
        session_set = set(calendar.sessions)
        raise VNIndexCalendarUnavailable(
            "no_usable_overlap",
            tuple(
                value
                for value in _weekday_dates(requested_start, requested_end)
                if value not in session_set
            ),
        )
    return filtered, calendar, outside


def _load_raw_history(
    engine: object,
    ticker: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Load one bounded raw OHLCV source through the project DBAPI pattern."""

    statement = text(
        """
        SELECT date, open, high, low, close, volume
        FROM trading_data
        WHERE ticker = %(ticker)s
          AND date >= %(start)s
          AND date <= %(end)s
        ORDER BY date ASC
        """
    )
    connection = engine.raw_connection()
    try:
        return pd.read_sql(
            statement.text,
            connection,
            params={"ticker": ticker, "start": start, "end": end},
        )
    finally:
        connection.close()


def load_calendar_aligned_history(
    engine: object,
    ticker: str,
    *,
    start: object,
    end: object,
) -> tuple[pd.DataFrame, VNIndexCalendar, tuple[date, ...]]:
    """Load ticker/VN-Index rows and filter ticker input before indicators."""

    requested_start = _date_only(start, "start")
    requested_end = _date_only(end, "end")
    if requested_start > requested_end:
        raise ValueError("start must not be after end")
    normalized = str(ticker or "").strip().upper()
    if not normalized:
        raise ValueError("ticker must be non-empty")
    ticker_raw = _load_raw_history(engine, normalized, requested_start, requested_end)
    vnindex_raw = _load_raw_history(engine, "VNINDEX", requested_start, requested_end)
    filtered, calendar, outside = align_to_vnindex_calendar(
        ticker_raw,
        vnindex_raw,
        start=requested_start,
        end=requested_end,
    )
    return filtered, calendar, outside


__all__ = [
    "VNIndexCalendar",
    "VNIndexCalendarUnavailable",
    "align_to_vnindex_calendar",
    "build_vnindex_calendar",
    "load_calendar_aligned_history",
    "restrict_to_vnindex_sessions",
]
