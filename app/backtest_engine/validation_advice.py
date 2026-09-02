"""Schema-5 Top-3 replay, evidence-safe BUY hints, and explicit SELL advice."""

from __future__ import annotations

from collections.abc import Mapping

from .config import DEFAULT_SIGNAL_DIR, HORIZONS, THEME_VARIANTS, RulebookSpec, _normalize_ticker, rulebook_for
from .early_warning import check_current_situation, load_current_rulebook_document
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


def _historical_positions(ticker: str, positions_dir: str) -> list[dict[str, object]]:
    history = load_manual_position_history(ticker, positions_dir)
    return [
        dict(position) for position in history["history"]
        if not isinstance(position.get("signal_reference"), Mapping)
        or position["signal_reference"].get("schema_version") != 5
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


def _replay_rulebook(ticker: str, horizon: str, rulebook_id: str, engine, signal_dir: str, manual_history: Mapping[str, object]) -> dict[str, object]:
    try:
        replay = check_current_situation(ticker, horizon=horizon, rulebook_id=rulebook_id, engine=engine, output_dir=signal_dir)
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
    literal_entry = bool(current.get("literal_entry"))
    buy_block_reason = (
        "evidence_ineligible" if not evidence_eligible else "open_position" if open_position is not None else None
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
        "signal_reference": reference,
        "open_position": open_position,
        "buy_eligible": literal_entry and buy_block_reason is None,
        "buy_block_reason": buy_block_reason,
        "position_action": _position_action(
            current,
            open_position,
            literal_entry and buy_block_reason is None,
        ),
    }


def validate_saved_signals(
    ticker: str,
    engine,
    signal_dir: str = DEFAULT_SIGNAL_DIR,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Replay only Top-3 preferred rulebooks; old positions remain history only."""

    normalized = _normalize_ticker(ticker)
    manual_history = load_manual_position_history(normalized, positions_dir)
    results = []
    for horizon in HORIZONS:
        document = load_current_rulebook_document(normalized, horizon, signal_dir)
        if document is None or document["terminal_state"] != "success":
            continue
        for rulebook_id in document["top_rulebook_ids"]:
            results.append(_replay_rulebook(normalized, horizon, rulebook_id, engine, signal_dir, manual_history))
    return {"ticker": normalized, "results": results, "historical_positions": _historical_positions(normalized, positions_dir)}


__all__ = ["monitoring_match_level", "validate_saved_signals"]
