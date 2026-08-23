"""Version-routed frozen exploratory identities for manual positions."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping

from .config import HORIZONS, THEME_VARIANTS, _normalize_ticker, rulebook_for
from .models import RulebookExecution


_LEGACY_CERTIFICATION_METRICS = ("win_rate", "profit", "sharpe")


def _hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_v4_position_snapshot(value: object) -> dict[str, object]:
    """Validate one new frozen Top-3 preferred exploratory candidate reference."""

    if not isinstance(value, Mapping):
        raise ValueError("V4 signal_reference must be an object")
    required = {"schema_version", "ticker", "horizon", "rulebook_id", "preferred_variant", "audit_eligible", "exploratory_candidate"}
    if set(value) not in (required, required | {"link_keys"}) or value.get("schema_version") != 4:
        raise ValueError("V4 signal_reference schema_version must be 4")
    ticker = _normalize_ticker(value["ticker"])
    if ticker != value["ticker"] or value["horizon"] not in HORIZONS or not isinstance(value["audit_eligible"], bool):
        raise ValueError("V4 signal_reference identity is invalid")
    candidate = value["exploratory_candidate"]
    if not isinstance(candidate, Mapping):
        raise ValueError("V4 signal_reference requires exploratory_candidate")
    expected = {"rulebook_id", "selected_gates", "preferred_variant", "treatments"}
    if set(candidate) != expected or not isinstance(candidate["selected_gates"], list):
        raise ValueError("V4 exploratory_candidate shape is invalid")
    try:
        execution = RulebookExecution(rulebook_for(value["horizon"]), tuple(candidate["selected_gates"]))
    except (TypeError, ValueError) as error:
        raise ValueError("V4 exploratory_candidate selected_gates are invalid") from error
    preferred = candidate["preferred_variant"]
    treatments = candidate["treatments"]
    if (
        value["rulebook_id"] != execution.rule_id
        or candidate["rulebook_id"] != execution.rule_id
        or value["preferred_variant"] != preferred
        or preferred not in THEME_VARIANTS
        or not isinstance(treatments, Mapping)
        or set(treatments) != set(THEME_VARIANTS)
    ):
        raise ValueError("V4 exploratory_candidate identity is invalid")
    treatment = treatments[preferred]
    if not isinstance(treatment, Mapping) or treatment.get("theme_variant") != preferred:
        raise ValueError("V4 preferred treatment is invalid")
    link_key = _hash({
        "ticker": ticker,
        "horizon": value["horizon"],
        "rulebook_id": execution.rule_id,
        "preferred_variant": preferred,
    })
    return {
        "schema_version": 4,
        "ticker": ticker,
        "horizon": value["horizon"],
        "rulebook_id": execution.rule_id,
        "preferred_variant": preferred,
        "audit_eligible": value["audit_eligible"],
        "exploratory_candidate": copy.deepcopy(dict(candidate)),
        "link_keys": [link_key],
    }


def validate_v3_position_snapshot(value: object) -> dict[str, object]:
    """Validate frozen schema-3 position history only; new writes must be V4."""

    if not isinstance(value, Mapping):
        raise ValueError("V3 signal_reference must be an object")
    required = {"schema_version", "ticker", "horizon", "theme_variant", "rule_id", "metrics", "signal_set"}
    if set(value) not in (required, required | {"link_keys"}) or value.get("schema_version") != 3:
        raise ValueError("V3 signal_reference schema_version must be 3")
    ticker = _normalize_ticker(value["ticker"])
    if ticker != value["ticker"] or value["horizon"] not in HORIZONS or value["theme_variant"] not in THEME_VARIANTS:
        raise ValueError("V3 signal_reference identity is invalid")
    signal = value["signal_set"]
    if not isinstance(signal, Mapping) or not isinstance(value["rule_id"], str):
        raise ValueError("V3 signal_reference is invalid")
    return {
        "schema_version": 3,
        "ticker": ticker,
        "horizon": value["horizon"],
        "theme_variant": value["theme_variant"],
        "rule_id": value["rule_id"],
        "metrics": list(value["metrics"]),
        "signal_set": copy.deepcopy(dict(signal)),
        "link_keys": [_hash({"frozen_v3": dict(value)})],
    }


def _legacy_signal_link_key(theme_variant: str, metric: str, certified_signal: Mapping[str, object]) -> str:
    if theme_variant not in THEME_VARIANTS or metric not in _LEGACY_CERTIFICATION_METRICS:
        raise ValueError("legacy signal reference identity is invalid")
    from .position_store import _validated_certified_signal

    signal, _ = _validated_certified_signal(certified_signal, metric, theme_variant)
    return _hash({"theme_variant": theme_variant, "metric": metric, "certified_signal": signal})


def _normalize_legacy_reference(value: Mapping[str, object]) -> dict[str, object]:
    theme_variant = value.get("theme_variant")
    metrics = value.get("metrics")
    certified = value.get("certified_signals")
    if theme_variant not in THEME_VARIANTS or not isinstance(metrics, (list, tuple)) or not isinstance(certified, Mapping):
        raise ValueError("legacy signal_reference is invalid")
    if list(metrics) != [metric for metric in _LEGACY_CERTIFICATION_METRICS if metric in metrics] or set(certified) != set(metrics):
        raise ValueError("legacy signal_reference metrics are invalid")
    snapshots, keys = {}, []
    for metric in metrics:
        from .position_store import _validated_certified_signal

        signal, _ = _validated_certified_signal(certified[metric], metric, str(theme_variant))
        snapshots[metric] = signal
        keys.append(_legacy_signal_link_key(str(theme_variant), metric, signal))
    return {"theme_variant": str(theme_variant), "metrics": list(metrics), "certified_signals": snapshots, "link_keys": keys}


def validate_position_snapshot(value: object) -> dict[str, object]:
    """Read schema-4 current references plus immutable legacy history."""

    if not isinstance(value, Mapping):
        raise ValueError("signal_reference must be an object")
    if value.get("schema_version") == 4:
        return validate_v4_position_snapshot(value)
    if value.get("schema_version") == 3:
        return validate_v3_position_snapshot(value)
    if value.get("schema_version") in (None, 2):
        return _normalize_legacy_reference(value)
    raise ValueError("signal_reference schema_version is unsupported")


def normalize_signal_reference(value: object) -> dict[str, object]:
    return validate_position_snapshot(value)


def position_signal_link_keys(position: Mapping[str, object]) -> set[str]:
    reference = position.get("signal_reference")
    return set() if reference is None else set(validate_position_snapshot(reference)["link_keys"])


def reference_metric_pairs(reference: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    normalized = validate_position_snapshot(reference)
    if normalized.get("schema_version") in (3, 4):
        return ()
    return tuple((str(normalized["theme_variant"]), metric) for metric in normalized["metrics"])


def signal_link_key(theme_variant: str, metric: str, certified_signal: Mapping[str, object]) -> str:
    """Legacy public helper retained solely for frozen historical records."""

    return _legacy_signal_link_key(theme_variant, metric, certified_signal)


__all__ = [
    "normalize_signal_reference", "position_signal_link_keys", "reference_metric_pairs",
    "signal_link_key", "validate_position_snapshot", "validate_v3_position_snapshot",
    "validate_v4_position_snapshot",
]
