"""Causal, Backtest-owned indicator inputs for immutable V3 rulebooks."""

from datetime import date

import numpy as np
import pandas as pd

from .config import HORIZONS, RulebookSpec, rulebook_for
from .data_quality import normalize_ohlc_for_backtest, validate_ohlcv
from .timeframes import to_weekly_ohlcv


def _smma_reference(values: pd.Series, period: int) -> pd.Series:
    """Return the row-based SMMA retained as the exact parity oracle."""

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    result = pd.Series(float("nan"), index=numeric.index, dtype=float)
    if len(numeric) < period:
        return result

    result.iloc[period - 1] = numeric.iloc[:period].mean()
    for position in range(period, len(numeric)):
        prior = result.iloc[position - 1]
        value = numeric.iloc[position]
        if not np.isfinite(prior) or not np.isfinite(value):
            continue
        result.iloc[position] = (prior * (period - 1) + value) / period
    return result


def _smma(values: pd.Series, period: int) -> pd.Series:
    """Return causal SMMA using an indexed array and the reference seed."""

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    result = np.full(len(numeric), np.nan, dtype=float)
    if len(numeric) < period:
        return pd.Series(result, index=numeric.index, dtype=float)

    source = numeric.to_numpy(dtype=float)
    result[period - 1] = numeric.iloc[:period].mean()
    for position in range(period, len(source)):
        prior = result[position - 1]
        value = source[position]
        if not np.isfinite(prior) or not np.isfinite(value):
            continue
        result[position] = (prior * (period - 1) + value) / period
    return pd.Series(result, index=numeric.index, dtype=float)


def _wilder_average_reference(
    values: pd.Series,
    period: int,
    *,
    seed_start: int,
) -> pd.Series:
    """Return the row-based Wilder average retained as the parity oracle."""

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    result = pd.Series(float("nan"), index=numeric.index, dtype=float)
    seed_end = seed_start + period
    if period < 1 or seed_start < 0 or len(numeric) < seed_end:
        return result
    seed = numeric.iloc[seed_start:seed_end]
    if not np.isfinite(seed.to_numpy(dtype=float)).all():
        return result
    result.iloc[seed_end - 1] = float(seed.mean())
    for position in range(seed_end, len(numeric)):
        prior = result.iloc[position - 1]
        current = numeric.iloc[position]
        if not np.isfinite(prior) or not np.isfinite(current):
            continue
        result.iloc[position] = (prior * (period - 1) + current) / period
    return result


def _wilder_average(
    values: pd.Series,
    period: int,
    *,
    seed_start: int,
) -> pd.Series:
    """Return an exact SMA-seeded Wilder average over an indexed array."""

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    result = np.full(len(numeric), np.nan, dtype=float)
    seed_end = seed_start + period
    if period < 1 or seed_start < 0 or len(numeric) < seed_end:
        return pd.Series(result, index=numeric.index, dtype=float)

    source = numeric.to_numpy(dtype=float)
    seed = source[seed_start:seed_end]
    if not np.isfinite(seed).all():
        return pd.Series(result, index=numeric.index, dtype=float)
    # Use pandas' seed reduction so the optimized recurrence starts bit-exactly.
    result[seed_end - 1] = float(numeric.iloc[seed_start:seed_end].mean())
    for position in range(seed_end, len(source)):
        prior = result[position - 1]
        current = source[position]
        if not np.isfinite(prior) or not np.isfinite(current):
            continue
        result[position] = (prior * (period - 1) + current) / period
    return pd.Series(result, index=numeric.index, dtype=float)


def rsi_upcross(values: pd.Series, level: float) -> pd.Series:
    """Return the one-bar upward crossing event for a numeric RSI series."""

    numeric = pd.to_numeric(values, errors="coerce")
    return (numeric.ge(level) & numeric.shift(1).lt(level)).fillna(False).astype(bool)


def series_upcross(left: pd.Series, right: pd.Series) -> pd.Series:
    """Return a causal one-bar event when left crosses strictly above right."""

    left_values = pd.to_numeric(left, errors="coerce")
    right_values = pd.to_numeric(right, errors="coerce")
    if not left_values.index.equals(right_values.index):
        raise ValueError("upcross inputs must share one index")
    return (
        left_values.gt(right_values)
        & left_values.shift(1).le(right_values.shift(1))
    ).fillna(False).astype(bool)


