"""Causal, Backtest-owned indicator inputs for immutable V3 rulebooks."""

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytz

from .config import HORIZONS, RulebookSpec, rulebook_for
from .data_quality import normalize_ohlc_for_backtest, validate_ohlcv


def _smma(values: pd.Series, period: int) -> pd.Series:
    """Return causal SMMA values seeded by the first complete simple average."""

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


def rsi_upcross(values: pd.Series, level: float) -> pd.Series:
    """Return the one-bar upward crossing event for a numeric RSI series."""

    numeric = pd.to_numeric(values, errors="coerce")
    return (numeric.ge(level) & numeric.shift(1).lt(level)).fillna(False).astype(bool)


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
    average_gain = gains.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()
    average_loss = losses.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()
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
    return true_range.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def _adx(working: pd.DataFrame, period: int) -> pd.Series:
    """Calculate causal ADX from local raw OHLCV inputs."""

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
    smooth_kwargs = {
        "alpha": 1.0 / period,
        "adjust": False,
        "min_periods": period,
    }
    average_true_range = true_range.ewm(**smooth_kwargs).mean()
    plus_di = 100.0 * plus_dm.ewm(**smooth_kwargs).mean() / average_true_range
    minus_di = 100.0 * minus_dm.ewm(**smooth_kwargs).mean() / average_true_range
    directional_index = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return directional_index.ewm(**smooth_kwargs).mean()


def _resample_weekly_w_fri(working: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Aggregate native daily bars to completed Friday-labelled weekly bars."""

    weekly = (
        working.sort_values("date")
        .set_index("date")
        .resample("W-FRI")
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
    return weekly.loc[weekly["date"] < pd.Timestamp(as_of_date)].reset_index(drop=True)


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
    today: date | None = None,
) -> pd.DataFrame:
    """Build one causal native-timeframe input frame for a canonical rulebook."""

    if not isinstance(rulebook, RulebookSpec):
        raise ValueError("rulebook must be a RulebookSpec")
    if rulebook != rulebook_for(rulebook.horizon):
        raise ValueError("rulebook must be registered for its horizon")
    quality = validate_ohlcv(ohlcv)
    if not quality.is_valid or quality.valid_frame is None:
        raise ValueError("invalid OHLCV data: " + "; ".join(quality.errors))

    as_of_date = today or datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).date()
    working = normalize_ohlc_for_backtest(quality.valid_frame)
    working["date"] = pd.to_datetime(working["date"])
    if rulebook.native_timeframe == "weekly":
        working = _resample_weekly_w_fri(working, as_of_date)
    else:
        working = working.reset_index(drop=True)

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
    adx = _adx(working, rulebook.adx_period)
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


def build_indicator_frame(ohlcv: pd.DataFrame, horizon: str) -> pd.DataFrame:
    """Return the V3 rulebook frame for callers migrating by horizon name."""

    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    return build_rulebook_frame(ohlcv, rulebook_for(horizon))


__all__ = [
    "build_indicator_frame",
    "build_rulebook_frame",
    "joint_trend_pass",
    "rsi_upcross",
]
