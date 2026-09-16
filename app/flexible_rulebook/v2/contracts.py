"""Immutable semantic contracts for the user-authored Flexible Rulebook v2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

import pytz


HORIZONS = ("swing", "midterm")
ENTRY_OPERATORS = ("all", "any")
PREDICATE_ROLES = ("buy", "gate", "technical_sell")
TRAINING_RATIOS = tuple(Decimal(value) / Decimal("100") for value in range(50, 81, 5))
_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
_HCM = pytz.timezone("Asia/Ho_Chi_Minh")
_UNSET = object()


Scalar = str | int | bool | Decimal | None
Pairs = tuple[tuple[str, Scalar], ...]


def _require_text(value: object, name: str, *, allow_blank: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    normalized = value.strip()
    if not normalized and not allow_blank:
        raise ValueError(f"{name} must be non-empty text")
    return normalized


def _require_token(value: object, name: str) -> str:
    normalized = _require_text(value, name)
    if not _TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError(f"{name} must be a lowercase token")
    return normalized


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _normalize_scalar(value: object, name: str) -> Scalar:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _require_text(value, name)
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        return value.normalize() if value else Decimal("0")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        try:
            normalized = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError(f"{name} must be finite") from error
        return normalized.normalize() if normalized else Decimal("0")
    raise ValueError(f"{name} must be a portable scalar")


def _normalize_pairs(value: object, name: str) -> Pairs:
    if isinstance(value, Mapping):
        raw_pairs = tuple(value.items())
    else:
        if isinstance(value, (str, bytes)):
            raise ValueError(f"{name} must be key/value pairs")
        try:
            raw_pairs = tuple(value)  # type: ignore[arg-type]
        except TypeError as error:
            raise ValueError(f"{name} must be key/value pairs") from error

    normalized: list[tuple[str, Scalar]] = []
    for pair in raw_pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f"{name} must contain two-value pairs")
        key = _require_token(pair[0], f"{name} key")
        normalized.append((key, _normalize_scalar(pair[1], f"{name}.{key}")))
    normalized.sort(key=lambda item: item[0])
    if len({key for key, _ in normalized}) != len(normalized):
        raise ValueError(f"{name} keys must be unique")
    return tuple(normalized)


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not result.is_finite():
        raise ValueError(f"{name} must be a finite number")
    return result.normalize() if result else Decimal("0")


def _positive_decimal(value: object, name: str, *, maximum: Decimal) -> Decimal | None:
    if value is None:
        return None
    result = _decimal(value, name)
    if result < Decimal("0.1") or result > maximum:
        raise ValueError(f"{name} must be from 0.1 through {maximum}")
    return result


def _normalize_timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(_HCM)


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("canonical decimal must be finite")
        normalized = value.normalize() if value else Decimal("0")
        return {"$decimal": format(normalized, "f")}
    if isinstance(value, float):
        return _canonical_value(_normalize_scalar(value, "canonical float"))
    if isinstance(value, datetime):
        return {"$datetime": _normalize_timestamp(value, "datetime").isoformat()}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, UUID):
        return {"$uuid": str(value)}
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ValueError("canonical mappings require string keys")
            normalized[key] = _canonical_value(value[key])
        return normalized
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if hasattr(value, "to_semantic_dict"):
        return _canonical_value(value.to_semantic_dict())
    raise ValueError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Return deterministic JSON for portable semantic identity material."""

    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def semantic_digest(value: object) -> str:
    """Return a raw SHA-256 digest for semantic content only."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_predicate_group(
    value: object,
    name: str,
    *,
    expected_role: str,
) -> tuple["PredicateV2", ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    try:
        predicates = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error
    if any(not isinstance(predicate, PredicateV2) for predicate in predicates):
        raise ValueError(f"{name} must contain PredicateV2 values")
    if any(predicate.role != expected_role for predicate in predicates):
        raise ValueError(f"{name} must contain only {expected_role} predicates")
    ordered = tuple(sorted(predicates, key=lambda predicate: canonical_json(predicate.to_semantic_dict())))
    identities = [canonical_json(predicate.to_semantic_dict()) for predicate in ordered]
    if len(set(identities)) != len(identities):
        raise ValueError(f"{name} contain duplicate predicates")
    return ordered


@dataclass(frozen=True)
class PredicateV2:
    """A typed condition owned by one registered indicator formula revision."""

    role: str
    family: str
    family_revision: str
    settings: Mapping[str, object] | Sequence[tuple[str, object]] = field(default_factory=tuple)
    operator: str = "state"
    condition: Mapping[str, object] | Sequence[tuple[str, object]] = field(default_factory=tuple)
    direction_lookback: int | None = None

    def __post_init__(self) -> None:
        if self.role not in PREDICATE_ROLES:
            raise ValueError(f"role must be one of {PREDICATE_ROLES}")
        object.__setattr__(self, "family", _require_token(self.family, "family"))
        object.__setattr__(self, "family_revision", _require_text(self.family_revision, "family_revision"))
        object.__setattr__(self, "operator", _require_token(self.operator, "operator"))
        object.__setattr__(self, "settings", _normalize_pairs(self.settings, "settings"))
        object.__setattr__(self, "condition", _normalize_pairs(self.condition, "condition"))
        if self.direction_lookback is not None:
            if (
                isinstance(self.direction_lookback, bool)
                or not isinstance(self.direction_lookback, int)
                or not 1 <= self.direction_lookback <= 20
            ):
                raise ValueError("direction_lookback must be an integer from 1 through 20")

    @property
    def settings_dict(self) -> dict[str, Scalar]:
        return dict(self.settings)

    @property
    def condition_dict(self) -> dict[str, Scalar]:
        return dict(self.condition)

    def to_semantic_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "family": self.family,
            "family_revision": self.family_revision,
            "settings": self.settings_dict,
            "operator": self.operator,
            "condition": self.condition_dict,
            "direction_lookback": self.direction_lookback,
        }


@dataclass(frozen=True)
class AtrExitV2:
    """Definition-owned ATR price exits; at least one enabled exit is required."""

    period: int = 14
    formula_revision: str = "atr-wilder-sma-seeded-v1"
    stop_multiplier: Decimal | float | int | None = None
    target_multiplier: Decimal | float | int | None = None
    trailing_multiplier: Decimal | float | int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.period, bool) or not isinstance(self.period, int) or not 2 <= self.period <= 100:
            raise ValueError("ATR period must be an integer from 2 through 100")
        object.__setattr__(self, "formula_revision", _require_text(self.formula_revision, "formula_revision"))
        stop = _positive_decimal(self.stop_multiplier, "stop_multiplier", maximum=Decimal("20"))
        target = _positive_decimal(self.target_multiplier, "target_multiplier", maximum=Decimal("20"))
        trailing = _positive_decimal(self.trailing_multiplier, "trailing_multiplier", maximum=Decimal("20"))
        if not any(value is not None for value in (stop, target, trailing)):
            raise ValueError("ATR exit requires stop, target, or trailing multiplier")
        object.__setattr__(self, "stop_multiplier", stop)
        object.__setattr__(self, "target_multiplier", target)
        object.__setattr__(self, "trailing_multiplier", trailing)

    def to_semantic_dict(self) -> dict[str, object]:
        return {
            "period": self.period,
            "formula_revision": self.formula_revision,
            "stop_multiplier": self.stop_multiplier,
            "target_multiplier": self.target_multiplier,
            "trailing_multiplier": self.trailing_multiplier,
        }


@dataclass(frozen=True)
class RulebookDefinitionV2:
    """One bounded long-only rulebook semantic definition for one horizon."""

    horizon: str
    entry_operator: str
    buy_predicates: Sequence[PredicateV2]
    gates: Sequence[PredicateV2] = field(default_factory=tuple)
    technical_exits: Sequence[PredicateV2] = field(default_factory=tuple)
    atr_exit: AtrExitV2 | None = None
    min_hold_bars: int = 3
    max_hold_bars: int = 22
    semantic_revision: str = "flexible-rulebook-v2"

    def __post_init__(self) -> None:
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        if self.entry_operator not in ENTRY_OPERATORS:
            raise ValueError("entry_operator must be 'all' or 'any'")
        buys = _normalize_predicate_group(self.buy_predicates, "buy_predicates", expected_role="buy")
        if not buys:
            raise ValueError("at least one BUY predicate is required")
        gates = _normalize_predicate_group(self.gates, "gates", expected_role="gate")
        exits = _normalize_predicate_group(
            self.technical_exits,
            "technical_exits",
            expected_role="technical_sell",
        )
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
        if self.atr_exit is not None and not isinstance(self.atr_exit, AtrExitV2):
            raise ValueError("atr_exit must be AtrExitV2 or None")
        object.__setattr__(self, "buy_predicates", buys)
        object.__setattr__(self, "gates", gates)
        object.__setattr__(self, "technical_exits", exits)
        object.__setattr__(self, "semantic_revision", _require_text(self.semantic_revision, "semantic_revision"))

    @property
    def native_timeframe(self) -> str:
        return "daily" if self.horizon == "swing" else "weekly"

    @property
    def weekly_frequency(self) -> str | None:
        """Expose the one valid weekly execution calendar for Mid-term rules."""

        return None if self.horizon == "swing" else "W-FRI"

    def to_semantic_dict(self) -> dict[str, object]:
        return {
            "semantic_revision": self.semantic_revision,
            "horizon": self.horizon,
            "native_timeframe": self.native_timeframe,
            "weekly_frequency": self.weekly_frequency,
            "entry_operator": self.entry_operator,
            "buy_predicates": [item.to_semantic_dict() for item in self.buy_predicates],
            "gates": [item.to_semantic_dict() for item in self.gates],
            "technical_exits": [item.to_semantic_dict() for item in self.technical_exits],
            "atr_exit": self.atr_exit.to_semantic_dict() if self.atr_exit else None,
            "min_hold_bars": self.min_hold_bars,
            "max_hold_bars": self.max_hold_bars,
        }

    @property
    def semantic_digest(self) -> str:
        return semantic_digest(self.to_semantic_dict())

    def validate(self, registry: Any) -> None:
        """Reject unsupported roles, settings, and predicates before a run starts."""

        for predicate in (*self.buy_predicates, *self.gates, *self.technical_exits):
            registry.validate_predicate(predicate, horizon=self.horizon)
        if self.atr_exit is not None:
            registry.validate_atr_exit(self.atr_exit, horizon=self.horizon)


@dataclass(frozen=True)
class RulebookDraft:
    """Mutable by revision replacement; names and timestamps never affect semantics."""

    draft_id: str
    revision: int
    name: str
    description: str
    definition: RulebookDefinitionV2
    created_at: datetime
    updated_at: datetime
    state: str = "draft"

    def __post_init__(self) -> None:
        try:
            normalized_id = str(UUID(str(self.draft_id)))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("draft_id must be a UUID") from error
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.definition, RulebookDefinitionV2):
            raise ValueError("definition must be RulebookDefinitionV2")
        created_at = _normalize_timestamp(self.created_at, "created_at")
        updated_at = _normalize_timestamp(self.updated_at, "updated_at")
        if updated_at < created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.state != "draft":
            raise ValueError("RulebookDraft state must be draft")
        object.__setattr__(self, "draft_id", normalized_id)
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "description", _require_text(self.description, "description", allow_blank=True))
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)

    @classmethod
    def new(
        cls,
        *,
        name: str,
        definition: RulebookDefinitionV2,
        now: datetime,
        description: str = "",
    ) -> "RulebookDraft":
        timestamp = _normalize_timestamp(now, "now")
        return cls(
            draft_id=str(uuid4()),
            revision=1,
            name=name,
            description=description,
            definition=definition,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def with_changes(
        self,
        *,
        now: datetime,
        name: object = _UNSET,
        description: object = _UNSET,
        definition: object = _UNSET,
    ) -> "RulebookDraft":
        return replace(
            self,
            revision=self.revision + 1,
            name=self.name if name is _UNSET else name,
            description=self.description if description is _UNSET else description,
            definition=self.definition if definition is _UNSET else definition,
            updated_at=_normalize_timestamp(now, "now"),
        )

    def validate(self, registry: Any) -> None:
        self.definition.validate(registry)

    def is_evaluated_by(self, evaluations: Iterable["EvaluationResult"]) -> bool:
        return any(
            item.is_completed and item.semantic_digest == self.definition.semantic_digest
            for item in evaluations
        )


def _freeze_document(value: Mapping[str, object] | Sequence[object]) -> object:
    """Validate serializability while retaining native values for live consumers."""

    canonical_json(value)

    def freeze(item: object) -> object:
        if isinstance(item, Mapping):
            return MappingProxyType({key: freeze(nested) for key, nested in item.items()})
        if isinstance(item, (tuple, list)):
            return tuple(freeze(nested) for nested in item)
        return item

    return freeze(value)


@dataclass(frozen=True)
class EvaluationRequest:
    """Operational evaluation scope, deliberately excluded from definition identity."""

    semantic_digest: str
    tickers: Sequence[str]
    training_ratio: Decimal | float | int = Decimal("0.65")
    start_date: date | None = None
    end_date: date | None = None
    use_cache: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "semantic_digest", _require_digest(self.semantic_digest, "semantic_digest"))
        if isinstance(self.tickers, (str, bytes)):
            raise ValueError("tickers must be a sequence")
        normalized: list[str] = []
        for ticker in self.tickers:
            if not isinstance(ticker, str):
                raise ValueError("ticker must be text")
            value = ticker.strip().upper()
            if not _TICKER_PATTERN.fullmatch(value):
                raise ValueError("ticker must be persistence-safe text")
            normalized.append(value)
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("tickers must be non-empty and unique")
        ratio = _decimal(self.training_ratio, "training_ratio")
        if ratio > 1:
            ratio = ratio / Decimal("100")
        if ratio not in TRAINING_RATIOS:
            raise ValueError("training_ratio must be one of 50, 55, 60, 65, 70, 75, or 80 percent")
        if self.start_date is not None and type(self.start_date) is not date:
            raise ValueError("start_date must be a date")
        if self.end_date is not None and type(self.end_date) is not date:
            raise ValueError("end_date must be a date")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not follow end_date")
        if not isinstance(self.use_cache, bool):
            raise ValueError("use_cache must be boolean")
        object.__setattr__(self, "tickers", tuple(normalized))
        object.__setattr__(self, "training_ratio", ratio)


@dataclass(frozen=True)
class EvaluationResult:
    """Immutable per-ticker result evidence; zero-trade completion remains valid."""

    semantic_digest: str
    ticker: str
    source: Mapping[str, object]
    split: Mapping[str, object]
    metrics: Mapping[str, object]
    trades: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    terminal_state: str = "completed"

    def __post_init__(self) -> None:
        object.__setattr__(self, "semantic_digest", _require_digest(self.semantic_digest, "semantic_digest"))
        normalized_ticker = self.ticker.strip().upper() if isinstance(self.ticker, str) else ""
        if not _TICKER_PATTERN.fullmatch(normalized_ticker):
            raise ValueError("ticker must be persistence-safe text")
        if self.terminal_state not in ("completed", "failed", "cancelled"):
            raise ValueError("terminal_state must be completed, failed, or cancelled")
        if any(not isinstance(warning, str) or not warning.strip() for warning in self.warnings):
            raise ValueError("warnings must contain non-empty text")
        object.__setattr__(self, "ticker", normalized_ticker)
        object.__setattr__(self, "source", _freeze_document(self.source))
        object.__setattr__(self, "split", _freeze_document(self.split))
        object.__setattr__(self, "metrics", _freeze_document(self.metrics))
        object.__setattr__(self, "trades", tuple(_freeze_document(item) for item in self.trades))
        object.__setattr__(self, "warnings", tuple(item.strip() for item in self.warnings))

    @classmethod
    def completed(cls, **values: object) -> "EvaluationResult":
        return cls(**(values | {"terminal_state": "completed"}))  # type: ignore[arg-type]

    @property
    def is_completed(self) -> bool:
        return self.terminal_state == "completed"


@dataclass(frozen=True)
class PublishedRulebook:
    """Immutable published semantic identity; retirement never changes the ID."""

    rulebook_id: str
    definition: RulebookDefinitionV2
    published_at: datetime
    retired_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.definition, RulebookDefinitionV2):
            raise ValueError("definition must be RulebookDefinitionV2")
        expected = f"frb2_{self.definition.semantic_digest}"
        if self.rulebook_id != expected:
            raise ValueError("rulebook_id must match the semantic definition")
        published_at = _normalize_timestamp(self.published_at, "published_at")
        retired_at = None if self.retired_at is None else _normalize_timestamp(self.retired_at, "retired_at")
        if retired_at is not None and retired_at < published_at:
            raise ValueError("retired_at must not precede published_at")
        object.__setattr__(self, "published_at", published_at)
        object.__setattr__(self, "retired_at", retired_at)

    @classmethod
    def publish(cls, definition: RulebookDefinitionV2, *, published_at: datetime) -> "PublishedRulebook":
        return cls(
            rulebook_id=f"frb2_{definition.semantic_digest}",
            definition=definition,
            published_at=published_at,
        )

    def retire(self, *, retired_at: datetime) -> "PublishedRulebook":
        if self.retired_at is not None:
            raise ValueError("published rulebook is already retired")
        return replace(self, retired_at=retired_at)

    @property
    def is_retired(self) -> bool:
        return self.retired_at is not None


def collision_safe_short_ids(
    rulebook_ids: Iterable[str],
    *,
    minimum_length: int = 8,
) -> dict[str, str]:
    """Resolve stable display prefixes while keeping full IDs as true identity."""

    if not isinstance(minimum_length, int) or not 1 <= minimum_length <= 64:
        raise ValueError("minimum_length must be an integer from 1 through 64")
    identifiers = tuple(dict.fromkeys(rulebook_ids))
    raw_digests: dict[str, str] = {}
    for identifier in identifiers:
        if not isinstance(identifier, str) or not re.fullmatch(r"frb2_[0-9a-f]{64}", identifier):
            raise ValueError("rulebook_ids must be full frb2_ SHA-256 identifiers")
        raw_digests[identifier] = identifier.removeprefix("frb2_")

    resolved: dict[str, str] = {}
    for identifier, digest in raw_digests.items():
        for length in range(minimum_length, 65):
            prefix = digest[:length]
            if sum(other.startswith(prefix) for other in raw_digests.values()) == 1:
                resolved[identifier] = f"FR-{prefix.upper()}"
                break
        else:
            raise ValueError("rulebook IDs cannot be disambiguated")
    return resolved
