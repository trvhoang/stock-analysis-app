"""Shared OHLCV timeframe adapters for Backtest horizons."""

from collections.abc import Mapping
from datetime import date

import pandas as pd


def latest_common_completed_bar(
    sources: Mapping[str, pd.DataFrame],
    requested_end: date,
) -> date:
    """Return the latest date available to every named source by request end."""

    if not sources:
        raise ValueError("at least one named source is required")
    cutoff = pd.Timestamp(requested_end)
    latest: list[pd.Timestamp] = []
    for name, frame in sources.items():
        if not isinstance(frame, pd.DataFrame) or "date" not in frame:
            raise ValueError(f"{name} source requires a date column")
        dates = pd.to_datetime(frame["date"], errors="coerce")
        eligible = dates.loc[dates.notna() & dates.le(cutoff)]
        if eligible.empty:
            raise ValueError(f"{name} has no completed bar within request")
        latest.append(pd.Timestamp(eligible.max()))
    return min(latest).date()


def to_weekly_ohlcv(
    frame: pd.DataFrame,
    *,
    common_as_of: date,
) -> pd.DataFrame:
    """Aggregate only common-cutoff daily OHLCV into completed W-FRI bars."""

    working = frame.copy(deep=True)
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(working.columns))
    if missing:
        raise ValueError("weekly OHLCV requires columns: " + ", ".join(missing))
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if working["date"].isna().any():
        raise ValueError("weekly OHLCV date contains missing or invalid values")
    cutoff = pd.Timestamp(common_as_of)
    working = working.loc[working["date"].le(cutoff)]
    working = working.sort_values("date").set_index("date")
    weekly = (
        working.resample("W-FRI", label="right", closed="right")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    return weekly.loc[weekly["date"].le(cutoff)].reset_index(drop=True)


__all__ = ["latest_common_completed_bar", "to_weekly_ohlcv"]
