"""Causal daily raw-array features for isolated Flexible Rulebook research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd

from .contracts import (
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    FeatureResolutionReceipt,
    FeatureSnapshot,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
)
from .history import HistorySnapshot
from .primitive_cache import CachedComponent, safe_read_component, try_write_component


_SUPPORTED_FAMILIES = frozenset({"adx", "atr", "breakout", "ema", "relative_volume", "rsi"})
_CACHE_REUSE_MAX_AGE = timedelta(hours=24)


def _readonly(values: np.ndarray) -> np.ndarray:
    """Return an owned C-order read-only array, never a raw-frame view."""

    result = np.array(values, copy=True, order="C")
    result.setflags(write=False)
    return result


def _integer_column(frame: pd.DataFrame, column: str) -> np.ndarray:
    """Copy one raw BIGINT source column without scale conversion or truncation."""

    source = frame[column].to_numpy(copy=True)
    result = np.empty(source.size, dtype=np.int64)
    lower, upper = np.iinfo(np.int64).min, np.iinfo(np.int64).max
    for index, value in enumerate(source):
        if isinstance(value, (bool, np.bool_)):
            raise ValueError(f"{column} must contain finite raw integer values")
        try:
            integer = int(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"{column} must contain finite raw integer values") from error
        if isinstance(value, (float, np.floating)) and (not math.isfinite(float(value)) or float(value) != integer):
            raise ValueError(f"{column} must contain finite raw integer values")
        if isinstance(value, Decimal) and (not value.is_finite() or value != Decimal(integer)):
            raise ValueError(f"{column} must contain finite raw integer values")
        if not lower <= integer <= upper:
            raise ValueError(f"{column} exceeds raw BIGINT range")
        result[index] = integer
    return _readonly(result)


def _setting(spec: PrimitiveSpec, name: str) -> int:
    settings = dict(spec.settings)
    value = settings.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{spec.family}.{name} must be a positive integer")
    return value


def _validate_spec(spec: PrimitiveSpec) -> None:
    """Validate approved-family primitives without selecting catalog-v1 values."""

    if spec.family not in _SUPPORTED_FAMILIES:
        raise ValueError(f"unsupported Flexible primitive family: {spec.family}")
    settings = dict(spec.settings)
    if spec.family == "ema":
        keys = set(settings)
        if keys == {"period"}:
            _setting(spec, "period")
        elif keys == {"fast_period", "slow_period"}:
            if _setting(spec, "fast_period") >= _setting(spec, "slow_period"):
                raise ValueError("ema fast_period must be less than slow_period")
        else:
            raise ValueError("ema settings must be period or fast_period/slow_period")
        return
    expected = {"lookback"} if spec.family == "breakout" else {"window"} if spec.family == "relative_volume" else {"period"}
    if set(settings) != expected:
        raise ValueError(f"{spec.family} settings must be exactly {sorted(expected)}")
    _setting(spec, next(iter(expected)))


def _ema(close: np.ndarray, period: int) -> np.ndarray:
    values = np.full(close.size, np.nan, dtype=np.float64)
    if close.size == 0:
        return values
    alpha = 2.0 / (period + 1.0)
    values[0] = float(close[0])
    for index in range(1, close.size):
        values[index] = alpha * float(close[index]) + (1.0 - alpha) * values[index - 1]
    return values


def _rsi(close: np.ndarray, period: int) -> np.ndarray:
    values = np.full(close.size, np.nan, dtype=np.float64)
    if close.size <= period:
        return values
    changes = np.diff(close.astype(np.float64, copy=False))
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    average_gain = float(gains[:period].mean())
    average_loss = float(losses[:period].mean())

    def score(gain: float, loss: float) -> float:
        if loss == 0.0:
            return 100.0 if gain > 0.0 else 50.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    values[period] = score(average_gain, average_loss)
    for index in range(period + 1, close.size):
        average_gain = (average_gain * (period - 1) + gains[index - 1]) / period
        average_loss = (average_loss * (period - 1) + losses[index - 1]) / period
        values[index] = score(average_gain, average_loss)
    return values


def _prior_extrema(high: np.ndarray, low: np.ndarray, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    prior_high = np.full(high.size, np.nan, dtype=np.float64)
    prior_low = np.full(low.size, np.nan, dtype=np.float64)
    for index in range(lookback, high.size):
        prior_high[index] = float(np.max(high[index - lookback:index]))
        prior_low[index] = float(np.min(low[index - lookback:index]))
    return prior_high, prior_low


def _relative_volume(volume: np.ndarray, window: int) -> np.ndarray:
    values = np.full(volume.size, np.nan, dtype=np.float64)
    for index in range(window, volume.size):
        baseline = float(np.mean(volume[index - window:index]))
        if baseline > 0.0:
            values[index] = float(volume[index]) / baseline
    return values


def _atr_and_adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> tuple[np.ndarray, np.ndarray]:
    """Return causal Wilder ATR and ADX. Values need completed bars only."""

    size = close.size
    atr = np.full(size, np.nan, dtype=np.float64)
    adx = np.full(size, np.nan, dtype=np.float64)
    if size <= period:
        return atr, adx
    true_range = np.empty(size, dtype=np.float64)
    plus_dm = np.zeros(size, dtype=np.float64)
    minus_dm = np.zeros(size, dtype=np.float64)
    true_range[0] = float(high[0] - low[0])
    for index in range(1, size):
        high_move = float(high[index] - high[index - 1])
        low_move = float(low[index - 1] - low[index])
        plus_dm[index] = high_move if high_move > low_move and high_move > 0.0 else 0.0
        minus_dm[index] = low_move if low_move > high_move and low_move > 0.0 else 0.0
        true_range[index] = max(
            float(high[index] - low[index]),
            abs(float(high[index] - close[index - 1])),
            abs(float(low[index] - close[index - 1])),
        )
    smoothed_tr = float(true_range[1:period + 1].sum())
    smoothed_plus = float(plus_dm[1:period + 1].sum())
    smoothed_minus = float(minus_dm[1:period + 1].sum())
    dx = np.full(size, np.nan, dtype=np.float64)
    for index in range(period, size):
        if index > period:
            smoothed_tr = smoothed_tr - smoothed_tr / period + true_range[index]
            smoothed_plus = smoothed_plus - smoothed_plus / period + plus_dm[index]
            smoothed_minus = smoothed_minus - smoothed_minus / period + minus_dm[index]
        atr[index] = smoothed_tr / period
        if smoothed_tr <= 0.0:
            continue
        plus_di = 100.0 * smoothed_plus / smoothed_tr
        minus_di = 100.0 * smoothed_minus / smoothed_tr
        denominator = plus_di + minus_di
        if denominator > 0.0:
            dx[index] = 100.0 * abs(plus_di - minus_di) / denominator
    first_adx = period * 2 - 1
    if size <= first_adx:
        return atr, adx
    adx[first_adx] = float(np.mean(dx[period:first_adx + 1]))
    for index in range(first_adx + 1, size):
        adx[index] = (adx[index - 1] * (period - 1) + dx[index]) / period
    return atr, adx


@dataclass(frozen=True)
class FeatureStore:
    """One immutable full-history causal primitive assembly; never candidate masks."""

    snapshot: HistorySnapshot
    dates: tuple[date, ...]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    components: Mapping[PrimitiveSpec, Mapping[str, np.ndarray]]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, HistorySnapshot) or self.snapshot.quality_state == "invalid":
            raise ValueError("FeatureStore requires usable HistorySnapshot")
        length = len(self.dates)
        if length == 0:
            raise ValueError("FeatureStore requires at least one native bar")
        if any(type(value) is not date for value in self.dates) or tuple(sorted(self.dates)) != self.dates:
            raise ValueError("FeatureStore dates must be ordered native dates")
        for name in ("open", "high", "low", "close", "volume"):
            values = getattr(self, name)
            if not isinstance(values, np.ndarray) or values.dtype != np.dtype(np.int64) or values.shape != (length,):
                raise ValueError(f"FeatureStore {name} must be one raw int64 array per bar")
            if values.flags.writeable:
                raise ValueError(f"FeatureStore {name} must be read-only")
        frozen_components: dict[PrimitiveSpec, Mapping[str, np.ndarray]] = {}
        for spec, arrays in self.components.items():
            if not isinstance(spec, PrimitiveSpec):
                raise ValueError("FeatureStore components require PrimitiveSpec keys")
            _validate_spec(spec)
            copied: dict[str, np.ndarray] = {}
            for name, values in arrays.items():
                if not isinstance(name, str) or not isinstance(values, np.ndarray) or values.shape != (length,):
                    raise ValueError("FeatureStore component arrays must match native bar count")
                copied[name] = _readonly(values.astype(np.float64, copy=False))
            frozen_components[spec] = MappingProxyType(copied)
        object.__setattr__(self, "components", MappingProxyType(frozen_components))

    def array_for(self, spec: PrimitiveSpec, name: str) -> np.ndarray:
        """Get one owned causal component array; predicates never persist masks."""

        try:
            return self.components[spec][name]
        except KeyError as error:
            raise ValueError(f"FeatureStore lacks {spec.family}.{name}") from error


@dataclass(frozen=True)
class CacheOffer:
    """Fresh compatible component coverage for one already-fingerprinted source."""

    reusable_keys: tuple[str, ...]
    stale_keys: tuple[str, ...]
    missing_keys: tuple[str, ...]

    @property
    def choice_required(self) -> bool:
        return bool(self.reusable_keys)


@dataclass(frozen=True)
class FeatureResolution:
    """Request-only feature assembly and immutable component receipt."""

    store: FeatureStore
    plan: FeaturePlan
    receipt: FeatureResolutionReceipt


def current_feature_build_contract() -> FeatureBuildContract:
    """Return current revision; campaign resume supplies its persisted revision."""

    return FeatureBuildContract()


def _feature_snapshot(snapshot: HistorySnapshot) -> FeatureSnapshot:
    if (
        snapshot.quality_state == "invalid"
        or snapshot.fingerprint is None
        or snapshot.first_date is None
        or snapshot.as_of_date is None
    ):
        raise ValueError("feature cache requires a usable fingerprinted history snapshot")
    return FeatureSnapshot(
        ticker=snapshot.ticker,
        raw_history_fingerprint=snapshot.fingerprint,
        requested_start=snapshot.requested_start,
        requested_as_of=snapshot.requested_as_of,
        first_date=snapshot.first_date,
        as_of_date=snapshot.as_of_date,
        quality_state=snapshot.quality_state,
        quality_revision="flexible-history-v1",
    )


def _cache_state(store: FeatureStore, spec: PrimitiveSpec) -> dict[str, object]:
    return {
        "as_of_date": store.dates[-1].isoformat(),
        "bar_count": len(store.dates),
        "first_date": store.dates[0].isoformat(),
        "primitive": spec.to_dict(),
        "state_revision": "flexible-primitive-state-v1",
    }


def _cached_component_is_compatible(
    component: CachedComponent,
    snapshot: HistorySnapshot,
    spec: PrimitiveSpec,
) -> bool:
    if snapshot.first_date is None or snapshot.as_of_date is None:
        return False
    state = component.state
    return (
        state.get("state_revision") == "flexible-primitive-state-v1"
        and state.get("primitive") == spec.to_dict()
        and state.get("bar_count") == len(snapshot.frame)
        and state.get("first_date") == snapshot.first_date.isoformat()
        and state.get("as_of_date") == snapshot.as_of_date.isoformat()
    )


def inspect_primitive_cache(
    snapshot: HistorySnapshot,
    contract: FeatureBuildContract,
    profile: FeatureProfile,
    root: object,
    now: datetime,
) -> CacheOffer:
    """Inspect only source-compatible components; age never validates source."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("cache inspection time must be timezone-aware")
    plan = FeaturePlan(_feature_snapshot(snapshot), contract, profile)
    reusable: list[str] = []
    stale: list[str] = []
    missing: list[str] = []
    for primitive_key in plan.primitive_keys:
        component = safe_read_component(Path(root), primitive_key.primitive_key)
        if component is None or not _cached_component_is_compatible(component, snapshot, primitive_key.primitive_spec):
            missing.append(primitive_key.primitive_key)
            continue
        age = now - component.completed_at
        if timedelta(0) <= age <= _CACHE_REUSE_MAX_AGE:
            reusable.append(primitive_key.primitive_key)
        else:
            stale.append(primitive_key.primitive_key)
    return CacheOffer(tuple(reusable), tuple(stale), tuple(missing))


