"""Pure Phase-B position-risk labels and assessment helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .config import ENTRY_GATE_NAMES, HORIZONS, THEME_VARIANTS, rulebook_for
from .data_quality import load_ticker_history
from .indicators import build_rulebook_frame
from .manual_position_store import (
    load_manual_position_history,
    update_manual_position_risk_suggestion,
)
from .position_monitor import monitor_position
from .validation_advice import monitoring_match_level


_HORIZON_LABELS = {"swing": "Swing", "midterm": "Mid-term"}


def _clamp_score(value: float) -> float:
    """Keep a risk component within the approved 0--100 range."""

    return min(100.0, max(0.0, float(value)))


def risk_label(score: float) -> str:
    """Map the rounded approved score to its exact inclusive risk band."""

    rounded = round(_clamp_score(score), 2)
    if rounded <= 40:
        return "low"
    if rounded <= 60:
        return "medium"
    if rounded <= 80:
        return "high"
    return "very"


def render_risk_suggestion(scores: Mapping[str, float]) -> str:
    """Render one or both native-horizon scores for the persisted BUY text."""

    lines = []
    for horizon in ("swing", "midterm"):
        if horizon not in scores:
            continue
        score = round(_clamp_score(float(scores[horizon])), 2)
        display_score = round(score, 1)
        lines.append(
            f"{_HORIZON_LABELS[horizon]}: {display_score:.1f}% - {risk_label(score)}"
        )
    if not lines:
        raise ValueError("risk scores must contain a registered horizon")
    return "\n".join(lines)


def elapsed_time_percent(horizon: str, completed_sessions_after_signal: int) -> float:
    """Return the approved daily-session elapsed component for one horizon."""

    if horizon == "swing":
        denominator = 22
    elif horizon == "midterm":
        denominator = 80
    else:
        raise ValueError("risk horizon must be swing or midterm")
    if isinstance(completed_sessions_after_signal, bool):
        raise ValueError("completed sessions must be an integer")
    sessions = int(completed_sessions_after_signal)
    if sessions < 0:
        raise ValueError("completed sessions must not be negative")
    return round(_clamp_score(100.0 * sessions / denominator), 2)


def score_signal_risk(
    *,
    entry_price: int,
    stop_loss: int,
    latest_close: int,
    latest_atr: float,
    holding_bars: int,
    max_hold_bars: int,
    strength_drop: float,
    elapsed_time: float,
) -> float:
    """Score approved frozen-stop downside and post-T+3 deterioration in raw units."""

    entry = float(entry_price)
    stop = float(stop_loss)
    close = float(latest_close)
    atr = float(latest_atr)
    maximum = int(max_hold_bars)
    holding = int(holding_bars)
    if entry <= 0 or stop <= 0 or close <= 0 or atr <= 0 or maximum <= 0 or holding < 0:
        raise ValueError("signal risk inputs must be positive")
    distance = entry - stop
    if distance <= 0:
        raise ValueError("entry price must exceed frozen stop loss")
    if close <= stop:
        return 100.0
    base = (
        0.55 * _clamp_score(100.0 * (entry - close) / distance)
        + 0.25 * _clamp_score(100.0 * atr / distance)
        + 0.20 * _clamp_score(100.0 * holding / maximum)
    )
    deterioration = 0.30 * max(
        _clamp_score(float(strength_drop)), _clamp_score(float(elapsed_time))
    )
    return round(_clamp_score(base + deterioration), 2)


def assess_no_signal_position(
    raw_history: pd.DataFrame, as_of_date: object
) -> dict[str, object]:
    """Score both fresh no-theme horizons from their four current V3 gates."""

    scores: dict[str, float] = {}
    for horizon in HORIZONS:
        frame = build_rulebook_frame(raw_history, rulebook_for(horizon), today=as_of_date)
        if frame.empty:
            return {"availability": "unavailable"}
        last = frame.iloc[-1]
        if any(gate not in last or pd.isna(last[gate]) for gate in ENTRY_GATE_NAMES):
            return {"availability": "unavailable"}
        passed = sum(bool(last[gate]) for gate in ENTRY_GATE_NAMES)
        scores[horizon] = round(100.0 - 100.0 * passed / len(ENTRY_GATE_NAMES), 2)
    return {"availability": "available", "scores": scores}


def _current_facts(
    raw_history: pd.DataFrame,
    horizon: str,
    selected_gates: tuple[str, ...],
    preferred_variant: str,
    as_of_date: date,
    vnindex_history: pd.DataFrame | None,
) -> dict[str, object] | None:
    rulebook = rulebook_for(horizon)
    frame = build_rulebook_frame(raw_history, rulebook, today=as_of_date)
    if frame.empty or any(gate not in frame for gate in selected_gates):
        return None
    last = frame.iloc[-1]
    if bool(last.get("rulebook_missing_required_input", True)):
        return None
    facts: dict[str, object] = {
        "gate_facts": {gate: bool(last[gate]) for gate in selected_gates},
        "latest_close": last.get("close"),
        "latest_atr": last.get("ATR_14"),
    }
    if preferred_variant == "background-theme":
        if vnindex_history is None:
            return None
        vn_frame = build_rulebook_frame(vnindex_history, rulebook, today=as_of_date)
        if vn_frame.empty:
            return None
        aligned = pd.merge_asof(
            frame[["date"]].sort_values("date"),
            vn_frame[["date", "close"]].assign(
                _sma=vn_frame["close"].rolling(rulebook.theme_sma_window).mean()
            ).sort_values("date"),
            on="date", direction="backward",
        )
        eligible = aligned.iloc[-1]
        if pd.isna(eligible["close"]) or pd.isna(eligible["_sma"]):
            return None
        facts["theme_eligible"] = bool(eligible["close"] > eligible["_sma"])
    return facts


def assess_signal_backed_position(
    position: dict[str, object],
    raw_history: pd.DataFrame,
    as_of_date: date,
    vnindex_history: pd.DataFrame | None,
) -> dict[str, object]:
    """Assess a frozen schema-4 position after its approved T+3 delay."""

    reference = position.get("signal_reference")
    context = position.get("entry_context")
    risk = position.get("risk_snapshot")
    if not isinstance(reference, Mapping) or reference.get("schema_version") != 4:
        return {"availability": "unavailable"}
    if not isinstance(context, Mapping) or not isinstance(risk, Mapping):
        return {"availability": "unavailable"}
    horizon = reference.get("horizon")
    preferred = reference.get("preferred_variant")
    candidate = reference.get("exploratory_candidate")
    if horizon not in HORIZONS or preferred not in THEME_VARIANTS or not isinstance(candidate, Mapping):
        return {"availability": "unavailable"}
    gates = candidate.get("selected_gates")
    if not isinstance(gates, list) or not gates or any(gate not in ENTRY_GATE_NAMES for gate in gates):
        return {"availability": "unavailable"}
    signal_date = pd.to_datetime(context.get("as_of_date"), errors="coerce")
    if pd.isna(signal_date):
        return {"availability": "unavailable"}
    source_dates = pd.to_datetime(raw_history.get("date"), errors="coerce")
    sessions = int(((source_dates > signal_date) & (source_dates <= pd.Timestamp(as_of_date))).sum())
    if sessions < 3:
        return {"availability": "t3_required"}
    facts = _current_facts(raw_history, str(horizon), tuple(gates), str(preferred), as_of_date, vnindex_history)
    if facts is None:
        return {"availability": "unavailable"}
    match = monitoring_match_level(str(horizon), tuple(gates), str(preferred), facts, rulebook_for(str(horizon)))
    try:
        saved_match = float(context["match_level"])
        current_match = float(match[0]) if match is not None else None
        monitor = monitor_position(position, raw_history, as_of_date)
        score = score_signal_risk(
            entry_price=int(position["actual_buy_price"]), stop_loss=int(risk["stop_loss"]),
            latest_close=float(facts["latest_close"]), latest_atr=float(facts["latest_atr"]),
            holding_bars=int(monitor["holding_bars"]), max_hold_bars=int(risk["max_hold_bars"]),
            strength_drop=max(0.0, saved_match - current_match),
            elapsed_time=elapsed_time_percent(str(horizon), sessions),
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"availability": "unavailable"}
    return {"availability": "available", "scores": {str(horizon): score}}


def list_validate_position_candidates(
    positions_dir: str = "backtest-positions",
) -> tuple[dict[str, object], ...]:
    """List only selectable OPEN generic records without probing legacy files."""

    root = Path(positions_dir)
    if not root.exists():
        return ()
    candidates: list[dict[str, object]] = []
    for ticker_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        ticker = ticker_dir.name.strip().upper()
        try:
            history = load_manual_position_history(ticker, str(root))
        except (OSError, ValueError):
            continue
        for position in history["history"]:
            if position.get("status") != "open":
                continue
            reference = position.get("signal_reference")
            if reference is not None and (
                not isinstance(reference, Mapping) or reference.get("schema_version") != 4
            ):
                continue
            if isinstance(reference, Mapping):
                horizon = reference.get("horizon")
                if horizon not in HORIZONS:
                    continue
                evaluation = _HORIZON_LABELS[str(horizon)]
            else:
                evaluation = "Swing + Mid-term"
            candidates.append(
                {"id": position["id"], "ticker": ticker, "evaluation": evaluation, "position": dict(position)}
            )
    return tuple(candidates)


def _latest_dates(tickers: tuple[str, ...], engine) -> dict[str, date]:
    query = text(
        """
        SELECT ticker, MAX(date) AS latest_date
        FROM trading_data
        WHERE ticker = ANY(%(tickers)s)
        GROUP BY ticker
        """
    )
    connection = engine.raw_connection()
    try:
        frame = pd.read_sql(query.text, connection, params={"tickers": list(tickers)})
    finally:
        connection.close()
    result: dict[str, date] = {}
    for row in frame.to_dict("records"):
        value = pd.to_datetime(row.get("latest_date"), errors="coerce")
        ticker = str(row.get("ticker", "")).strip().upper()
        if ticker and not pd.isna(value):
            result[ticker] = value.date()
    return result


def validate_open_positions(
    position_ids: tuple[str, ...],
    engine,
    positions_dir: str = "backtest-positions",
    persist_risk_suggestion_fn: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    """Assess one through five selected candidates, isolating every row failure."""

    if not 1 <= len(position_ids) <= 5 or len(set(position_ids)) != len(position_ids):
        raise ValueError("select one to five unique open positions")
    candidates = {item["id"]: item for item in list_validate_position_candidates(positions_dir)}
    selected = [candidates[item] for item in position_ids if item in candidates]
    if len(selected) != len(position_ids):
        raise ValueError("selected position is unavailable")
    required = {item["ticker"] for item in selected}
    if any(
        isinstance(item["position"].get("signal_reference"), Mapping)
        and item["position"]["signal_reference"].get("preferred_variant") == "background-theme"
        for item in selected
    ):
        required.add("VNINDEX")
    dates = _latest_dates(tuple(sorted(required)), engine)
    unique_dates = set(dates.values())
    if set(dates) != required or len(unique_dates) != 1:
        return {"as_of_date": None, "results": [
            {"ticker": item["ticker"], "position_id": item["id"], "evaluation": item["evaluation"], "risk_suggestion": "N/A", "result": "Failed — assess failed."}
            for item in selected
        ]}
    as_of = next(iter(unique_dates))
    raw_cache: dict[str, pd.DataFrame] = {}
    writer = persist_risk_suggestion_fn or update_manual_position_risk_suggestion
    results = []
    for item in selected:
        position = item["position"]
        ticker = item["ticker"]
        try:
            if ticker not in raw_cache:
                raw_cache[ticker] = load_ticker_history(ticker, pd.Timestamp(as_of) - pd.DateOffset(years=15), as_of, engine)
            reference = position.get("signal_reference")
            vnindex = None
            if isinstance(reference, Mapping) and reference.get("preferred_variant") == "background-theme":
                if "VNINDEX" not in raw_cache:
                    raw_cache["VNINDEX"] = load_ticker_history("VNINDEX", pd.Timestamp(as_of) - pd.DateOffset(years=15), as_of, engine)
                vnindex = raw_cache["VNINDEX"]
            assessment = assess_signal_backed_position(position, raw_cache[ticker], as_of, vnindex) if isinstance(reference, Mapping) else assess_no_signal_position(raw_cache[ticker], as_of)
            if assessment["availability"] == "t3_required":
                result = "T+3 required"; text_value = "N/A"
            elif assessment["availability"] != "available":
                text_value = "Unavailable"; writer(ticker, item["id"], text_value, positions_dir); result = "Unavailable — risk score missing/invalid."
            else:
                text_value = render_risk_suggestion(assessment["scores"]); writer(ticker, item["id"], text_value, positions_dir); result = "Updated"
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            text_value = "N/A"; result = "Failed — assess failed."
        results.append({"ticker": ticker, "position_id": item["id"], "evaluation": item["evaluation"], "risk_suggestion": text_value, "result": result})
    return {"as_of_date": as_of.isoformat(), "results": results}


__all__ = [
    "elapsed_time_percent",
    "assess_no_signal_position",
    "assess_signal_backed_position",
    "list_validate_position_candidates",
    "render_risk_suggestion",
    "risk_label",
    "score_signal_risk",
    "validate_open_positions",
]
