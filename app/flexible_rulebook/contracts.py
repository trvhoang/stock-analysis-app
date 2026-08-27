"""Portable immutable contracts for the isolated Flexible Rulebook core."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import itertools
import json
import math
from pathlib import Path
import re


ANIMAL_POOL_V1 = (
    "Aardvark", "Albatross", "Antelope", "Badger", "Bear", "Beaver", "Bison",
    "Buffalo", "Camel", "Capybara", "Cheetah", "Cobra", "Crane", "Dolphin",
    "Eagle", "Elephant", "Falcon", "Fennec", "Fox", "Gecko", "Giraffe", "Hawk",
    "Heron", "Jaguar", "Koala", "Leopard", "Lion", "Lynx", "Meerkat", "Mongoose",
    "Otter", "Owl", "Panda", "Panther", "Penguin", "Puma", "Raven", "Rhino",
    "Seal", "Shark", "Sloth", "Tiger", "Tortoise", "Viper", "Walrus", "Whale",
    "Wolf", "Wombat", "Yak", "Zebra",
)

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_PREDICATE_ROLES = ("buy", "gate", "filter", "technical_sell")
_QUALITY_STATES = ("eligible", "display_only", "invalid")
_SPLIT_METHODS = ("calendar_10y_5y", "chronological_65_35")
_PROHIBITED_SETTING_KEYS = {
    "as_of",
    "age",
    "cache",
    "cache_age",
    "cache_age_seconds",
    "cache_hit",
    "cache_path",
    "date",
    "dates",
    "fingerprint",
    "history",
    "hit",
    "metric",
    "metrics",
    "path",
    "rebuild_choice",
    "result",
    "results",
    "source_fingerprint",
    "ticker",
}


def _require_non_blank(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _require_token(value: object, name: str) -> str:
    normalized = _require_non_blank(value, name)
    if not _TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError(f"{name} must be lowercase token text")
    return normalized


def _require_hash(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _normalize_ticker(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("ticker must be text")
    ticker = value.strip().upper()
    if not ticker or not _TICKER_PATTERN.fullmatch(ticker):
        raise ValueError("ticker must contain only persistence-safe characters")
    return ticker


def _is_native_bar_date(value: object) -> bool:
    """Return whether value is a date-only daily-bar boundary."""

    return type(value) is date


def _normalize_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Decimal values must be finite")
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _canonical_value(value: object) -> object:
    """Return a JSON-safe canonical value or reject nonportable input."""

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return {"$decimal": _normalize_decimal(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("float values must be finite")
        if value == 0:
            value = 0.0
        return {"$float": repr(value)}
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime values must be timezone-aware")
        return {"$datetime": value.isoformat()}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, Path):
        raise ValueError("paths are not canonical identity material")
    if is_dataclass(value):
        if hasattr(value, "to_semantic_dict"):
            return _canonical_value(value.to_semantic_dict())
        if hasattr(value, "to_identity_dict"):
            return _canonical_value(value.to_identity_dict())
        raise ValueError("dataclass lacks an explicit canonical representation")
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ValueError("canonical mappings require string keys")
            result[key] = _canonical_value(value[key])
        return result
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    raise ValueError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Serialize portable identity material with one deterministic JSON form."""

    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_scalar(value: object, name: str) -> str | int | bool | Decimal | None:
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str) and not value:
            raise ValueError(f"{name} must not be empty text")
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        try:
            return Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError(f"{name} must be finite") from error
    raise ValueError(f"{name} must be a portable scalar")


def _normalize_pairs(
    value: object,
    name: str,
    *,
    reject_operational_keys: bool,
) -> tuple[tuple[str, str | int | bool | Decimal | None], ...]:
    if isinstance(value, Mapping):
        items = tuple(value.items())
    else:
        if isinstance(value, (str, bytes)):
            raise ValueError(f"{name} must be key/value pairs")
        try:
            items = tuple(value)  # type: ignore[arg-type]
        except TypeError as error:
            raise ValueError(f"{name} must be key/value pairs") from error

    normalized: list[tuple[str, str | int | bool | Decimal | None]] = []
    for item in items:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(f"{name} must contain two-value pairs")
        key = _require_token(item[0], f"{name} key")
        if reject_operational_keys and (
            key in _PROHIBITED_SETTING_KEYS or key.startswith("cache_")
        ):
            raise ValueError(f"{name} must not contain cache metadata")
        normalized.append((key, _normalize_scalar(item[1], f"{name}.{key}")))
    normalized.sort(key=lambda item: item[0])
    if len({key for key, _ in normalized}) != len(normalized):
        raise ValueError(f"{name} keys must be unique")
    return tuple(normalized)