def resolve_feature_store(
    snapshot: HistorySnapshot,
    contract: FeatureBuildContract,
    profile: FeatureProfile,
    root: object,
    *,
    choice: str,
    now: datetime,
) -> FeatureResolution:
    """Resolve exact primitive components; persistence remains optional only."""

    if choice not in ("reuse", "rebuild"):
        raise ValueError("feature resolution choice must be reuse or rebuild")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("feature resolution time must be timezone-aware")
    plan = FeaturePlan(_feature_snapshot(snapshot), contract, profile)
    offer = inspect_primitive_cache(snapshot, contract, profile, root, now)
    cached: dict[PrimitiveSpec, CachedComponent] = {}
    if choice == "reuse":
        for primitive_key in plan.primitive_keys:
            if primitive_key.primitive_key in offer.reusable_keys:
                component = safe_read_component(Path(root), primitive_key.primitive_key)
                if component is not None and _cached_component_is_compatible(component, snapshot, primitive_key.primitive_spec):
                    cached[primitive_key.primitive_spec] = component

    # Build once per request when any component needs calculation; no raw source
    # or composed candidate mask enters the persistent cache.
    built = build_feature_store(snapshot, contract, profile)
    resolved: dict[PrimitiveSpec, Mapping[str, np.ndarray]] = {}
    component_digests: list[tuple[str, str]] = []
    for primitive_key in plan.primitive_keys:
        spec = primitive_key.primitive_spec
        component = cached.get(spec)
        if component is None:
            arrays = dict(built.components[spec])
            state = _cache_state(built, spec)
            outcome = try_write_component(Path(root), primitive_key.primitive_key, arrays, state, now)
            if outcome.state == "nondeterministic_build":
                # Old valid component remains source of truth; never overwrite it.
                component = safe_read_component(Path(root), primitive_key.primitive_key)
            if component is None:
                from .primitive_cache import component_digest
                component = CachedComponent(component_digest(primitive_key.primitive_key, arrays, state), arrays, state, now)
        resolved[spec] = component.arrays
        component_digests.append((primitive_key.primitive_key, component.digest))
    store = FeatureStore(
        snapshot=built.snapshot, dates=built.dates, open=built.open, high=built.high,
        low=built.low, close=built.close, volume=built.volume, components=resolved,
    )
    receipt = FeatureResolutionReceipt(plan, tuple(component_digests))
    return FeatureResolution(store, plan, receipt)


