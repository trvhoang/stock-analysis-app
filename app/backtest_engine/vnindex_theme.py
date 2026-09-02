"""Optional VN-Index background-theme alignment and confirmation."""

from datetime import date

import pandas as pd

from commons import technical_analysis

from .config import HORIZONS, THEME_MODES
from .timeframes import to_weekly_ohlcv


def align_vnindex_asof(
    ticker_frame: pd.DataFrame,
    vnindex_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Attach only the latest VN-Index row dated on or before each ticker row."""

    if "date" not in ticker_frame or not {"date", "close"}.issubset(vnindex_frame.columns):
        raise ValueError("ticker and VN-Index frames require date; VN-Index requires close")

    ticker = ticker_frame.copy(deep=True)
    ticker["date"] = pd.to_datetime(ticker["date"])
    ticker["_original_order"] = range(len(ticker))
    ticker = ticker.sort_values("date")

    vnindex = vnindex_frame[["date", "close"]].copy(deep=True)
    vnindex["date"] = pd.to_datetime(vnindex["date"])
    vnindex = (
        vnindex.rename(columns={"date": "vnindex_date", "close": "vnindex_close"})
        .sort_values("vnindex_date")
    )

    aligned = pd.merge_asof(
        ticker,
        vnindex,
        left_on="date",
        right_on="vnindex_date",
        direction="backward",
    )
    return aligned.sort_values("_original_order").drop(columns="_original_order").reset_index(drop=True)


def build_vnindex_confirmation(
    vnindex_frame: pd.DataFrame,
    horizon: str,
    *,
    common_as_of: date,
) -> pd.Series:
    """Return ``close > SMA`` using the existing MA calculation path."""

    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    if not {"date", "close"}.issubset(vnindex_frame.columns):
        raise ValueError("VN-Index frame requires date and close columns")

    working = vnindex_frame.copy(deep=True)
    if horizon == "midterm":
        working = to_weekly_ohlcv(working, common_as_of=common_as_of)
        period = 20
    else:
        working["date"] = pd.to_datetime(working["date"])
        working = working.loc[
            working["date"].le(pd.Timestamp(common_as_of))
        ].reset_index(drop=True)
        period = 50

    working = technical_analysis.calculate_ma_cross(working, [(period, period)])
    sma = pd.to_numeric(working[f"SMA_{period}"], errors="coerce")
    close = pd.to_numeric(working["close"], errors="coerce")
    confirmation = (close > sma).fillna(False).rename("vnindex_trend_up")
    confirmation.index = pd.DatetimeIndex(working["date"])
    return confirmation


def combine_theme_signal(
    ticker_signal: pd.Series,
    theme_signal: pd.Series,
    mode: str | None,
) -> pd.Series:
    """Combine ticker and theme signals using the certified mode."""

    ticker = pd.Series(ticker_signal, copy=True).astype(bool)
    theme = pd.Series(theme_signal, copy=True).astype(bool)
    if mode is None:
        return ticker
    if mode not in THEME_MODES:
        raise ValueError(f"mode must be one of {THEME_MODES}")
    if len(ticker) != len(theme):
        raise ValueError("ticker and theme signals must have equal length")
    if mode == "AND":
        return ticker & theme
    return ticker | theme
