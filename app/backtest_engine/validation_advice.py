"""Schema-5 Top-3 replay, evidence-safe BUY hints, and explicit SELL advice."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from pathlib import Path

from .config import DEFAULT_SIGNAL_DIR, HORIZONS, THEME_VARIANTS, RulebookSpec, _normalize_ticker, rulebook_for
from .early_warning import check_current_situation, load_current_rulebook_document
from .flexible_adapter import (
    flexible_signal_artifact_root,
    load_flexible_signal_artifact,
    replay_flexible_signal_artifact,
)
from .listing_status import ListingStatus, load_listing_statuses
from .manual_position_store import load_manual_position_history


def _classification(level: float) -> str:
    if level <= 0:
        return "no_match"
    if level < 50:
        return "weak"
    if level < 100:
        return "nearly_match"
    return "closely_match"


def monitoring_match_level(
    horizon: str,
    selected_gates: tuple[str, ...],
    preferred_variant: str,
    current: Mapping[str, object],
    rulebook: RulebookSpec,
) -> tuple[float, str] | None:
    """Return equal-weight selected-gate alignment; it never controls entry or rank."""

    if horizon not in HORIZONS or preferred_variant not in THEME_VARIANTS:
        raise ValueError("monitoring identity is invalid")
    if rulebook != rulebook_for(horizon) or not selected_gates:
        raise ValueError("monitoring requires a registered rulebook and selected gates")
    gate_facts = current.get("gate_facts") if isinstance(current, Mapping) else None
    if not isinstance(gate_facts, Mapping) or any(gate not in gate_facts for gate in selected_gates):
        return None
    factors = [bool(gate_facts[gate]) for gate in selected_gates]
    if preferred_variant == "background-theme":
        if "theme_eligible" not in current:
            return None
        factors.append(bool(current["theme_eligible"]))
    level = round(100.0 * sum(factors) / len(factors), 2)
    return level, _classification(level)


def _unavailable(reason: object) -> dict[str, object]:
    return {"availability": "unavailable", "reason": str(reason)}


def _preferred_win_rates(
    candidate: Mapping[str, object], preferred_variant: str
) -> dict[str, float | None]:
    """Project immutable preferred-treatment win rates without ranking again."""

    treatment = candidate.get("treatments", {}).get(preferred_variant, {})
    values: dict[str, float | None] = {}
    for partition in ("training", "test"):
        try:
            value = float(treatment.get(partition, {}).get("win_rate"))
        except (AttributeError, TypeError, ValueError):
            value = None
        values[partition] = value if value is not None and isfinite(value) else None
    return values


def _historical_positions(ticker: str, positions_dir: str) -> list[dict[str, object]]:
    history = load_manual_position_history(ticker, positions_dir)
    return [
        dict(position) for position in history["history"]
        if not isinstance(position.get("signal_reference"), Mapping)
        or position["signal_reference"].get("schema_version") not in {5, 6}
    ]


def _open_v5_position(reference: Mapping[str, object], manual_history: Mapping[str, object]) -> dict[str, object] | None:
    identity = (reference["horizon"], reference["rulebook_id"], reference["preferred_variant"])
    for position in manual_history["history"]:
        candidate = position.get("signal_reference") if isinstance(position, Mapping) else None
        if not isinstance(candidate, Mapping) or candidate.get("schema_version") != 5:
            continue
        if position.get("status") == "open" and (
            candidate.get("horizon"), candidate.get("rulebook_id"), candidate.get("preferred_variant")
        ) == identity:
            return dict(position)
    return None


def _open_flexible_position(
    reference: Mapping[str, object], manual_history: Mapping[str, object],
) -> dict[str, object] | None:
    identity = (
        reference["horizon"], reference["rulebook_id"], reference["evaluation_id"],
    )
    for position in manual_history["history"]:
        candidate = position.get("signal_reference") if isinstance(position, Mapping) else None
        if not isinstance(candidate, Mapping):
            continue
        if position.get("status") == "open" and (
            candidate.get("schema_version") == 6
            and candidate.get("origin") == "flexible"
            and (
                candidate.get("horizon"), candidate.get("rulebook_id"),
                candidate.get("evaluation_id"),
            ) == identity
        ):
            return dict(position)
    return None


def _position_action(
    current: Mapping[str, object],
    open_position: Mapping[str, object] | None,
    buy_eligible: bool,
) -> str:
    """Classify one current rulebook replay without changing its trading state."""

    if open_position is None:
        return "can BUY" if buy_eligible else "expired BUY"
    if bool(current.get("technical_exit")) or bool(current.get("deteriorated")):
        return "can SELL"
    try:
        close = float(current["latest_close"])
        risk_snapshot = open_position["risk_snapshot"]
        if not isinstance(risk_snapshot, Mapping):
            raise ValueError("risk snapshot is invalid")
        stop_loss = float(risk_snapshot["stop_loss"])
        take_profit = float(risk_snapshot["take_profit"])
    except (KeyError, TypeError, ValueError):
        return "HOLD"
    return "can SELL" if close <= stop_loss or close >= take_profit else "HOLD"


def _state_allows_buy(current: Mapping[str, object]) -> bool:
    """Allow only a fresh or causally supported ongoing signal to open a BUY."""

    state = current.get("signal_state")
    if isinstance(state, Mapping):
        return state.get("state") in ("fresh", "ongoing")
    # Compatibility for synthetic/legacy callers; live schema-5 replays always
    # provide a progressive state from early_warning._current_rulebook_facts.
    return bool(current.get("literal_entry"))


def _replay_rulebook(
    ticker: str,
    horizon: str,
    rulebook_id: str,
    engine,
    signal_dir: str,
    manual_history: Mapping[str, object],
    listing_status: ListingStatus,
) -> dict[str, object]:
    try:
        replay = check_current_situation(
            ticker,
            horizon=horizon,
            rulebook_id=rulebook_id,
            engine=engine,
            output_dir=signal_dir,
            listing_status=listing_status,
        )
    except (OSError, ValueError) as error:
        return _unavailable(error)
    candidate = replay.get("candidate")
    current = replay.get("current")
    if not isinstance(candidate, Mapping) or not isinstance(current, Mapping):
        return _unavailable(replay.get("reason", "No current schema-5 exploratory rulebook exists."))
    preferred = candidate["preferred_variant"]
    monitoring = monitoring_match_level(horizon, tuple(candidate["selected_gates"]), preferred, current, rulebook_for(horizon))
    evidence = replay.get("evidence_eligibility")
    if not isinstance(evidence, Mapping):
        return _unavailable("schema-5 replay evidence is unavailable")
    reference = {
        "schema_version": 5,
        "contract_version": "backtest_schema5_v1",
        "ticker": ticker,
        "horizon": horizon,
        "rulebook_id": candidate["rulebook_id"],
        "preferred_variant": preferred,
        "evidence_eligibility": dict(evidence),
        "exploratory_candidate": dict(candidate),
    }
    open_position = _open_v5_position(reference, manual_history)
    evidence_eligible = bool(evidence.get("eligible"))
    state_allows_buy = _state_allows_buy(current)
    buy_block_reason = (
        "evidence_ineligible" if not evidence_eligible else "open_position" if open_position is not None
        else "signal_weakening" if not state_allows_buy else None
    )
    return {
        "availability": "available",
        "horizon": horizon,
        "rulebook_id": candidate["rulebook_id"],
        "preferred_variant": preferred,
        "candidate": dict(candidate),
        "current": dict(current),
        "audit_eligibility": dict(replay["audit_eligibility"]),
        "evidence_eligibility": dict(evidence),
        "evaluation_label": replay.get("evaluation_label", "Exploratory — gross"),
        "partition_labels": dict(replay.get("partition_labels", {})),
        "monitoring": None if monitoring is None else {"match_level": monitoring[0], "match_classification": monitoring[1]},
        "signal_date": current.get("signal_date"),
        "signal_state": dict(current.get("signal_state", {})),
        "win_rate": _preferred_win_rates(candidate, preferred),
        "signal_reference": reference,
        "open_position": open_position,
        "buy_eligible": state_allows_buy and buy_block_reason is None,
        "buy_block_reason": buy_block_reason,
        "position_action": _position_action(
            current,
            open_position,
            state_allows_buy and buy_block_reason is None,
        ),
    }


def _flexible_artifacts_for_ticker(
    ticker: str, signal_dir: str,
) -> tuple[dict[str, object], ...]:
    """Read only current success artifacts from the isolated Flexible root."""

    root = flexible_signal_artifact_root(signal_dir) / ticker
    if not root.is_dir():
        return ()
    artifacts: list[dict[str, object]] = []
    for path in sorted(root.glob(f"{ticker}_flexible_signals_*__*.json")):
        try:
            artifact = load_flexible_signal_artifact(path)
        except (OSError, TypeError, ValueError):
            continue
        if artifact["ticker"] == ticker and artifact["terminal_state"] == "success":
            artifacts.append(artifact)
    return tuple(artifacts)


def _flexible_treatments(artifact: Mapping[str, object]) -> dict[str, object]:
    evaluation = artifact.get("evaluation")
    metrics = evaluation.get("metrics") if isinstance(evaluation, Mapping) else None
    if not isinstance(metrics, Mapping):
        raise ValueError("Flexible artifact metrics are unavailable")
    treatment: dict[str, dict[str, float | int | None]] = {}
    for partition in ("training", "test"):
        source = metrics.get(partition)
        if not isinstance(source, Mapping):
            raise ValueError("Flexible artifact metrics are unavailable")
        treatment[partition] = {
            "n": source.get("n"),
            "win_rate": source.get("win_rate"),
            "profit_pct": source.get("total_return_pct"),
            "sharpe": source.get("sharpe"),
        }
    return {"flexible": treatment}


def _flexible_classification(value: str) -> str:
    return {
        "Closely Match": "closely_match",
        "Nearly Match": "nearly_match",
        "No Match": "no_match",
    }[value]


def _replay_flexible_rulebook(
    artifact: Mapping[str, object],
    engine,
    manual_history: Mapping[str, object],
    listing_status: ListingStatus,
) -> dict[str, object]:
    """Project one v2 replay into the existing read-only Validate UI contract."""

    try:
        replay = replay_flexible_signal_artifact(artifact, engine=engine)
        current = replay["inspection"]
        source_artifact = replay["artifact"]
    except (OSError, TypeError, ValueError) as error:
        return _unavailable(error)
    if not isinstance(source_artifact, Mapping):
        return _unavailable("Flexible artifact is unavailable")
    try:
        horizon = str(source_artifact["horizon"])
        rulebook_id = str(source_artifact["rulebook_id"])
        evaluation_reference = source_artifact["evaluation_reference"]
        if not isinstance(evaluation_reference, Mapping):
            raise ValueError("Flexible evaluation reference is unavailable")
        evaluation_id = str(evaluation_reference["evaluation_id"])
        treatments = _flexible_treatments(source_artifact)
        trend_state = str(current.signal_state)
        from flexible_rulebook.v2.validation import classify_monitoring, determine_buy_action

        classification = _flexible_classification(
            classify_monitoring(current.support_percentage, trend_state)
        )
        reference = {
            "schema_version": 6,
            "contract_version": "flexible_rulebook_signal_v1",
            "origin": "flexible",
            "ticker": str(source_artifact["ticker"]),
            "horizon": horizon,
            "rulebook_id": rulebook_id,
            "semantic_digest": str(source_artifact["semantic_digest"]),
            "evaluation_id": evaluation_id,
            "evaluation_label": str(source_artifact["evaluation_label"]),
            "metrics": treatments["flexible"],
        }
        open_position = _open_flexible_position(reference, manual_history)
        position_action = determine_buy_action(
            has_prior_event=bool(current.has_prior_event),
            trend_state=trend_state,
            live_entry_support=bool(current.live_entry_support),
            all_gates_support=bool(current.all_gates_support),
            evidence_available=True,
            is_listed=listing_status.is_listed,
            has_open_position=open_position is not None,
        )
        current_payload = {
            "as_of_date": current.as_of_date.isoformat(),
            "latest_close": current.latest_close,
            "latest_atr": current.latest_atr,
            "literal_entry": current.age_native_bars == 0,
            "technical_exit": bool(current.technical_exit),
            "deteriorated": trend_state in {"Weakening", "Invalidated"},
            "support_percentage": current.support_percentage,
            "live_entry_support": bool(current.live_entry_support),
            "all_gates_support": bool(current.all_gates_support),
        }
        buy_eligible = position_action == "can BUY"
        if open_position is not None:
            position_action = _position_action(current_payload, open_position, False)
        buy_block_reason = (
            None if buy_eligible else "open_position" if open_position is not None
            else "signal_weakening" if trend_state in {"Weakening", "Invalidated"}
            else "entry_conditions_not_current"
        )
        return {
            "availability": "available",
            "origin": "flexible",
            "horizon": horizon,
            "rulebook_id": rulebook_id,
            "preferred_variant": "flexible",
            "candidate": {
                "rulebook_id": rulebook_id,
                "selected_gates": [],
                "preferred_variant": "flexible",
                "treatments": treatments,
            },
            "current": current_payload,
            "audit_eligibility": {"eligible": True, "status": "available"},
            "evidence_eligibility": {"eligible": True, "status": "available", "reasons": []},
            "evaluation_label": source_artifact["evaluation_label"],
            "partition_labels": {"training": "in-sample", "test": "historical test — previously observed"},
            "monitoring": {
                "match_level": round(float(current.support_percentage), 2),
                "match_classification": classification,
            },
            "signal_date": None if current.signal_date is None else current.signal_date.isoformat(),
            "signal_state": {
                "state": trend_state.lower().replace("-", ""),
                "age_native_bars": current.age_native_bars,
            },
            "win_rate": _preferred_win_rates({"treatments": treatments}, "flexible"),
            "signal_reference": reference,
            "open_position": open_position,
            "buy_eligible": buy_eligible,
            "buy_block_reason": buy_block_reason,
            "position_action": position_action,
        }
    except (KeyError, TypeError, ValueError) as error:
        return _unavailable(error)
def validate_saved_signals(
    ticker: str,
    engine,
    signal_dir: str = DEFAULT_SIGNAL_DIR,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Replay only Top-3 preferred rulebooks; old positions remain history only."""

    normalized = _normalize_ticker(ticker)
    manual_history = load_manual_position_history(normalized, positions_dir)
    try:
        listing = load_listing_statuses((normalized,), engine)[normalized]
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        return {
            "ticker": normalized,
            "results": [_unavailable(f"Listing status unavailable: {error}")],
            "historical_positions": _historical_positions(normalized, positions_dir),
        }
    if not listing.is_listed:
        return {
            "ticker": normalized,
            "results": [_unavailable(listing.reason)],
            "historical_positions": _historical_positions(normalized, positions_dir),
        }
    results = []
    for horizon in HORIZONS:
        document = load_current_rulebook_document(normalized, horizon, signal_dir)
        if document is None or document["terminal_state"] != "success":
            continue
        for rulebook_id in document["top_rulebook_ids"]:
            results.append(
                _replay_rulebook(
                    normalized,
                    horizon,
                    rulebook_id,
                    engine,
                    signal_dir,
                    manual_history,
                    listing,
                )
            )
    for artifact in _flexible_artifacts_for_ticker(normalized, signal_dir):
        results.append(
            _replay_flexible_rulebook(artifact, engine, manual_history, listing)
        )
    return {"ticker": normalized, "results": results, "historical_positions": _historical_positions(normalized, positions_dir)}


__all__ = ["monitoring_match_level", "validate_saved_signals"]