def build_feature_store(
    snapshot: HistorySnapshot,
    contract: FeatureBuildContract,
    profile: FeatureProfile,
) -> FeatureStore:
    """Build requested causal components once from full frozen history."""

    if not isinstance(snapshot, HistorySnapshot) or snapshot.quality_state == "invalid":
        raise ValueError("cannot build features from invalid history")
    if not isinstance(contract, FeatureBuildContract) or not isinstance(profile, FeatureProfile):
        raise ValueError("build requires FeatureBuildContract and FeatureProfile")
    frame = snapshot.frame
    parsed_dates = pd.to_datetime(frame["date"], errors="raise")
    dates = tuple(item.date() for item in parsed_dates)
    raw_open = _integer_column(frame, "open")
    raw_high = _integer_column(frame, "high")
    raw_low = _integer_column(frame, "low")
    raw_close = _integer_column(frame, "close")
    raw_volume = _integer_column(frame, "volume")
    components: dict[PrimitiveSpec, Mapping[str, np.ndarray]] = {}
    for spec in profile.primitive_specs:
        _validate_spec(spec)
        if spec.family == "ema":
            settings = dict(spec.settings)
            if "period" in settings:
                components[spec] = {"ema": _ema(raw_close, _setting(spec, "period"))}
            else:
                components[spec] = {
                    "fast": _ema(raw_close, _setting(spec, "fast_period")),
                    "slow": _ema(raw_close, _setting(spec, "slow_period")),
                }
        elif spec.family == "rsi":
            components[spec] = {"rsi": _rsi(raw_close, _setting(spec, "period"))}
        elif spec.family == "breakout":
            prior_high, prior_low = _prior_extrema(raw_high, raw_low, _setting(spec, "lookback"))
            components[spec] = {"prior_high": prior_high, "prior_low": prior_low}
        elif spec.family == "relative_volume":
            components[spec] = {"relative_volume": _relative_volume(raw_volume, _setting(spec, "window"))}
        elif spec.family in ("atr", "adx"):
            atr, adx = _atr_and_adx(raw_high, raw_low, raw_close, _setting(spec, "period"))
            components[spec] = {spec.family: atr if spec.family == "atr" else adx}
    return FeatureStore(snapshot, dates, raw_open, raw_high, raw_low, raw_close, raw_volume, components)


