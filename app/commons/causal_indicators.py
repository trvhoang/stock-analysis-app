"""Authoritative causal technical-indicator primitives.

These primitives use only completed native OHLCV bars.  They deliberately
return aligned ``NaN`` values through warm-up or unavailable input rather than
forward filling a value that could manufacture a signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


SUPERTREND_FORMULA_ID = "supertrend-hl2-wilder-v1"


def _numeric(values: pd.Series) -> pd.Series:
    """Return one float series without changing its caller-owned object."""

    return pd.to_numeric(values, errors="coerce").astype(float)


def _nan_series(index: pd.Index, *, name: str | None = None) -> pd.Series:
    return pd.Series(float("nan"), index=index, dtype=float, name=name)


def _nan_frame(index: pd.Index, columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame({column: _nan_series(index) for column in columns}, index=index)


def sma(close: pd.Series, period: int) -> pd.Series:
    """Return the arithmetic mean of the last ``period`` completed closes."""

    values = _numeric(close)
    return values.rolling(period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    """Return the Backtest-compatible ``adjust=False`` EMA."""

    values = _numeric(close)
    return values.ewm(span=period, adjust=False, min_periods=period).mean()


def wilder_average(values: pd.Series, period: int, *, seed_start: int = 0) -> pd.Series:
    """Return an exact SMA-seeded Wilder recurrence aligned to ``values``."""

    numeric = _numeric(values)
    result = np.full(len(numeric), np.nan, dtype=float)
    seed_end = seed_start + period
    if period < 1 or seed_start < 0 or len(numeric) < seed_end:
        return pd.Series(result, index=numeric.index, dtype=float)

    source = numeric.to_numpy(dtype=float)
    seed = source[seed_start:seed_end]
    if not np.isfinite(seed).all():
        return pd.Series(result, index=numeric.index, dtype=float)

    result[seed_end - 1] = float(numeric.iloc[seed_start:seed_end].mean())
    for position in range(seed_end, len(source)):
        previous = result[position - 1]
        current = source[position]
        if np.isfinite(previous) and np.isfinite(current):
            result[position] = (previous * (period - 1) + current) / period
    return pd.Series(result, index=numeric.index, dtype=float)


def smma(values: pd.Series, period: int) -> pd.Series:
    """Return the project SMMA: SMA seed followed by Wilder recurrence."""

    return wilder_average(values, period, seed_start=0)


def true_range(ohlcv: pd.DataFrame) -> pd.Series:
    """Return causal true range; the first completed bar uses high minus low."""

    required = {"high", "low", "close"}
    if not required.issubset(ohlcv.columns):
        return _nan_series(ohlcv.index)
    high = _numeric(ohlcv["high"])
    low = _numeric(ohlcv["low"])
    close = _numeric(ohlcv["close"])
    previous_close = close.shift(1)
    values = pd.concat(
        (high - low, (high - previous_close).abs(), (low - previous_close).abs()),
        axis=1,
    ).max(axis=1)
    if len(values):
        values.iloc[0] = (high - low).iloc[0]
    return values.astype(float)


def rsi(close: pd.Series, period: int) -> pd.Series:
    """Return exact SMA-seeded Wilder RSI, retaining defined flat-market 100."""

    values = _numeric(close)
    delta = values.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    average_gain = wilder_average(gains, period, seed_start=1)
    average_loss = wilder_average(losses, period, seed_start=1)
    relative_strength = average_gain / average_loss
    result = 100.0 - 100.0 / (1.0 + relative_strength)
    result = result.where(average_loss.ne(0.0), 100.0)
    return result.where(average_gain.notna() & average_loss.notna())


def atr(ohlcv: pd.DataFrame, period: int) -> pd.Series:
    """Return exact SMA-seeded Wilder ATR from causal true range."""

    return wilder_average(true_range(ohlcv), period, seed_start=0)


def adx_dmi(ohlcv: pd.DataFrame, period: int) -> pd.DataFrame:
    """Return exact SMA-seeded Wilder ADX with +DI and -DI."""

    columns = ("adx", "plus_di", "minus_di")
    required = {"high", "low", "close"}
    if not required.issubset(ohlcv.columns):
        return _nan_frame(ohlcv.index, columns)

    high = _numeric(ohlcv["high"])
    low = _numeric(ohlcv["low"])
    previous_high = high.shift(1)
    previous_low = low.shift(1)
    upward_move = high - previous_high
    downward_move = previous_low - low
    plus_dm = upward_move.where((upward_move > downward_move) & (upward_move > 0), 0.0)
    minus_dm = downward_move.where((downward_move > upward_move) & (downward_move > 0), 0.0)
    average_true_range = wilder_average(true_range(ohlcv), period, seed_start=0)
    average_plus_dm = wilder_average(plus_dm, period, seed_start=0)
    average_minus_dm = wilder_average(minus_dm, period, seed_start=0)
    plus_di = 100.0 * average_plus_dm / average_true_range
    minus_di = 100.0 * average_minus_dm / average_true_range
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = wilder_average(dx, period, seed_start=period - 1)
    return pd.DataFrame({"adx": adx, "plus_di": plus_di, "minus_di": minus_di}, index=ohlcv.index)


def alligator_hl2(
    ohlcv: pd.DataFrame,
    *,
    jaw_period: int,
    teeth_period: int,
    lips_period: int,
    jaw_offset: int,
    teeth_offset: int,
    lips_offset: int,
) -> pd.DataFrame:
    """Return causal HL2 Alligator lines; offsets expose only prior values."""

    if not {"high", "low"}.issubset(ohlcv.columns):
        return _nan_frame(ohlcv.index, ("jaw", "teeth", "lips"))
    hl2 = (_numeric(ohlcv["high"]) + _numeric(ohlcv["low"])) / 2.0
    return pd.DataFrame(
        {
            "jaw": smma(hl2, jaw_period).shift(jaw_offset),
            "teeth": smma(hl2, teeth_period).shift(teeth_offset),
            "lips": smma(hl2, lips_period).shift(lips_offset),
        },
        index=ohlcv.index,
    )


def stochastic(
    ohlcv: pd.DataFrame,
    *,
    k_period: int,
    k_smoothing: int,
    d_period: int,
) -> pd.DataFrame:
    """Return raw %K, SMA-smoothed %K, and SMA %D from completed bars."""

    if not {"high", "low", "close"}.issubset(ohlcv.columns):
        return _nan_frame(ohlcv.index, ("raw_k", "k", "d"))
    high = _numeric(ohlcv["high"])
    low = _numeric(ohlcv["low"])
    close = _numeric(ohlcv["close"])
    lowest = low.rolling(k_period, min_periods=k_period).min()
    highest = high.rolling(k_period, min_periods=k_period).max()
    width = highest - lowest
    raw_k = (100.0 * (close - lowest) / width).where(width.ne(0.0))
    k = raw_k.rolling(k_smoothing, min_periods=k_smoothing).mean()
    d = k.rolling(d_period, min_periods=d_period).mean()
    return pd.DataFrame({"raw_k": raw_k, "k": k, "d": d}, index=ohlcv.index)


def relative_volume(volume: pd.Series, period: int) -> pd.DataFrame:
    """Compare current volume with a prior-only average, never its own bar."""

    values = _numeric(volume)
    baseline = values.shift(1).rolling(period, min_periods=period).mean()
    return pd.DataFrame(
        {
            "baseline": baseline,
            "relative_volume": (values / baseline).where(baseline.ne(0.0)),
        },
        index=values.index,
    )


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Return close-direction OBV with an explicit zero at the first bar."""

    values = _numeric(close)
    amounts = _numeric(volume)
    return (np.sign(values.diff()).fillna(0.0) * amounts).cumsum().astype(float)