def _positive_decimal(value: object, name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive finite number")
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be a positive finite number") from error
    if not decimal.is_finite() or decimal <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return decimal


@dataclass(frozen=True)
class PrimitiveSpec:
    """One reusable parameterized base feature, without a predicate threshold."""

    family: str
    family_revision: str
    settings: tuple[tuple[str, str | int | bool | Decimal | None], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", _require_token(self.family, "family"))
        object.__setattr__(self, "family_revision", _require_non_blank(self.family_revision, "family_revision"))
        object.__setattr__(self, "settings", _normalize_pairs(
            self.settings,
            "settings",
            reject_operational_keys=True,
        ))

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "family_revision": self.family_revision,
            "settings": {key: value for key, value in self.settings},
        }


@dataclass(frozen=True)
class PredicateSpec:
    """One rulebook predicate over a reusable base feature."""

    role: str
    primitive: PrimitiveSpec
    condition: tuple[tuple[str, str | int | bool | Decimal | None], ...] = ()

    def __post_init__(self) -> None:
        if self.role not in _PREDICATE_ROLES:
            raise ValueError(f"role must be one of {_PREDICATE_ROLES}")
        if not isinstance(self.primitive, PrimitiveSpec):
            raise ValueError("primitive must be a PrimitiveSpec")
        object.__setattr__(self, "condition", _normalize_pairs(
            self.condition,
            "condition",
            reject_operational_keys=True,
        ))

    def to_dict(self, *, include_role: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "primitive": self.primitive.to_dict(),
            "condition": {key: item for key, item in self.condition},
        }
        if include_role:
            value["role"] = self.role
        return value


def _normalize_predicate_group(
    value: object,
    name: str,
    allowed_roles: tuple[str, ...],
) -> tuple[PredicateSpec, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        predicates = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    if any(not isinstance(predicate, PredicateSpec) for predicate in predicates):
        raise ValueError(f"{name} must contain PredicateSpec values")
    if any(predicate.role not in allowed_roles for predicate in predicates):
        raise ValueError(f"{name} roles are invalid")
    ordered = tuple(sorted(predicates, key=lambda predicate: canonical_json(predicate.to_dict())))
    if len({canonical_json(predicate.to_dict()) for predicate in ordered}) != len(ordered):
        raise ValueError(f"{name} must not contain duplicate predicates")
    return ordered


@dataclass(frozen=True)
class RulebookDefinition:
    """Portable long-only daily rulebook semantics, without result provenance."""

    buy_predicates: tuple[PredicateSpec, ...]
    gates: tuple[PredicateSpec, ...] = ()
    filters: tuple[PredicateSpec, ...] = ()
    exits: tuple[PredicateSpec, ...] = ()
    atr_primitive: PrimitiveSpec | None = None
    atr_stop_multiplier: Decimal | None = None
    atr_target_multiplier: Decimal | None = None
    atr_trailing_multiplier: Decimal | None = None
    min_hold_bars: int = 3
    max_hold_bars: int = 64
    definition_revision: str = "flexible-rulebook-definition-v1"

    def __post_init__(self) -> None:
        buy_predicates = _normalize_predicate_group(
            self.buy_predicates,
            "buy_predicates",
            ("buy",),
        )
        if not buy_predicates:
            raise ValueError("buy_predicates must contain at least one predicate")
        gates = _normalize_predicate_group(self.gates, "gates", ("gate",))
        filters = _normalize_predicate_group(self.filters, "filters", ("filter",))
        exits = _normalize_predicate_group(self.exits, "exits", ("technical_sell",))
        entry_filters = tuple(
            sorted(
                (predicate.to_dict(include_role=False) for predicate in (*gates, *filters)),
                key=canonical_json,
            )
        )
        if len({canonical_json(predicate) for predicate in entry_filters}) != len(entry_filters):
            raise ValueError("gates and filters must not duplicate one another")
        if (
            isinstance(self.min_hold_bars, bool)
            or not isinstance(self.min_hold_bars, int)
            or self.min_hold_bars != 3
        ):
            raise ValueError("min_hold_bars must equal 3")
        if (
            isinstance(self.max_hold_bars, bool)
            or not isinstance(self.max_hold_bars, int)
            or not 4 <= self.max_hold_bars <= 64
        ):
            raise ValueError("max_hold_bars must be an integer from 4 through 64")
        object.__setattr__(self, "buy_predicates", buy_predicates)
        object.__setattr__(self, "gates", gates)
        object.__setattr__(self, "filters", filters)
        object.__setattr__(self, "exits", exits)
        stop_multiplier = _positive_decimal(
            self.atr_stop_multiplier,
            "atr_stop_multiplier",
        )
        target_multiplier = _positive_decimal(
            self.atr_target_multiplier,
            "atr_target_multiplier",
        )
        trailing_multiplier = _positive_decimal(
            self.atr_trailing_multiplier,
            "atr_trailing_multiplier",
        )
        has_price_exit = any(value is not None for value in (
            stop_multiplier,
            target_multiplier,
            trailing_multiplier,
        ))
        atr14 = PrimitiveSpec(
            family="atr",
            family_revision="atr-wilder-v1",
            settings=(("period", 14),),
        )
        if has_price_exit:
            if self.atr_primitive is not None and self.atr_primitive != atr14:
                raise ValueError("Flexible price exits require fixed ATR(14)")
            object.__setattr__(self, "atr_primitive", atr14)
        elif self.atr_primitive is not None:
            raise ValueError("ATR primitive requires an enabled ATR price exit")
        object.__setattr__(self, "atr_stop_multiplier", stop_multiplier)
        object.__setattr__(self, "atr_target_multiplier", target_multiplier)
        object.__setattr__(self, "atr_trailing_multiplier", trailing_multiplier)
        object.__setattr__(self, "definition_revision", _require_non_blank(
            self.definition_revision,
            "definition_revision",
        ))

    def to_semantic_dict(self) -> dict[str, object]:
        entry_filters = tuple(
            sorted(
                (predicate.to_dict(include_role=False) for predicate in (*self.gates, *self.filters)),
                key=canonical_json,
            )
        )
        return {
            "definition_revision": self.definition_revision,
            "buy_predicates": [predicate.to_dict() for predicate in self.buy_predicates],
            "entry_filters": list(entry_filters),
            "technical_sell_predicates": [predicate.to_dict() for predicate in self.exits],
            "atr_primitive": (
                self.atr_primitive.to_dict() if self.atr_primitive is not None else None
            ),
            "atr_price_exits": {
                "stop_multiplier": self.atr_stop_multiplier,
                "target_multiplier": self.atr_target_multiplier,
                "trailing_multiplier": self.atr_trailing_multiplier,
            },
            "min_hold_bars": self.min_hold_bars,
            "max_hold_bars": self.max_hold_bars,
        }


def rulebook_id(definition: RulebookDefinition) -> str:
    """Return the portable definition identity, excluding ticker and results."""

    if not isinstance(definition, RulebookDefinition):
        raise ValueError("definition must be a RulebookDefinition")
    return f"frb_{_digest(definition.to_semantic_dict())}"


@dataclass(frozen=True)
class ExecutionContract:
    """Frozen daily next-open execution semantics for evaluation provenance."""

    execution_revision: str = "flexible-daily-execution-v1"
    native_timeframe: str = "daily"
    entry_fill_model: str = "next_open"
    min_hold_bars: int = 3
    exit_precedence_revision: str = "queued-technical-price-stop-first-timeout-v1"
    trailing_state_revision: str = "prior-high-water-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_revision", _require_non_blank(
            self.execution_revision,
            "execution_revision",
        ))
        if self.native_timeframe != "daily":
            raise ValueError("Flexible execution supports daily bars only")
        if self.entry_fill_model != "next_open":
            raise ValueError("Flexible execution uses next_open entry fills")
        if (
            isinstance(self.min_hold_bars, bool)
            or not isinstance(self.min_hold_bars, int)
            or self.min_hold_bars != 3
        ):
            raise ValueError("Flexible execution requires min_hold_bars == 3")
        object.__setattr__(self, "exit_precedence_revision", _require_non_blank(
            self.exit_precedence_revision,
            "exit_precedence_revision",
        ))
        object.__setattr__(self, "trailing_state_revision", _require_non_blank(
            self.trailing_state_revision,
            "trailing_state_revision",
        ))

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "execution_revision": self.execution_revision,
            "native_timeframe": self.native_timeframe,
            "entry_fill_model": self.entry_fill_model,
            "min_hold_bars": self.min_hold_bars,
            "exit_precedence_revision": self.exit_precedence_revision,
            "trailing_state_revision": self.trailing_state_revision,
        }

    @property
    def execution_contract_hash(self) -> str:
        return f"frec_{_digest(self.to_identity_dict())}"