def _condition_number(predicate: PredicateSpec, name: str) -> float:
    value = dict(predicate.condition).get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{predicate.primitive.family} predicate requires numeric {name}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{predicate.primitive.family} predicate requires finite {name}")
    return number


def _condition_text(predicate: PredicateSpec, name: str) -> str:
    value = dict(predicate.condition).get(name)
    if not isinstance(value, str):
        raise ValueError(f"{predicate.primitive.family} predicate requires text {name}")
    return value


def _crosses(values: np.ndarray, level: float, direction: str) -> np.ndarray:
    mask = np.zeros(values.size, dtype=bool)
    finite = np.isfinite(values)
    if direction == "up":
        mask[1:] = finite[1:] & finite[:-1] & (values[1:] >= level) & (values[:-1] < level)
    elif direction == "down":
        mask[1:] = finite[1:] & finite[:-1] & (values[1:] <= level) & (values[:-1] > level)
    else:
        raise ValueError("cross must be up or down")
    return mask


def primitive_mask(store: FeatureStore, predicate: PredicateSpec) -> np.ndarray:
    """Compose one ephemeral causal predicate mask from cached base arrays."""

    if not isinstance(store, FeatureStore) or not isinstance(predicate, PredicateSpec):
        raise ValueError("primitive_mask requires FeatureStore and PredicateSpec")
    spec = predicate.primitive
    if spec.family == "rsi":
        return _crosses(store.array_for(spec, "rsi"), _condition_number(predicate, "level"), _condition_text(predicate, "cross"))
    if spec.family == "ema":
        direction = _condition_text(predicate, "direction")
        settings = dict(spec.settings)
        if "period" in settings:
            current = store.close.astype(np.float64, copy=False)
            reference = store.array_for(spec, "ema")
        else:
            current = store.array_for(spec, "fast")
            reference = store.array_for(spec, "slow")
        finite = np.isfinite(current) & np.isfinite(reference)
        if direction == "up":
            return finite & (current > reference)
        if direction == "down":
            return finite & (current < reference)
        if direction == "cross_up":
            return np.r_[False, finite[1:] & finite[:-1] & (current[1:] > reference[1:]) & (current[:-1] <= reference[:-1])]
        if direction == "cross_down":
            return np.r_[False, finite[1:] & finite[:-1] & (current[1:] < reference[1:]) & (current[:-1] >= reference[:-1])]
        raise ValueError("ema direction must be up, down, cross_up, or cross_down")
    if spec.family == "breakout":
        direction = _condition_text(predicate, "direction")
        if direction == "up":
            level = store.array_for(spec, "prior_high")
            return np.isfinite(level) & (store.close.astype(np.float64, copy=False) > level)
        if direction == "down":
            level = store.array_for(spec, "prior_low")
            return np.isfinite(level) & (store.close.astype(np.float64, copy=False) < level)
        raise ValueError("breakout direction must be up or down")
    if spec.family == "relative_volume":
        values = store.array_for(spec, "relative_volume")
        return np.isfinite(values) & (values >= _condition_number(predicate, "minimum"))
    if spec.family == "adx":
        values = store.array_for(spec, "adx")
        return np.isfinite(values) & (values >= _condition_number(predicate, "minimum"))
    raise ValueError(f"{spec.family} cannot be used as a predicate")


