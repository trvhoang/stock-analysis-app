"""Shared OHLCV timeframe adapters for Backtest horizons."""

import pandas as pd


def to_weekly_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily OHLCV into date-sorted weekly bars."""

    working = frame.copy(deep=True)
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values("date").set_index("date")
    return (
        working.resample("W")
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
