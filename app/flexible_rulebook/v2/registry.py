"""Single-source indicator metadata and settings validation for Flexible v2."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .contracts import AtrExitV2, HORIZONS, PredicateV2


def _as_decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class ParameterSpec:
    """One UI/evaluator-shared scalar parameter bound."""

    name: str
    kind: str
    minimum: Decimal | int | None = None
    maximum: Decimal | int | None = None
    required: bool = True

    def validate(self, value: object) -> None:
        if self.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{self.name} must be an integer")
            numeric: Decimal | int = value
        elif self.kind == "decimal":
            numeric = _as_decimal(value, self.name)
        else:
            raise ValueError(f"unsupported parameter kind {self.kind}")
        if self.minimum is not None and numeric < self.minimum:
            raise ValueError(f"{self.name} must be at least {self.minimum}")
        if self.maximum is not None and numeric > self.maximum:
            raise ValueError(f"{self.name} must be at most {self.maximum}")


SettingsValidator = Callable[[Mapping[str, object]], None]


@dataclass(frozen=True)
class IndicatorSpec:
    """Registry-owned formula, role, predicate, and support metadata."""

    family: str
    formula_revision: str
    native_timeframes: tuple[str, ...]
    roles: frozenset[str]
    input_series: tuple[str, ...]
    output_names: tuple[str, ...]
    parameters: tuple[ParameterSpec, ...]
    operators: frozenset[str]
    warmup: Callable[[Mapping[str, object]], int]
    support_projection: str
    condition_parameters: tuple[ParameterSpec, ...] = ()
    settings_validator: SettingsValidator | None = None

    def warmup_bars(self, settings: Mapping[str, object]) -> int:
        self._validate_mapping(settings, self.parameters, label="setting", require_all=False)
        if self.settings_validator is not None:
            self.settings_validator(settings)
        result = self.warmup(settings)
        if isinstance(result, bool) or not isinstance(result, int) or result < 0:
            raise ValueError(f"{self.family} warm-up must be a non-negative integer")
        return result

    def validate(self, predicate: PredicateV2, *, horizon: str) -> None:
        if horizon not in HORIZONS:
            raise ValueError(f"{self.family} does not support horizon {horizon}")
        native_timeframe = "daily" if horizon == "swing" else "weekly"
        if native_timeframe not in self.native_timeframes:
            raise ValueError(f"{self.family} does not support horizon {horizon}")
        if predicate.role not in self.roles:
            raise ValueError(f"{self.family} does not support role {predicate.role}")
        if predicate.operator not in self.operators:
            raise ValueError(f"{self.family} does not support operator {predicate.operator}")
        settings = predicate.settings_dict
        condition = predicate.condition_dict
        self._validate_mapping(settings, self.parameters, label="setting", require_all=False)
        self._validate_mapping(condition, self.condition_parameters, label="condition", require_all=False)
        if self.settings_validator is not None:
            self.settings_validator(settings)
        self._validate_operator_condition(predicate)

    def _validate_mapping(
        self,
        supplied: Mapping[str, object],
        parameters: Sequence[ParameterSpec],
        *,
        label: str,
        require_all: bool,
    ) -> None:
        by_name = {spec.name: spec for spec in parameters}
        unknown = set(supplied) - set(by_name)
        if unknown:
            raise ValueError(f"{self.family} has unknown {label} {sorted(unknown)[0]}")
        for spec in parameters:
            if spec.required and require_all and spec.name not in supplied:
                raise ValueError(f"{self.family} requires {label} {spec.name}")
            if spec.name in supplied:
                spec.validate(supplied[spec.name])

    def _validate_operator_condition(self, predicate: PredicateV2) -> None:
        condition = predicate.condition_dict
        threshold_operators = {
            "above", "below", "upcross", "downcross",
            "percent_b_above", "percent_b_below", "bandwidth_above", "bandwidth_below",
        }
        direction_operators = {"rising", "falling", "direction", "opening", "closing"}
        if predicate.operator in threshold_operators and "threshold" not in condition:
            raise ValueError(f"{self.family} {predicate.operator} requires condition threshold")
        if predicate.operator in direction_operators:
            if predicate.direction_lookback is None:
                raise ValueError(f"{self.family} {predicate.operator} requires direction_lookback")
        elif predicate.direction_lookback is not None:
            raise ValueError(f"{self.family} {predicate.operator} does not use direction_lookback")


class IndicatorRegistry:
    """Immutable lookup facade used by both draft validation and future UI."""

    def __init__(self, specifications: Sequence[IndicatorSpec]) -> None:
        by_family = {spec.family: spec for spec in specifications}
        if len(by_family) != len(specifications):
            raise ValueError("indicator families must be unique")
        self._by_family = by_family

    @property
    def families(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_family))

    def for_family(self, family: str) -> IndicatorSpec:
        try:
            return self._by_family[family]
        except KeyError as error:
            raise ValueError(f"unsupported indicator family {family}") from error

    def validate_predicate(self, predicate: PredicateV2, *, horizon: str) -> None:
        specification = self.for_family(predicate.family)
        if predicate.family_revision != specification.formula_revision:
            raise ValueError(
                f"{predicate.family} must use formula revision {specification.formula_revision}"
            )
        specification.validate(predicate, horizon=horizon)

    def validate_atr_exit(self, atr_exit: AtrExitV2, *, horizon: str) -> None:
        specification = self.for_family("atr")
        if atr_exit.formula_revision != specification.formula_revision:
            raise ValueError(f"atr must use formula revision {specification.formula_revision}")
        specification.warmup_bars({"period": atr_exit.period})
        if horizon not in HORIZONS:
            raise ValueError(f"atr does not support horizon {horizon}")


def _require_exact_keys(settings: Mapping[str, object], keys: set[str], family: str) -> None:
    if set(settings) != keys:
        raise ValueError(f"{family} requires settings {', '.join(sorted(keys))}")


def _single_period(family: str, minimum: int, maximum: int) -> SettingsValidator:
    def validate(settings: Mapping[str, object]) -> None:
        _require_exact_keys(settings, {"period"}, family)
        value = settings["period"]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"period must be from {minimum} through {maximum}")

    return validate


def _ma_settings(family: str) -> SettingsValidator:
    def validate(settings: Mapping[str, object]) -> None:
        keys = set(settings)
        if keys == {"period"}:
            value = settings["period"]
            if isinstance(value, bool) or not isinstance(value, int) or not 2 <= value <= 250:
                raise ValueError("period must be from 2 through 250")
            return
        if keys != {"fast_period", "slow_period"}:
            raise ValueError(f"{family} requires period or fast_period and slow_period")
        fast, slow = settings["fast_period"], settings["slow_period"]
        if any(isinstance(item, bool) or not isinstance(item, int) or not 2 <= item <= 250 for item in (fast, slow)):
            raise ValueError("fast_period and slow_period must be from 2 through 250")
        if fast >= slow:
            raise ValueError("fast_period must be less than slow_period")

    return validate


def _alligator_settings(settings: Mapping[str, object]) -> None:
    required = {
        "jaw_period", "teeth_period", "lips_period", "jaw_offset", "teeth_offset", "lips_offset",
    }
    _require_exact_keys(settings, required, "alligator")
    periods = [settings[name] for name in ("jaw_period", "teeth_period", "lips_period")]
    offsets = [settings[name] for name in ("jaw_offset", "teeth_offset", "lips_offset")]
    if any(isinstance(value, bool) or not isinstance(value, int) or not 2 <= value <= 100 for value in periods):
        raise ValueError("alligator periods must be from 2 through 100")
    if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 50 for value in offsets):
        raise ValueError("alligator offsets must be from 0 through 50")
    if len(set(periods)) != 3 or len(set(offsets)) != 3:
        raise ValueError("alligator periods and offsets must be distinct")


def _stochastic_settings(settings: Mapping[str, object]) -> None:
    required = {"k_period", "k_smoothing", "d_period"}
    _require_exact_keys(settings, required, "stochastic")
    k, smoothing, d_period = (settings[name] for name in ("k_period", "k_smoothing", "d_period"))
    if isinstance(k, bool) or not isinstance(k, int) or not 2 <= k <= 100:
        raise ValueError("k_period must be from 2 through 100")
    if any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 20 for value in (smoothing, d_period)):
        raise ValueError("k_smoothing and d_period must be from 1 through 20")


def _bollinger_settings(settings: Mapping[str, object]) -> None:
    _require_exact_keys(settings, {"period", "multiplier"}, "bollinger")
    period, multiplier = settings["period"], _as_decimal(settings["multiplier"], "multiplier")
    if isinstance(period, bool) or not isinstance(period, int) or not 2 <= period <= 250:
        raise ValueError("period must be from 2 through 250")
    if not Decimal("0.1") <= multiplier <= Decimal("5.0"):
        raise ValueError("multiplier must be from 0.1 through 5.0")


def _supertrend_settings(settings: Mapping[str, object]) -> None:
    _require_exact_keys(settings, {"period", "multiplier"}, "supertrend")
    period, multiplier = settings["period"], _as_decimal(settings["multiplier"], "multiplier")
    if isinstance(period, bool) or not isinstance(period, int) or not 2 <= period <= 100:
        raise ValueError("period must be from 2 through 100")
    if not Decimal("0.1") <= multiplier <= Decimal("20.0"):
        raise ValueError("multiplier must be from 0.1 through 20.0")


def _relative_volume_settings(settings: Mapping[str, object]) -> None:
    _require_exact_keys(settings, {"period"}, "relative_volume")
    period = settings["period"]
    if isinstance(period, bool) or not isinstance(period, int) or not 2 <= period <= 250:
        raise ValueError("period must be from 2 through 250")


def _warmup_from_period(settings: Mapping[str, object]) -> int:
    return int(settings.get("period", 0))


def _warmup_ma(settings: Mapping[str, object]) -> int:
    return int(settings.get("slow_period", settings.get("period", 0)))


def _warmup_alligator(settings: Mapping[str, object]) -> int:
    return max(int(settings[name]) + int(settings[offset]) for name, offset in (
        ("jaw_period", "jaw_offset"), ("teeth_period", "teeth_offset"), ("lips_period", "lips_offset"),
    ))


def _warmup_stochastic(settings: Mapping[str, object]) -> int:
    return int(settings["k_period"]) + int(settings["k_smoothing"]) + int(settings["d_period"]) - 2


def _warmup_bollinger(settings: Mapping[str, object]) -> int:
    return int(settings["period"])


_THRESHOLD = ParameterSpec("threshold", "decimal", Decimal("0"), Decimal("100"), required=False)
_PERIOD = ParameterSpec("period", "int", 2, 250, required=False)
_FAST = ParameterSpec("fast_period", "int", 2, 250, required=False)
_SLOW = ParameterSpec("slow_period", "int", 2, 250, required=False)
_MULTIPLIER = ParameterSpec("multiplier", "decimal", Decimal("0.1"), Decimal("20"), required=False)


DEFAULT_INDICATOR_REGISTRY = IndicatorRegistry(
    (
        IndicatorSpec(
            family="sma", formula_revision="sma-close-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("close",), output_names=("sma",),
            parameters=(_PERIOD, _FAST, _SLOW), operators=frozenset({"above", "below", "bullish_state", "bearish_state", "bullish_cross", "bearish_cross", "rising", "falling"}),
            warmup=_warmup_ma, support_projection="relation", condition_parameters=(_THRESHOLD,), settings_validator=_ma_settings("sma"),
        ),
        IndicatorSpec(
            family="ema", formula_revision="ema-close-adjust-false-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("close",), output_names=("ema",),
            parameters=(_PERIOD, _FAST, _SLOW), operators=frozenset({"above", "below", "bullish_state", "bearish_state", "bullish_cross", "bearish_cross", "rising", "falling"}),
            warmup=_warmup_ma, support_projection="relation", condition_parameters=(_THRESHOLD,), settings_validator=_ma_settings("ema"),
        ),
        IndicatorSpec(
            family="rsi", formula_revision="rsi-wilder-sma-seeded-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("close",), output_names=("rsi",), parameters=(_PERIOD,),
            operators=frozenset({"above", "below", "upcross", "downcross", "rising", "falling"}),
            warmup=_warmup_from_period, support_projection="threshold_or_direction", condition_parameters=(_THRESHOLD,), settings_validator=_single_period("rsi", 2, 100),
        ),
        IndicatorSpec(
            family="alligator", formula_revision="alligator-hl2-smma-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("high", "low", "close"), output_names=("jaw", "teeth", "lips"),
            parameters=tuple(ParameterSpec(name, "int", 0, 100, required=False) for name in ("jaw_period", "teeth_period", "lips_period", "jaw_offset", "teeth_offset", "lips_offset")),
            operators=frozenset({"bullish_alignment", "bearish_alignment", "opening", "closing", "bullish_cross", "bearish_cross", "rising", "falling"}),
            warmup=_warmup_alligator, support_projection="alignment_or_direction", settings_validator=_alligator_settings,
        ),
        IndicatorSpec(
            family="adx_dmi", formula_revision="adx-dmi-wilder-sma-seeded-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("high", "low", "close"), output_names=("adx", "plus_di", "minus_di"), parameters=(_PERIOD,),
            operators=frozenset({"above", "below", "rising", "falling", "bullish_state", "bearish_state", "bullish_cross", "bearish_cross"}),
            warmup=lambda settings: int(settings["period"]) * 2, support_projection="threshold_or_direction", condition_parameters=(_THRESHOLD,), settings_validator=_single_period("adx_dmi", 2, 100),
        ),
        IndicatorSpec(
            family="stochastic", formula_revision="stochastic-sma-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("high", "low", "close"), output_names=("raw_k", "k", "d"),
            parameters=tuple(ParameterSpec(name, "int", 1, 100, required=False) for name in ("k_period", "k_smoothing", "d_period")),
            operators=frozenset({"above", "below", "upcross", "downcross", "bullish_state", "bearish_state", "bullish_cross", "bearish_cross", "rising", "falling"}),
            warmup=_warmup_stochastic, support_projection="threshold_or_direction", condition_parameters=(_THRESHOLD,), settings_validator=_stochastic_settings,
        ),
        IndicatorSpec(
            family="breakout", formula_revision="prior-extrema-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("high", "low", "close"), output_names=("prior_high", "prior_low"), parameters=(_PERIOD,),
            operators=frozenset({"above", "below", "crosses_above", "crosses_below"}), warmup=_warmup_from_period,
            support_projection="relation", condition_parameters=(_THRESHOLD,), settings_validator=_single_period("breakout", 2, 250),
        ),
        IndicatorSpec(
            family="relative_volume", formula_revision="relative-volume-prior-window-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate"}), input_series=("volume",), output_names=("relative_volume",), parameters=(_PERIOD,),
            operators=frozenset({"above", "below", "rising", "falling"}), warmup=_warmup_from_period,
            support_projection="threshold_or_direction", condition_parameters=(ParameterSpec("threshold", "decimal", Decimal("0.1"), Decimal("20"), required=False),), settings_validator=_relative_volume_settings,
        ),
        IndicatorSpec(
            family="obv", formula_revision="obv-close-direction-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("close", "volume"), output_names=("obv", "obv_ma"), parameters=(_PERIOD,),
            operators=frozenset({"above", "below", "bullish_state", "bearish_state", "bullish_cross", "bearish_cross", "rising", "falling"}),
            warmup=_warmup_from_period, support_projection="relation_or_direction", condition_parameters=(_THRESHOLD,), settings_validator=_single_period("obv", 2, 250),
        ),
        IndicatorSpec(
            family="atr", formula_revision="atr-wilder-sma-seeded-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"gate"}), input_series=("high", "low", "close"), output_names=("atr",), parameters=(_PERIOD,), operators=frozenset({"above", "below", "rising", "falling"}),
            warmup=_warmup_from_period, support_projection="threshold_or_direction", condition_parameters=(_THRESHOLD,), settings_validator=_single_period("atr", 2, 100),
        ),
        IndicatorSpec(
            family="bollinger", formula_revision="bollinger-close-sample-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("close",), output_names=("middle", "upper", "lower", "bandwidth", "percent_b"), parameters=(_PERIOD, _MULTIPLIER),
            operators=frozenset({"above", "below", "crosses_above", "crosses_below", "percent_b_above", "percent_b_below", "bandwidth_above", "bandwidth_below", "rising", "falling"}),
            warmup=_warmup_bollinger, support_projection="band_or_direction", condition_parameters=(_THRESHOLD,), settings_validator=_bollinger_settings,
        ),
        IndicatorSpec(
            family="supertrend", formula_revision="supertrend-hl2-wilder-v1", native_timeframes=("daily", "weekly"),
            roles=frozenset({"buy", "gate", "technical_sell"}), input_series=("high", "low", "close"), output_names=("supertrend", "direction", "final_upper", "final_lower"), parameters=(_PERIOD, _MULTIPLIER),
            operators=frozenset({"bullish_state", "bearish_state", "direction_flip", "rising", "falling"}),
            warmup=_warmup_from_period, support_projection="state_or_direction", settings_validator=_supertrend_settings,
        ),
    )
)