def compose_entry_mask(store: FeatureStore, definition: RulebookDefinition) -> np.ndarray:
    """AND all BUY, gate, and filter masks in memory for one candidate."""

    if not isinstance(definition, RulebookDefinition):
        raise ValueError("compose_entry_mask requires RulebookDefinition")
    result = np.ones(len(store.dates), dtype=bool)
    for predicate in (*definition.buy_predicates, *definition.gates, *definition.filters):
        result &= primitive_mask(store, predicate)
    return result


def compose_technical_exit_mask(store: FeatureStore, definition: RulebookDefinition) -> np.ndarray | None:
    """AND selected technical SELL predicates, or return no technical exit."""

    if not isinstance(definition, RulebookDefinition):
        raise ValueError("compose_technical_exit_mask requires RulebookDefinition")
    if not definition.exits:
        return None
    result = np.ones(len(store.dates), dtype=bool)
    for predicate in definition.exits:
        result &= primitive_mask(store, predicate)
    return result


__all__ = [
    "FeatureStore",
    "CacheOffer",
    "FeatureResolution",
    "build_feature_store",
    "compose_entry_mask",
    "compose_technical_exit_mask",
    "primitive_mask",
    "current_feature_build_contract",
    "inspect_primitive_cache",
    "resolve_feature_store",
]