@dataclass(frozen=True)
class EvaluationPartition:
    """One inclusive native-bar evaluation boundary."""

    label: str
    start: date
    end: date
    start_ordinal: int
    end_ordinal: int
    row_count: int

    def __post_init__(self) -> None:
        if self.label not in ("training", "test"):
            raise ValueError("partition label must be training or test")
        if (
            not _is_native_bar_date(self.start)
            or not _is_native_bar_date(self.end)
            or self.start > self.end
        ):
            raise ValueError("partition dates must be ordered dates")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.start_ordinal, self.end_ordinal)
        ):
            raise ValueError("partition ordinals must be non-negative integers")
        if self.end_ordinal < self.start_ordinal:
            raise ValueError("partition end ordinal must not precede start ordinal")
        if (
            isinstance(self.row_count, bool)
            or not isinstance(self.row_count, int)
            or self.row_count != self.end_ordinal - self.start_ordinal + 1
        ):
            raise ValueError("partition row_count must match inclusive ordinal bounds")

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "start_ordinal": self.start_ordinal,
            "end_ordinal": self.end_ordinal,
            "row_count": self.row_count,
        }


@dataclass(frozen=True)
class EvaluationSplit:
    """One frozen native-bar train/test split."""

    method: str
    requested_test_cutoff: date | None
    training: EvaluationPartition
    test: EvaluationPartition

    def __post_init__(self) -> None:
        if self.method not in _SPLIT_METHODS:
            raise ValueError(f"method must be one of {_SPLIT_METHODS}")
        if self.method == "calendar_10y_5y" and not _is_native_bar_date(self.requested_test_cutoff):
            raise ValueError("calendar split requires a requested test cutoff")
        if self.method == "chronological_65_35" and self.requested_test_cutoff is not None:
            raise ValueError("chronological split cannot define a calendar cutoff")
        if self.training.label != "training" or self.test.label != "test":
            raise ValueError("split partitions must be labeled training and test")
        if self.training.end >= self.test.start:
            raise ValueError("training must end before test begins")
        if self.training.end_ordinal + 1 != self.test.start_ordinal:
            raise ValueError("split partitions must be native-bar contiguous")

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "requested_test_cutoff": self.requested_test_cutoff,
            "training": self.training.to_identity_dict(),
            "test": self.test.to_identity_dict(),
        }