def prior_extrema(ohlcv: pd.DataFrame, period: int) -> pd.DataFrame:
    """Return prior-only high/low extrema for causal breakout rules."""

    if not {"high", "low"}.issubset(ohlcv.columns):
        return _nan_frame(ohlcv.index, ("prior_high", "prior_low"))
    return pd.DataFrame(
        {
            "prior_high": _numeric(ohlcv["high"]).shift(1).rolling(period, min_periods=period).max(),
            "prior_low": _numeric(ohlcv["low"]).shift(1).rolling(period, min_periods=period).min(),
        },
        index=ohlcv.index,
    )


def bollinger(close: pd.Series, period: int, multiplier: float) -> pd.DataFrame:
    """Return sample-standard-deviation Bollinger components from close."""

    values = _numeric(close)
    middle = values.rolling(period, min_periods=period).mean()
    deviation = values.rolling(period, min_periods=period).std(ddof=1)
    upper = middle + multiplier * deviation
    lower = middle - multiplier * deviation
    width = upper - lower
    bandwidth = (width / middle * 100.0).where(middle.ne(0.0))
    percent_b = ((values - lower) / width).where(width.ne(0.0))
    return pd.DataFrame(
        {
            "middle": middle,
            "upper": upper,
            "lower": lower,
            "bandwidth": bandwidth,
            "percent_b": percent_b,
        },
        index=values.index,
    )