def joint_trend_pass(ma_point, alligator_point):
    """Require strict local Up labels from both MA and Alligator trend inputs."""

    if isinstance(ma_point, pd.Series) or isinstance(alligator_point, pd.Series):
        ma_values = pd.to_numeric(ma_point, errors="coerce")
        alligator_values = pd.to_numeric(alligator_point, errors="coerce")
        return (ma_values.ge(3) & alligator_values.ge(3)).fillna(False).astype(bool)
    try:
        return bool(float(ma_point) >= 3 and float(alligator_point) >= 3)
    except (TypeError, ValueError):
        return False


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """Calculate causal Wilder RSI without importing any Analyze helper."""

    values = pd.to_numeric(close, errors="coerce").astype(float)
    delta = values.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    average_gain = _wilder_average(gains, period, seed_start=1)
    average_loss = _wilder_average(losses, period, seed_start=1)
    relative_strength = average_gain / average_loss
    result = 100.0 - 100.0 / (1.0 + relative_strength)
    result = result.where(average_loss.ne(0.0), 100.0)
    return result.where(average_gain.notna() & average_loss.notna())


def _atr(working: pd.DataFrame, period: int) -> pd.Series:
    """Calculate causal raw-price Wilder ATR from OHLCV bars."""

    high = pd.to_numeric(working["high"], errors="coerce").astype(float)
    low = pd.to_numeric(working["low"], errors="coerce").astype(float)
    close = pd.to_numeric(working["close"], errors="coerce").astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        (high - low, (high - previous_close).abs(), (low - previous_close).abs()),
        axis=1,
    ).max(axis=1)
    return _wilder_average(true_range, period, seed_start=0)