@dataclass(frozen=True)
class RuntimeBudget:
    """The immutable under-five-hour candidate admission/terminal contract."""

    candidate_admission_seconds: int = 16_200
    normal_terminal_seconds: int = 17_700
    outer_worker_watchdog_seconds: int = 18_000

    def __post_init__(self) -> None:
        values = (
            self.candidate_admission_seconds,
            self.normal_terminal_seconds,
            self.outer_worker_watchdog_seconds,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("runtime deadlines must be positive integers")
        if self.candidate_admission_seconds > 16_200:
            raise ValueError("candidate admission deadline cannot exceed 16,200 seconds")
        if self.normal_terminal_seconds > 17_700:
            raise ValueError("normal terminal deadline cannot exceed 17,700 seconds")
        if self.outer_worker_watchdog_seconds > 18_000:
            raise ValueError("outer worker watchdog cannot exceed 18,000 seconds")
        if not (
            self.candidate_admission_seconds < self.normal_terminal_seconds < self.outer_worker_watchdog_seconds
        ):
            raise ValueError("runtime deadlines must have candidate < terminal < watchdog ordering")
        if self.normal_terminal_seconds - self.candidate_admission_seconds < 1_500:
            raise ValueError("runtime budget must retain the 25-minute terminal reserve")

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "candidate_admission_seconds": self.candidate_admission_seconds,
            "normal_terminal_seconds": self.normal_terminal_seconds,
            "outer_worker_watchdog_seconds": self.outer_worker_watchdog_seconds,
        }


