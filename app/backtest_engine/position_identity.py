"""Version-routed frozen exploratory identities for manual positions."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from datetime import date
from numbers import Real

from .config import ENTRY_GATE_NAMES, HORIZONS, THEME_VARIANTS, _normalize_ticker, rulebook_for
from .models import RulebookExecution


_LEGACY_CERTIFICATION_METRICS = ("win_rate", "profit", "sharpe")
_GATE_SUFFIXES = {
    "rulebook_adx_gate": "adx",
    "rulebook_joint_trend_pass": "joint_trend",
    "rulebook_rsi_upcross": "rsi_upcross",
    "rulebook_volume_gate": "volume",
}


def _hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _selected_gates(value: object, version: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{version} exploratory_candidate selected_gates are invalid")
    gates = tuple(value)
    if (
        not gates
        or any(gate not in ENTRY_GATE_NAMES for gate in gates)
        or gates != tuple(sorted(set(gates)))
    ):
        raise ValueError(f"{version} exploratory_candidate selected_gates are invalid")
    return gates


def _v4_rulebook_id(horizon: str, gates: tuple[str, ...]) -> str:
    return f"{horizon}_rulebook_v4__" + "__".join(
        _GATE_SUFFIXES[gate] for gate in gates
    )


def _validate_candidate(
    candidate: object,
    *,
    version: str,
    expected_rulebook_id: str,
    preferred_variant: object,
    require_role: bool,
) -> dict[str, object]:
    if not isinstance(candidate, Mapping):
        raise ValueError(f"{version} signal_reference requires exploratory_candidate")
    expected = {
        "rulebook_id",
        "selected_gates",
        "preferred_variant",
        "treatments",
    }
    if require_role:
        expected.add("candidate_role")
    if set(candidate) != expected:
        raise ValueError(f"{version} exploratory_candidate shape is invalid")
    _selected_gates(candidate["selected_gates"], version)
    if require_role and candidate.get("candidate_role") != "baseline_control":
        raise ValueError("V5 position references require a baseline_control candidate")
    preferred = candidate.get("preferred_variant")
    treatments = candidate.get("treatments")
    if (
        candidate.get("rulebook_id") != expected_rulebook_id
        or preferred_variant != preferred
        or preferred not in THEME_VARIANTS
        or not isinstance(treatments, Mapping)
        or set(treatments) != set(THEME_VARIANTS)
    ):
        raise ValueError(f"{version} exploratory_candidate identity is invalid")
    treatment = treatments[preferred]
    if not isinstance(treatment, Mapping) or treatment.get("theme_variant") != preferred:
        raise ValueError(f"{version} preferred treatment is invalid")
    return copy.deepcopy(dict(candidate))


def _validate_evidence_snapshot(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("V5 signal_reference requires evidence_eligibility")
    required = {
        "status", "eligible", "reasons", "common_as_of", "first_available_bar",
        "last_available_bar", "ticker_fingerprint", "vnindex_fingerprint",
        "observed_sessions", "expected_sessions", "coverage_ratio", "max_gap_sessions",
    }
    if set(value) != required or value.get("status") not in ("eligible", "ineligible"):
        raise ValueError("V5 evidence_eligibility shape is invalid")
    eligible = value.get("eligible")
    reasons = value.get("reasons")
    if (
        not isinstance(eligible, bool)
        or not isinstance(reasons, list)
        or any(not isinstance(reason, str) or not reason for reason in reasons)
        or (eligible and (value["status"] != "eligible" or reasons))
        or (not eligible and (value["status"] != "ineligible" or not reasons))
    ):
        raise ValueError("V5 evidence_eligibility status is invalid")
    for field in ("common_as_of", "first_available_bar", "last_available_bar"):
        try:
            date.fromisoformat(str(value[field]))
        except ValueError as error:
            raise ValueError(f"V5 evidence_eligibility {field} is invalid") from error
    for field in ("ticker_fingerprint", "vnindex_fingerprint"):
        fingerprint = value[field]
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
        ):
            raise ValueError(f"V5 evidence_eligibility {field} is invalid")
    observed = value["observed_sessions"]
    expected = value["expected_sessions"]
    maximum_gap = value["max_gap_sessions"]
    coverage = value["coverage_ratio"]
    if (
        isinstance(observed, bool)
        or not isinstance(observed, int)
        or isinstance(expected, bool)
        or not isinstance(expected, int)
        or isinstance(maximum_gap, bool)
        or not isinstance(maximum_gap, int)
        or not 0 <= observed <= expected
        or expected < 1
        or maximum_gap < 0
        or isinstance(coverage, bool)
        or not isinstance(coverage, Real)
        or abs(float(coverage) - observed / expected) > 1e-12
    ):
        raise ValueError("V5 evidence_eligibility counts are invalid")
    return copy.deepcopy(dict(value))


def validate_v5_position_snapshot(value: object) -> dict[str, object]:
    """Validate one current frozen schema-5 baseline-control reference."""

    if not isinstance(value, Mapping):
        raise ValueError("V5 signal_reference must be an object")
    required = {
        "schema_version", "contract_version", "ticker", "horizon", "rulebook_id",
        "preferred_variant", "evidence_eligibility", "exploratory_candidate",
    }
    if set(value) not in (required, required | {"link_keys"}) or value.get("schema_version") != 5:
        raise ValueError("V5 signal_reference schema_version must be 5")
    if value.get("contract_version") != "backtest_schema5_v1":
        raise ValueError("V5 signal_reference contract_version is invalid")
    ticker = _normalize_ticker(value["ticker"])
    horizon = value.get("horizon")
    if ticker != value["ticker"] or horizon not in HORIZONS:
        raise ValueError("V5 signal_reference identity is invalid")
    candidate = value["exploratory_candidate"]
    if not isinstance(candidate, Mapping):
        raise ValueError("V5 signal_reference requires exploratory_candidate")
    try:
        execution = RulebookExecution(
            rulebook_for(str(horizon)),
            _selected_gates(candidate.get("selected_gates"), "V5"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("V5 exploratory_candidate selected_gates are invalid") from error
    if value.get("rulebook_id") != execution.rule_id:
        raise ValueError("V5 exploratory_candidate identity is invalid")
    normalized_candidate = _validate_candidate(
        candidate,
        version="V5",
        expected_rulebook_id=execution.rule_id,
        preferred_variant=value.get("preferred_variant"),
        require_role=True,
    )
    evidence = _validate_evidence_snapshot(value["evidence_eligibility"])
    link_key = _hash({
        "schema_version": 5,
        "ticker": ticker,
        "horizon": horizon,
        "rulebook_id": execution.rule_id,
        "preferred_variant": value["preferred_variant"],
    })
    return {
        "schema_version": 5,
        "contract_version": "backtest_schema5_v1",
        "ticker": ticker,
        "horizon": horizon,
        "rulebook_id": execution.rule_id,
        "preferred_variant": value["preferred_variant"],
        "evidence_eligibility": evidence,
        "exploratory_candidate": normalized_candidate,
        "link_keys": [link_key],
    }


def validate_v4_position_snapshot(value: object) -> dict[str, object]:
    """Validate one frozen schema-4 reference without current-rulebook replay."""

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
    gates = _selected_gates(candidate.get("selected_gates"), "V4")
    rulebook_id = _v4_rulebook_id(str(value["horizon"]), gates)
    if value["rulebook_id"] != rulebook_id:
        raise ValueError("V4 exploratory_candidate identity is invalid")
    normalized_candidate = _validate_candidate(
        candidate,
        version="V4",
        expected_rulebook_id=rulebook_id,
        preferred_variant=value["preferred_variant"],
        require_role=False,
    )
    link_key = _hash({
        "ticker": ticker,
        "horizon": value["horizon"],
        "rulebook_id": rulebook_id,
        "preferred_variant": value["preferred_variant"],
    })
    return {
        "schema_version": 4,
        "ticker": ticker,
        "horizon": value["horizon"],
        "rulebook_id": rulebook_id,
        "preferred_variant": value["preferred_variant"],
        "audit_eligible": value["audit_eligible"],
        "exploratory_candidate": normalized_candidate,
        "link_keys": [link_key],
    }


def validate_v3_position_snapshot(value: object) -> dict[str, object]:
    """Validate frozen schema-3 position history only; new writes must be V5."""

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
    """Read schema-5 current references plus immutable legacy history."""

    if not isinstance(value, Mapping):
        raise ValueError("signal_reference must be an object")
    if value.get("schema_version") == 5:
        return validate_v5_position_snapshot(value)
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
    if normalized.get("schema_version") in (3, 4, 5):
        return ()
    return tuple((str(normalized["theme_variant"]), metric) for metric in normalized["metrics"])


def signal_link_key(theme_variant: str, metric: str, certified_signal: Mapping[str, object]) -> str:
    """Legacy public helper retained solely for frozen historical records."""

    return _legacy_signal_link_key(theme_variant, metric, certified_signal)


__all__ = [
    "normalize_signal_reference", "position_signal_link_keys", "reference_metric_pairs",
    "signal_link_key", "validate_position_snapshot", "validate_v3_position_snapshot",
    "validate_v4_position_snapshot", "validate_v5_position_snapshot",
]
