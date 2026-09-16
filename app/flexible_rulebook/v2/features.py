"""Registry-driven causal components and exact predicate facts for Flexible v2."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

from commons.causal_indicators import (
    adx_dmi,
    alligator_hl2,
    atr,
    bollinger,
    ema,
    obv,
    prior_extrema,
    relative_volume,
    rsi,
    sma,
    stochastic,
    supertrend,
)

from .contracts import PredicateV2, semantic_digest
from .contracts import HORIZONS
from .registry import DEFAULT_INDICATOR_REGISTRY, IndicatorRegistry


@dataclass(frozen=True)
class PredicateEvaluation:
    """One causal event mask, its continuing support relation, and diagnostics."""

    mask: pd.Series
    support: pd.Series
    diagnostics: tuple[str, ...]


def component_cache_key(predicate: PredicateV2) -> str:
    """Return the math-only cache identity; comparisons never affect it."""

    return semantic_digest(
        {
            "family": predicate.family,
            "family_revision": predicate.family_revision,
            "settings": predicate.settings_dict,
        }
    )


def _as_float(value: object) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _bool(values: pd.Series, available: pd.Series | None = None) -> pd.Series:
    result = values.fillna(False).astype(bool)
    if available is not None:
        result = (result & available.fillna(False).astype(bool)).astype(bool)
    return result


def _finite(*series: pd.Series) -> pd.Series:
    if not series:
        raise ValueError("at least one series is required")
    result = pd.Series(True, index=series[0].index, dtype=bool)
    for values in series:
        result &= np.isfinite(pd.to_numeric(values, errors="coerce"))
    return result


def _crosses_above(left: pd.Series, right: pd.Series) -> pd.Series:
    return _bool(left.gt(right) & left.shift(1).le(right.shift(1)), _finite(left, right, left.shift(1), right.shift(1)))


def _crosses_below(left: pd.Series, right: pd.Series) -> pd.Series:
    return _bool(left.lt(right) & left.shift(1).ge(right.shift(1)), _finite(left, right, left.shift(1), right.shift(1)))


class FeatureStore:
    """Per-evaluation component store whose values are shared by all predicates."""

    def __init__(
        self,
        frame: pd.DataFrame,
        *,
        horizon: str = "swing",
        registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
    ) -> None:
        if horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        self.frame = frame.copy(deep=True)
        self.horizon = horizon
        self.registry = registry
        self._components: dict[str, pd.DataFrame] = {}

    def component(self, predicate: PredicateV2) -> pd.DataFrame:
        """Build or return the immutable math component selected by one predicate."""

        self.registry.validate_predicate(predicate, horizon=self.horizon)
        key = component_cache_key(predicate)
        if key not in self._components:
            self._components[key] = self._build_component(predicate)
        return self._components[key]

    def evaluate(self, predicate: PredicateV2) -> PredicateEvaluation:
        """Return event and continuing-support facts without threshold distance ratios."""

        component = self.component(predicate)
        mask, support, available = self._evaluate_component(predicate, component)
        diagnostics = (f"unavailable:{predicate.family}",) if bool((~available).any()) else ()
        return PredicateEvaluation(_bool(mask, available), _bool(support, available), diagnostics)

    def _build_component(self, predicate: PredicateV2) -> pd.DataFrame:
        settings = predicate.settings_dict
        family = predicate.family
        close = self._series("close")
        if family in {"sma", "ema"}:
            calculator = sma if family == "sma" else ema
            if "period" in settings:
                return pd.DataFrame({"value": calculator(close, int(settings["period"]))}, index=self.frame.index)
            return pd.DataFrame(
                {
                    "fast": calculator(close, int(settings["fast_period"])),
                    "slow": calculator(close, int(settings["slow_period"])),
                },
                index=self.frame.index,
            )
        if family == "rsi":
            return pd.DataFrame({"rsi": rsi(close, int(settings["period"]))}, index=self.frame.index)
        if family == "alligator":
            return alligator_hl2(self.frame, **{key: int(value) for key, value in settings.items()})
        if family == "adx_dmi":
            return adx_dmi(self.frame, int(settings["period"]))
        if family == "stochastic":
            return stochastic(self.frame, **{key: int(value) for key, value in settings.items()})
        if family == "breakout":
            return prior_extrema(self.frame, int(settings["period"]))
        if family == "relative_volume":
            return relative_volume(self._series("volume"), int(settings["period"]))
        if family == "obv":
            value = obv(close, self._series("volume"))
            period = int(settings["period"])
            return pd.DataFrame({"obv": value, "obv_ma": sma(value, period)}, index=self.frame.index)
        if family == "atr":
            return pd.DataFrame({"atr": atr(self.frame, int(settings["period"]))}, index=self.frame.index)
        if family == "bollinger":
            return bollinger(close, int(settings["period"]), _as_float(settings["multiplier"]))
        if family == "supertrend":
            return supertrend(self.frame, period=int(settings["period"]), multiplier=_as_float(settings["multiplier"]))
        raise ValueError(f"unsupported indicator family {family}")

    def _series(self, name: str) -> pd.Series:
        if name in self.frame.columns:
            return pd.to_numeric(self.frame[name], errors="coerce").astype(float)
        return pd.Series(float("nan"), index=self.frame.index, dtype=float)

    def _evaluate_component(
        self,
        predicate: PredicateV2,
        component: pd.DataFrame,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        family = predicate.family
        operator = predicate.operator
        condition = predicate.condition_dict
        close = self._series("close")
        index = self.frame.index
        if family in {"sma", "ema"}:
            if {"fast", "slow"}.issubset(component.columns):
                left, right = component["fast"], component["slow"]
            else:
                left, right = close, component["value"]
            return self._relation(operator, left, right, condition, predicate.direction_lookback)
        if family in {"rsi", "adx_dmi", "stochastic", "relative_volume", "atr"}:
            column = {"rsi": "rsi", "adx_dmi": "adx", "stochastic": "k", "relative_volume": "relative_volume", "atr": "atr"}[family]
            return self._threshold_relation(operator, component[column], condition, predicate.direction_lookback)
        if family == "breakout":
            if operator in {"above", "crosses_above"}:
                return self._relation(operator, close, component["prior_high"], condition, predicate.direction_lookback)
            return self._relation(operator, close, component["prior_low"], condition, predicate.direction_lookback)
        if family == "obv":
            return self._relation(operator, component["obv"], component["obv_ma"], condition, predicate.direction_lookback)
        if family == "bollinger":
            if operator == "percent_b_above":
                return self._threshold_relation("above", component["percent_b"], condition, predicate.direction_lookback)
            if operator == "percent_b_below":
                return self._threshold_relation("below", component["percent_b"], condition, predicate.direction_lookback)
            if operator == "bandwidth_above":
                return self._threshold_relation("above", component["bandwidth"], condition, predicate.direction_lookback)
            if operator == "bandwidth_below":
                return self._threshold_relation("below", component["bandwidth"], condition, predicate.direction_lookback)
            if operator in {"crosses_above", "above"}:
                return self._relation(operator, close, component["upper"], condition, predicate.direction_lookback)
            if operator in {"crosses_below", "below"}:
                return self._relation(operator, close, component["lower"], condition, predicate.direction_lookback)
            return self._direction(operator, component["middle"], predicate.direction_lookback)
        if family == "alligator":
            return self._alligator_relation(operator, component, predicate.direction_lookback, index)
        if family == "supertrend":
            return self._supertrend_relation(operator, component, predicate.direction_lookback)
        raise ValueError(f"unsupported indicator family {family}")

    @staticmethod
    def _threshold_relation(
        operator: str,
        values: pd.Series,
        condition: dict[str, object],
        lookback: int | None,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        if operator in {"rising", "falling", "direction"}:
            return FeatureStore._direction(operator, values, lookback)
        threshold = _as_float(condition["threshold"])
        level = pd.Series(threshold, index=values.index, dtype=float)
        return FeatureStore._relation(operator, values, level, condition, lookback)

    @staticmethod
    def _relation(
        operator: str,
        left: pd.Series,
        right: pd.Series,
        condition: dict[str, object],
        lookback: int | None,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        available = _finite(left, right)
        if operator in {"above", "bullish_state"}:
            state = left.gt(right)
            return state, state, available
        if operator in {"below", "bearish_state"}:
            state = left.lt(right)
            return state, state, available
        if operator in {"upcross", "crosses_above", "bullish_cross"}:
            event = _crosses_above(left, right)
            return event, left.ge(right), available & _finite(left.shift(1), right.shift(1))
        if operator in {"downcross", "crosses_below", "bearish_cross"}:
            event = _crosses_below(left, right)
            return event, left.le(right), available & _finite(left.shift(1), right.shift(1))
        if operator in {"rising", "falling", "direction"}:
            return FeatureStore._direction(operator, left, lookback)
        raise ValueError(f"unsupported relation operator {operator}")

    @staticmethod
    def _direction(
        operator: str,
        values: pd.Series,
        lookback: int | None,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        if lookback is None:
            raise ValueError("direction_lookback is required")
        previous = values.shift(lookback)
        available = _finite(values, previous)
        if operator == "falling":
            state = values.lt(previous)
        else:
            state = values.gt(previous)
        return state, state, available

    @staticmethod
    def _alligator_relation(
        operator: str,
        component: pd.DataFrame,
        lookback: int | None,
        index: pd.Index,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        lips, teeth, jaw = component["lips"], component["teeth"], component["jaw"]
        available = _finite(lips, teeth, jaw)
        bullish = lips.gt(teeth) & teeth.gt(jaw)
        bearish = lips.lt(teeth) & teeth.lt(jaw)
        if operator == "bullish_alignment":
            return bullish, bullish, available
        if operator == "bearish_alignment":
            return bearish, bearish, available
        if operator == "bullish_cross":
            event = _crosses_above(lips, teeth) & teeth.gt(jaw)
            return event, bullish, available & _finite(lips.shift(1), teeth.shift(1))
        if operator == "bearish_cross":
            event = _crosses_below(lips, teeth) & teeth.lt(jaw)
            return event, bearish, available & _finite(lips.shift(1), teeth.shift(1))
        spread = (lips - jaw).abs()
        if operator in {"opening", "closing"}:
            if lookback is None:
                raise ValueError("direction_lookback is required")
            prior_spread = spread.shift(lookback)
            direction_available = available & _finite(prior_spread)
            state = spread.gt(prior_spread) if operator == "opening" else spread.lt(prior_spread)
            return state & (bullish | bearish), state & (bullish | bearish), direction_available
        if operator in {"rising", "falling"}:
            return FeatureStore._direction(operator, spread, lookback)
        return pd.Series(False, index=index), pd.Series(False, index=index), available

    @staticmethod
    def _supertrend_relation(
        operator: str,
        component: pd.DataFrame,
        lookback: int | None,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        direction = component["direction"]
        available = _finite(direction)
        if operator == "bullish_state":
            state = direction.eq(1.0)
            return state, state, available
        if operator == "bearish_state":
            state = direction.eq(-1.0)
            return state, state, available
        if operator == "direction_flip":
            prior = direction.shift(1)
            event = direction.ne(prior)
            return event, direction.eq(1.0), available & _finite(prior)
        return FeatureStore._direction(operator, component["supertrend"], lookback)


__all__ = ["FeatureStore", "PredicateEvaluation", "component_cache_key"]