@dataclass(frozen=True)
class FeatureSnapshot:
    """Portable identity for one fresh, validated raw-history source."""

    ticker: str
    raw_history_fingerprint: str
    requested_start: date
    requested_as_of: date
    first_date: date
    as_of_date: date
    quality_state: str
    quality_revision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        object.__setattr__(self, "raw_history_fingerprint", _require_hash(
            self.raw_history_fingerprint,
            "raw_history_fingerprint",
        ))
        if not all(_is_native_bar_date(value) for value in (
            self.requested_start,
            self.requested_as_of,
            self.first_date,
            self.as_of_date,
        )):
            raise ValueError("feature snapshot dates must be dates")
        if self.requested_start > self.requested_as_of or self.first_date > self.as_of_date:
            raise ValueError("feature snapshot dates must be ordered")
        if self.first_date < self.requested_start or self.as_of_date > self.requested_as_of:
            raise ValueError("feature snapshot actual dates must remain inside requested bounds")
        if self.quality_state not in _QUALITY_STATES:
            raise ValueError(f"quality_state must be one of {_QUALITY_STATES}")
        object.__setattr__(self, "quality_revision", _require_non_blank(
            self.quality_revision,
            "quality_revision",
        ))

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "raw_history_fingerprint": self.raw_history_fingerprint,
            "requested_start": self.requested_start,
            "requested_as_of": self.requested_as_of,
            "first_date": self.first_date,
            "as_of_date": self.as_of_date,
            "quality_state": self.quality_state,
            "quality_revision": self.quality_revision,
        }


@dataclass(frozen=True)
class FeatureProfile:
    """Canonical base primitive requirements, independent from predicate masks."""

    primitive_specs: tuple[PrimitiveSpec, ...]

    def __post_init__(self) -> None:
        if isinstance(self.primitive_specs, (str, bytes)):
            raise ValueError("primitive_specs must be a sequence")
        try:
            specs = tuple(self.primitive_specs)
        except TypeError as error:
            raise ValueError("primitive_specs must be a sequence") from error
        if not specs or any(not isinstance(spec, PrimitiveSpec) for spec in specs):
            raise ValueError("primitive_specs must contain at least one PrimitiveSpec")
        ordered = tuple(sorted(specs, key=lambda spec: canonical_json(spec.to_dict())))
        if len({canonical_json(spec.to_dict()) for spec in ordered}) != len(ordered):
            raise ValueError("primitive_specs must not contain duplicates")
        object.__setattr__(self, "primitive_specs", ordered)

    def to_identity_dict(self) -> dict[str, object]:
        return {"primitive_specs": [spec.to_dict() for spec in self.primitive_specs]}

    @property
    def feature_profile_hash(self) -> str:
        return f"frfp_{_digest(self.to_identity_dict())}"


@dataclass(frozen=True)
class FeatureBuildContract:
    """Frozen causal feature-build semantics; cache age/path never enter it."""

    feature_algorithm_revision: str = "flexible-features-v1"
    warmup_policy_revision: str = "full-history-causal-v1"
    quality_policy_revision: str = "flexible-quality-v1"
    numeric_runtime_revision: str = "numpy-pandas-flexible-v1"
    raw_price_scale: int = 1000
    cache_schema_revision: str = "primitive-cache-v1"
    append_extension_enabled: bool = False
    append_extension_algorithm_revision: str | None = None
    append_stream_state_schema_revision: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "feature_algorithm_revision",
            "warmup_policy_revision",
            "quality_policy_revision",
            "numeric_runtime_revision",
            "cache_schema_revision",
        ):
            object.__setattr__(self, name, _require_non_blank(getattr(self, name), name))
        if (
            isinstance(self.raw_price_scale, bool)
            or not isinstance(self.raw_price_scale, int)
            or self.raw_price_scale <= 0
        ):
            raise ValueError("raw_price_scale must be a positive integer")
        if not isinstance(self.append_extension_enabled, bool):
            raise ValueError("append_extension_enabled must be boolean")
        if self.append_extension_enabled:
            object.__setattr__(self, "append_extension_algorithm_revision", _require_non_blank(
                self.append_extension_algorithm_revision,
                "append_extension_algorithm_revision",
            ))
            object.__setattr__(self, "append_stream_state_schema_revision", _require_non_blank(
                self.append_stream_state_schema_revision,
                "append_stream_state_schema_revision",
            ))
        elif (
            self.append_extension_algorithm_revision is not None
            or self.append_stream_state_schema_revision is not None
        ):
            raise ValueError("disabled append extension cannot declare append revisions")

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "feature_algorithm_revision": self.feature_algorithm_revision,
            "warmup_policy_revision": self.warmup_policy_revision,
            "quality_policy_revision": self.quality_policy_revision,
            "numeric_runtime_revision": self.numeric_runtime_revision,
            "raw_price_scale": self.raw_price_scale,
            "cache_schema_revision": self.cache_schema_revision,
            "append_extension_enabled": self.append_extension_enabled,
            "append_extension_algorithm_revision": self.append_extension_algorithm_revision,
            "append_stream_state_schema_revision": self.append_stream_state_schema_revision,
        }

    @property
    def feature_build_contract_hash(self) -> str:
        return f"frbc_{_digest(self.to_identity_dict())}"