def supertrend(ohlcv: pd.DataFrame, *, period: int, multiplier: float) -> pd.DataFrame:
    """Return completed-bar HL2/Wilder Supertrend using the versioned recurrence."""

    columns = ("basic_upper", "basic_lower", "final_upper", "final_lower", "direction", "supertrend")
    if not {"high", "low", "close"}.issubset(ohlcv.columns):
        return _nan_frame(ohlcv.index, columns)

    high = _numeric(ohlcv["high"])
    low = _numeric(ohlcv["low"])
    close = _numeric(ohlcv["close"])
    atr_values = atr(ohlcv, period)
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr_values
    basic_lower = hl2 - multiplier * atr_values
    final_upper = np.full(len(ohlcv), np.nan, dtype=float)
    final_lower = np.full(len(ohlcv), np.nan, dtype=float)
    direction = np.full(len(ohlcv), np.nan, dtype=float)
    values_upper = basic_upper.to_numpy(dtype=float)
    values_lower = basic_lower.to_numpy(dtype=float)
    values_close = close.to_numpy(dtype=float)

    for position in range(len(ohlcv)):
        upper = values_upper[position]
        lower = values_lower[position]
        if not np.isfinite(upper) or not np.isfinite(lower) or not np.isfinite(values_close[position]):
            continue
        if position == 0 or not np.isfinite(final_upper[position - 1]):
            final_upper[position] = upper
            final_lower[position] = lower
            direction[position] = 1.0
            continue
        prior_upper = final_upper[position - 1]
        prior_lower = final_lower[position - 1]
        prior_close = values_close[position - 1]
        final_upper[position] = upper if upper < prior_upper or prior_close > prior_upper else prior_upper
        final_lower[position] = lower if lower > prior_lower or prior_close < prior_lower else prior_lower
        if values_close[position] > prior_upper:
            direction[position] = 1.0
        elif values_close[position] < prior_lower:
            direction[position] = -1.0
        else:
            direction[position] = direction[position - 1]

    direction_series = pd.Series(direction, index=ohlcv.index, dtype=float)
    upper_series = pd.Series(final_upper, index=ohlcv.index, dtype=float)
    lower_series = pd.Series(final_lower, index=ohlcv.index, dtype=float)
    line = lower_series.where(direction_series.eq(1.0), upper_series)
    return pd.DataFrame(
        {
            "basic_upper": basic_upper,
            "basic_lower": basic_lower,
            "final_upper": upper_series,
            "final_lower": lower_series,
            "direction": direction_series,
            "supertrend": line,
        },
        index=ohlcv.index,
    )


__all__ = [
    "SUPERTREND_FORMULA_ID",
    "adx_dmi",
    "alligator_hl2",
    "atr",
    "bollinger",
    "ema",
    "obv",
    "prior_extrema",
    "relative_volume",
    "rsi",
    "sma",
    "smma",
    "stochastic",
    "supertrend",
    "true_range",
    "wilder_average",
]