def _adx_components(
    working: pd.DataFrame,
    period: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate exact SMA-seeded Wilder +DI, -DI, and ADX."""

    high = pd.to_numeric(working["high"], errors="coerce").astype(float)
    low = pd.to_numeric(working["low"], errors="coerce").astype(float)
    close = pd.to_numeric(working["close"], errors="coerce").astype(float)
    previous_high = high.shift(1)
    previous_low = low.shift(1)
    previous_close = close.shift(1)
    upward_move = high - previous_high
    downward_move = previous_low - low
    plus_dm = upward_move.where((upward_move > downward_move) & (upward_move > 0), 0.0)
    minus_dm = downward_move.where((downward_move > upward_move) & (downward_move > 0), 0.0)
    true_range = pd.concat(
        (high - low, (high - previous_close).abs(), (low - previous_close).abs()),
        axis=1,
    ).max(axis=1)
    average_true_range = _wilder_average(true_range, period, seed_start=0)
    average_plus_dm = _wilder_average(plus_dm, period, seed_start=0)
    average_minus_dm = _wilder_average(minus_dm, period, seed_start=0)
    plus_di = 100.0 * average_plus_dm / average_true_range
    minus_di = 100.0 * average_minus_dm / average_true_range
    directional_index = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = _wilder_average(directional_index, period, seed_start=period - 1)
    return plus_di, minus_di, adx


def _adx(working: pd.DataFrame, period: int) -> pd.Series:
    """Calculate exact SMA-seeded Wilder ADX from local raw OHLCV inputs."""

    return _adx_components(working, period)[2]


def _moving_average(close: pd.Series, rulebook: RulebookSpec) -> tuple[pd.Series, pd.Series]:
    fast_period, slow_period = rulebook.ma_pair
    values = pd.to_numeric(close, errors="coerce").astype(float)
    if rulebook.ma_kind == "EMA":
        return (
            values.ewm(span=fast_period, adjust=False, min_periods=fast_period).mean(),
            values.ewm(span=slow_period, adjust=False, min_periods=slow_period).mean(),
        )
    return (
        values.rolling(fast_period, min_periods=fast_period).mean(),
        values.rolling(slow_period, min_periods=slow_period).mean(),
    )


def _trend_point(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """Map local strict MA/Alligator ordering to Down=1, Sideways=2, Up=3."""

    point = pd.Series(float("nan"), index=fast.index, dtype=float)
    available = fast.notna() & slow.notna()
    point.loc[available & fast.lt(slow)] = 1.0
    point.loc[available & fast.eq(slow)] = 2.0
    point.loc[available & fast.gt(slow)] = 3.0
    return point


def _alligator_point(
    lips: pd.Series,
    teeth: pd.Series,
    jaw: pd.Series,
) -> pd.Series:
    """Map strict three-line Alligator order to Down=1, Sideways=2, Up=3."""

    point = pd.Series(float("nan"), index=lips.index, dtype=float)
    available = lips.notna() & teeth.notna() & jaw.notna()
    point.loc[available & lips.lt(teeth) & teeth.lt(jaw)] = 1.0
    point.loc[available & lips.gt(teeth) & teeth.gt(jaw)] = 3.0
    point.loc[available & point.isna()] = 2.0
    return point


def build_rulebook_frame(
    ohlcv: pd.DataFrame,
    rulebook: RulebookSpec,
    *,
    common_as_of: date,
) -> pd.DataFrame:
    """Build one causal native-timeframe input frame for a canonical rulebook."""

    if not isinstance(rulebook, RulebookSpec):
        raise ValueError("rulebook must be a RulebookSpec")
    if rulebook != rulebook_for(rulebook.horizon):
        raise ValueError("rulebook must be registered for its horizon")
    quality = validate_ohlcv(ohlcv)
    if not quality.is_valid or quality.valid_frame is None:
        raise ValueError("invalid OHLCV data: " + "; ".join(quality.errors))

    working = normalize_ohlc_for_backtest(quality.valid_frame)
    working["date"] = pd.to_datetime(working["date"])
    working = working.loc[
        working["date"].le(pd.Timestamp(common_as_of))
    ].reset_index(drop=True)
    if rulebook.native_timeframe == "weekly":
        working = to_weekly_ohlcv(working, common_as_of=common_as_of)

    fast_ma, slow_ma = _moving_average(working["close"], rulebook)
    jaw_period, teeth_period, lips_period = rulebook.alligator_periods
    jaw_lag, teeth_lag, lips_lag = rulebook.alligator_lags
    close = pd.to_numeric(working["close"], errors="coerce")
    alligator_jaw = _smma(close, jaw_period).shift(jaw_lag)
    alligator_teeth = _smma(close, teeth_period).shift(teeth_lag)
    alligator_lips = _smma(close, lips_period).shift(lips_lag)
    ma_point = _trend_point(fast_ma, slow_ma)
    alligator_point = _alligator_point(
        alligator_lips,
        alligator_teeth,
        alligator_jaw,
    )
    rsi = _rsi(close, rulebook.rsi_period)
    volume = pd.to_numeric(working["volume"], errors="coerce").astype(float)
    volume_baseline = volume.shift(1).rolling(
        rulebook.volume_window,
        min_periods=rulebook.volume_window,
    ).mean()
    plus_di, minus_di, adx = _adx_components(working, rulebook.adx_period)
    atr = _atr(working, rulebook.atr_period)

    working["rulebook_ma_fast"] = fast_ma
    working["rulebook_ma_slow"] = slow_ma
    working["rulebook_ma_point"] = ma_point
    working["rulebook_alligator_jaw"] = alligator_jaw
    working["rulebook_alligator_teeth"] = alligator_teeth
    working["rulebook_alligator_lips"] = alligator_lips
    working["rulebook_alligator_point"] = alligator_point
    working["rulebook_rsi"] = rsi
    working["rulebook_volume_baseline"] = volume_baseline
    working["rulebook_plus_di_14"] = plus_di
    working["rulebook_minus_di_14"] = minus_di
    working["rulebook_adx_14"] = adx
    working["ATR_14"] = atr

    required_input = working[
        [
            "rulebook_ma_fast",
            "rulebook_ma_slow",
            "rulebook_alligator_jaw",
            "rulebook_alligator_teeth",
            "rulebook_alligator_lips",
            "rulebook_rsi",
            "volume",
            "rulebook_volume_baseline",
            "rulebook_adx_14",
            "ATR_14",
        ]
    ].apply(pd.to_numeric, errors="coerce")
    missing_required_input = ~pd.DataFrame(
        np.isfinite(required_input.to_numpy(dtype=float)),
        index=working.index,
        columns=required_input.columns,
    ).all(axis=1)
    working["rulebook_missing_required_input"] = missing_required_input.astype(bool)
    working["rulebook_rsi_upcross"] = rsi_upcross(rsi, rulebook.rsi_upcross_level)
    working["rulebook_joint_trend_pass"] = joint_trend_pass(ma_point, alligator_point)
    working["rulebook_volume_gate"] = (
        volume.ge(volume_baseline * rulebook.volume_multiplier)
    ).fillna(False).astype(bool)
    working["rulebook_adx_gate"] = adx.ge(rulebook.adx_minimum).fillna(False).astype(bool)
    return working


def build_indicator_frame(
    ohlcv: pd.DataFrame,
    horizon: str,
    *,
    common_as_of: date,
) -> pd.DataFrame:
    """Return the V3 rulebook frame for callers migrating by horizon name."""

    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    return build_rulebook_frame(
        ohlcv,
        rulebook_for(horizon),
        common_as_of=common_as_of,
    )


__all__ = [
    "build_indicator_frame",
    "build_rulebook_frame",
    "joint_trend_pass",
    "rsi_upcross",
    "series_upcross",
]