@dataclass(frozen=True)
class PrimitiveKey:
    """Computed identity for one reusable component under a frozen source/build."""

    snapshot: FeatureSnapshot
    build_contract: FeatureBuildContract
    primitive_spec: PrimitiveSpec

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, FeatureSnapshot):
            raise ValueError("snapshot must be a FeatureSnapshot")
        if not isinstance(self.build_contract, FeatureBuildContract):
            raise ValueError("build_contract must be a FeatureBuildContract")
        if not isinstance(self.primitive_spec, PrimitiveSpec):
            raise ValueError("primitive_spec must be a PrimitiveSpec")

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "snapshot": self.snapshot.to_identity_dict(),
            "feature_build_contract_hash": self.build_contract.feature_build_contract_hash,
            "primitive_spec": self.primitive_spec.to_dict(),
        }

    @property
    def primitive_key(self) -> str:
        return f"frpk_{_digest(self.to_identity_dict())}"


@dataclass(frozen=True)
class FeaturePlan:
    """A request-scoped canonical primitive-key set derived without cache state."""

    snapshot: FeatureSnapshot
    build_contract: FeatureBuildContract
    profile: FeatureProfile
    primitive_keys: tuple[PrimitiveKey, ...] = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, FeatureSnapshot):
            raise ValueError("snapshot must be a FeatureSnapshot")
        if not isinstance(self.build_contract, FeatureBuildContract):
            raise ValueError("build_contract must be a FeatureBuildContract")
        if not isinstance(self.profile, FeatureProfile):
            raise ValueError("profile must be a FeatureProfile")
        keys = tuple(
            PrimitiveKey(self.snapshot, self.build_contract, spec)
            for spec in self.profile.primitive_specs
        )
        object.__setattr__(self, "primitive_keys", keys)

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "snapshot": self.snapshot.to_identity_dict(),
            "feature_build_contract_hash": self.build_contract.feature_build_contract_hash,
            "feature_profile_hash": self.profile.feature_profile_hash,
            "primitive_keys": [key.primitive_key for key in self.primitive_keys],
        }

    @property
    def feature_plan_hash(self) -> str:
        return f"frpl_{_digest(self.to_identity_dict())}"


@dataclass(frozen=True)
class FeatureResolutionReceipt:
    """Resolved component bytes for one FeaturePlan, before any slot commits."""

    plan: FeaturePlan
    resolved_components: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plan, FeaturePlan):
            raise ValueError("plan must be a FeaturePlan")
        if isinstance(self.resolved_components, (str, bytes)):
            raise ValueError("resolved_components must be ordered key/digest pairs")
        try:
            components = tuple(self.resolved_components)
        except TypeError as error:
            raise ValueError("resolved_components must be ordered key/digest pairs") from error
        normalized: list[tuple[str, str]] = []
        for component in components:
            if not isinstance(component, (tuple, list)) or len(component) != 2:
                raise ValueError("resolved_components must be key/digest pairs")
            key, digest = component
            if not isinstance(key, str) or not isinstance(digest, str) or not _HASH_PATTERN.fullmatch(digest):
                raise ValueError("resolved component values are invalid")
            normalized.append((key, digest))
        expected = tuple(key.primitive_key for key in self.plan.primitive_keys)
        if tuple(key for key, _ in normalized) != expected:
            raise ValueError("resolved components must exactly match FeaturePlan key order")
        object.__setattr__(self, "resolved_components", tuple(normalized))

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "feature_plan_hash": self.plan.feature_plan_hash,
            "resolved_components": list(self.resolved_components),
        }

    @property
    def receipt_id(self) -> str:
        return f"frpr_{_digest(self.to_identity_dict())}"


@dataclass(frozen=True)
class SelectionPolicy:
    """Frozen Top-3 training timing-distinctness policy."""

    policy_revision: str = "timing-distinct-top3-v1"
    pairing_algorithm_revision: str = "inclusive-two-pointer-v1"
    max_representatives: int = 3
    training_overlap_ratio: Decimal = Decimal("0.75")

    def __post_init__(self) -> None:
        if self.policy_revision != "timing-distinct-top3-v1":
            raise ValueError("unsupported selection policy revision")
        if self.pairing_algorithm_revision != "inclusive-two-pointer-v1":
            raise ValueError("unsupported pairing algorithm revision")
        if (
            isinstance(self.max_representatives, bool)
            or not isinstance(self.max_representatives, int)
            or self.max_representatives != 3
        ):
            raise ValueError("phase-one selection keeps exactly three representatives maximum")
        if (
            not isinstance(self.training_overlap_ratio, Decimal)
            or self.training_overlap_ratio != Decimal("0.75")
        ):
            raise ValueError("training_overlap_ratio must equal Decimal('0.75')")

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "policy_revision": self.policy_revision,
            "pairing_algorithm_revision": self.pairing_algorithm_revision,
            "max_representatives": self.max_representatives,
            "training_overlap_ratio": self.training_overlap_ratio,
        }


def _metric_value(value: object, name: str, *, nullable: bool) -> float | Decimal | None:
    if value is None:
        if nullable:
            return None
        raise ValueError(f"{name} must be finite")
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
        return float(value)
    raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class PartitionMetrics:
    """Exact gross metrics for one completed-trade partition."""

    n: int
    win_rate: float | Decimal | None
    total_return_pct: float | Decimal
    mean_return_pct: float | Decimal | None
    sharpe: float | Decimal | None

    def __post_init__(self) -> None:
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 0:
            raise ValueError("n must be a non-negative integer")
        win_rate = _metric_value(self.win_rate, "win_rate", nullable=self.n == 0)
        total_return_pct = _metric_value(self.total_return_pct, "total_return_pct", nullable=False)
        mean_return_pct = _metric_value(self.mean_return_pct, "mean_return_pct", nullable=self.n == 0)
        sharpe = _metric_value(self.sharpe, "sharpe", nullable=True)
        if self.n == 0:
            if win_rate is not None or mean_return_pct is not None or total_return_pct != 0:
                raise ValueError("empty partitions require null win/mean metrics and zero total return")
        else:
            if win_rate is None or mean_return_pct is None or not 0 <= win_rate <= 100:
                raise ValueError("non-empty partitions require a win rate from 0 through 100")
        if self.n < 2 and sharpe is not None:
            raise ValueError("partitions with fewer than two trades require null sharpe")
        object.__setattr__(self, "win_rate", win_rate)
        object.__setattr__(self, "total_return_pct", total_return_pct)
        object.__setattr__(self, "mean_return_pct", mean_return_pct)
        object.__setattr__(self, "sharpe", sharpe)

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "win_rate": self.win_rate,
            "total_return_pct": self.total_return_pct,
            "mean_return_pct": self.mean_return_pct,
            "sharpe": self.sharpe,
        }


@dataclass(frozen=True)
class RulebookEvaluation:
    """One immutable ticker/source/split evaluation of a portable definition."""

    definition: RulebookDefinition
    ticker: str
    source_snapshot: FeatureSnapshot
    catalog_hash: str
    split: EvaluationSplit
    execution_contract: ExecutionContract
    feature_build_contract: FeatureBuildContract
    feature_profile: FeatureProfile
    feature_receipt: FeatureResolutionReceipt
    training_metrics: PartitionMetrics
    test_metrics: PartitionMetrics
    qualification_revision: str = "both-partitions-12-65-15-v1"
    state: str = "evaluated"
    training_trades: tuple[object, ...] = ()
    test_trades: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.definition, RulebookDefinition):
            raise ValueError("definition must be a RulebookDefinition")
        ticker = _normalize_ticker(self.ticker)
        if not isinstance(self.source_snapshot, FeatureSnapshot) or ticker != self.source_snapshot.ticker:
            raise ValueError("ticker must match the source snapshot")
        object.__setattr__(self, "ticker", ticker)
        object.__setattr__(self, "catalog_hash", _require_hash(self.catalog_hash, "catalog_hash"))
        if not isinstance(self.split, EvaluationSplit):
            raise ValueError("split must be an EvaluationSplit")
        if not isinstance(self.execution_contract, ExecutionContract):
            raise ValueError("execution_contract must be an ExecutionContract")
        if not isinstance(self.feature_build_contract, FeatureBuildContract):
            raise ValueError("feature_build_contract must be a FeatureBuildContract")
        if not isinstance(self.feature_profile, FeatureProfile):
            raise ValueError("feature_profile must be a FeatureProfile")
        definition_primitive_keys = {
            canonical_json(predicate.primitive.to_dict())
            for predicate in (
                *self.definition.buy_predicates,
                *self.definition.gates,
                *self.definition.filters,
                *self.definition.exits,
            )
        }
        if self.definition.atr_primitive is not None:
            definition_primitive_keys.add(
                canonical_json(self.definition.atr_primitive.to_dict())
            )
        profile_primitive_keys = {
            canonical_json(spec.to_dict())
            for spec in self.feature_profile.primitive_specs
        }
        if not definition_primitive_keys <= profile_primitive_keys:
            raise ValueError("feature_profile must cover every rulebook primitive")
        if not isinstance(self.feature_receipt, FeatureResolutionReceipt):
            raise ValueError("feature_receipt must be a FeatureResolutionReceipt")
        receipt_plan = self.feature_receipt.plan
        if (
            receipt_plan.snapshot != self.source_snapshot
            or receipt_plan.build_contract != self.feature_build_contract
            or receipt_plan.profile != self.feature_profile
        ):
            raise ValueError("feature receipt must match evaluation source and feature contracts")
        if not isinstance(self.training_metrics, PartitionMetrics) or not isinstance(self.test_metrics, PartitionMetrics):
            raise ValueError("evaluation metrics must be PartitionMetrics")
        # Local import prevents the contracts/execution module cycle at import time.
        from .execution import CompletedTrade

        for name, trades, metrics in (
            ("training_trades", self.training_trades, self.training_metrics),
            ("test_trades", self.test_trades, self.test_metrics),
        ):
            if not isinstance(trades, tuple) or any(not isinstance(trade, CompletedTrade) for trade in trades):
                raise ValueError(f"{name} must be an immutable CompletedTrade tuple")
            ordered = tuple(sorted(
                trades,
                key=lambda trade: (trade.entry_bar_ordinal, trade.exit_bar_ordinal, trade.trade_id),
            ))
            if trades != ordered:
                raise ValueError(f"{name} must use canonical native-bar order")
            if len({trade.trade_id for trade in trades}) != len(trades):
                raise ValueError(f"{name} trade IDs must be unique")
            if len(trades) != metrics.n:
                raise ValueError(f"{name} count must match partition metrics n")
            object.__setattr__(self, name, trades)
        object.__setattr__(self, "qualification_revision", _require_non_blank(
            self.qualification_revision,
            "qualification_revision",
        ))
        object.__setattr__(self, "state", _require_non_blank(self.state, "state"))

    @property
    def rulebook_id(self) -> str:
        return rulebook_id(self.definition)

    @property
    def feature_receipt_id(self) -> str:
        return self.feature_receipt.receipt_id

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "rulebook_id": self.rulebook_id,
            "ticker": self.ticker,
            "source_snapshot": self.source_snapshot.to_identity_dict(),
            "catalog_hash": self.catalog_hash,
            "split": self.split.to_identity_dict(),
            "execution_contract_hash": self.execution_contract.execution_contract_hash,
            "feature_build_contract_hash": self.feature_build_contract.feature_build_contract_hash,
            "feature_profile_hash": self.feature_profile.feature_profile_hash,
            "feature_receipt_id": self.feature_receipt_id,
            "qualification_revision": self.qualification_revision,
        }

    @property
    def evaluation_id(self) -> str:
        return f"frev_{_digest(self.to_identity_dict())}"


def animal_alias(identifier: str) -> str:
    """Return display-only animals-50-v1 alias for one full rulebook hash."""

    if not isinstance(identifier, str) or not re.fullmatch(r"frb_[0-9a-f]{64}", identifier):
        raise ValueError("identifier must be a full frb_ SHA-256 rulebook ID")
    pairs = tuple(itertools.combinations(ANIMAL_POOL_V1, 2))
    return "-".join(pairs[int(identifier[4:], 16) % len(pairs)])


__all__ = [
    "ANIMAL_POOL_V1",
    "EvaluationPartition",
    "EvaluationSplit",
    "ExecutionContract",
    "FeatureBuildContract",
    "FeaturePlan",
    "FeatureProfile",
    "FeatureResolutionReceipt",
    "FeatureSnapshot",
    "PartitionMetrics",
    "PredicateSpec",
    "PrimitiveKey",
    "PrimitiveSpec",
    "RulebookDefinition",
    "RulebookEvaluation",
    "RuntimeBudget",
    "SelectionPolicy",
    "animal_alias",
    "canonical_json",
    "rulebook_id",
]
