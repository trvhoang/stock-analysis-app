"""Atomic generic histories for manual Backtest positions."""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import pytz

from .config import _normalize_ticker, rulebook_for
from .position_identity import (
    normalize_signal_reference,
    position_signal_link_keys,
    reference_metric_pairs,
)
from .position_store import (
    _iso_date,
    _iso_timestamp,
    _json_snapshot,
    _optional_quantity,
    _positive_raw_int,
    _risk_for_buy_price,
    _validated_entry_context,
    _validated_risk_snapshot,
    _write_history,
    load_position_history,
)


_SCHEMA_VERSION = 1
_MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")


def _reference_signal_and_horizon(
    reference: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    """Select one frozen preferred exploratory treatment or legacy representative."""

    if reference.get("schema_version") in (4, 5):
        schema_version = reference.get("schema_version")
        candidate = reference.get("exploratory_candidate")
        horizon = reference.get("horizon")
        if not isinstance(candidate, Mapping) or not isinstance(horizon, str):
            raise ValueError("exploratory signal_reference is incomplete")
        treatment = candidate["treatments"][reference["preferred_variant"]]
        representative = {
            "rulebook_id": reference["rulebook_id"],
            "selected_gates": copy.deepcopy(candidate["selected_gates"]),
            "preferred_variant": reference["preferred_variant"],
            "treatment": copy.deepcopy(treatment),
            "evaluation_label": "Exploratory — gross",
        }
        # V4 records keep their byte-for-byte historical representative shape.
        if schema_version == 5:
            representative["horizon"] = horizon
        return representative, horizon

    if reference.get("schema_version") == 3:
        signal = reference.get("signal_set")
        horizon = reference.get("horizon")
        if not isinstance(signal, dict) or not isinstance(horizon, str):
            raise ValueError("V3 signal_reference is incomplete")
        return copy.deepcopy(signal), horizon
    metrics = reference["metrics"]
    signals = reference["certified_signals"]
    return copy.deepcopy(signals[metrics[0]]), str(signals[metrics[0]]["combo"]["horizon"])


def build_v5_risk_snapshot(
    horizon: str, atr: object, actual_buy_price: object
) -> dict[str, object]:
    """Build frozen V5 exit levels from one rulebook and raw entry facts."""

    rulebook = rulebook_for(horizon)
    raw_atr = _positive_raw_int(atr, "risk_snapshot atr")
    raw_buy_price = _positive_raw_int(actual_buy_price, "actual_buy_price")
    return _risk_for_buy_price(
        {
            "atr": raw_atr,
            "stop_loss": 1,
            "take_profit": 1,
            "max_hold_bars": rulebook.max_hold_bars,
        },
        raw_buy_price,
        horizon,
    )


def _manual_path(ticker: str, positions_dir: str) -> tuple[str, Path]:
    normalized_ticker = _normalize_ticker(ticker)
    target = Path(positions_dir) / normalized_ticker / f"{normalized_ticker}_manual_positions.json"
    return normalized_ticker, target


def _empty_history(ticker: str) -> dict[str, object]:
    return {"schema_version": _SCHEMA_VERSION, "ticker": ticker, "history": []}


def _validated_manual_position(value: object, ticker: str) -> dict[str, object]:
    position = _json_snapshot(value, "position")
    if not isinstance(position.get("id"), str) or not position["id"].strip():
        raise ValueError("position id must be a non-empty string")
    if position.get("ticker") != ticker:
        raise ValueError("position ticker does not match its history file")
    if position.get("status") not in ("open", "closed"):
        raise ValueError("position status must be open or closed")
    if not isinstance(position.get("origin"), str) or not position["origin"].strip():
        raise ValueError("position origin must be a non-empty string")

    position["actual_buy_price"] = _positive_raw_int(
        position.get("actual_buy_price"), "actual_buy_price"
    )
    position["quantity"] = _optional_quantity(position.get("quantity"))
    position["buy_date"] = _iso_date(position.get("buy_date"), "buy_date")
    position["opened_at"] = _iso_timestamp(position.get("opened_at"), "opened_at")
    risk_suggestion = position.get("risk_suggestion_text")
    if risk_suggestion is not None:
        if not isinstance(risk_suggestion, str) or not risk_suggestion.strip():
            raise ValueError("risk_suggestion_text must be a non-empty string")
        position["risk_suggestion_text"] = risk_suggestion.strip()

    reference = position.get("signal_reference")
    if reference is None:
        if any(position.get(field) is not None for field in ("certified_signal", "entry_context", "risk_snapshot")):
            raise ValueError("P&L-only position cannot contain saved signal data")
        position["certified_signal"] = None
        position["entry_context"] = None
        position["risk_snapshot"] = None
    else:
        normalized_reference = normalize_signal_reference(reference)
        representative, horizon = _reference_signal_and_horizon(normalized_reference)
        if position.get("certified_signal") != representative:
            raise ValueError("position certified_signal must match its saved signal reference")
        position["signal_reference"] = normalized_reference
        position["certified_signal"] = copy.deepcopy(representative)
        position["entry_context"] = _validated_entry_context(position.get("entry_context"))
        position["risk_snapshot"] = _validated_risk_snapshot(
            position.get("risk_snapshot"), horizon
        )

    sell_fields = ("actual_sell_price", "sell_date", "closed_at", "sell_reason")
    if position["status"] == "open":
        if any(position.get(field) is not None for field in sell_fields):
            raise ValueError("open position cannot contain manual SELL data")
        return position

    position["actual_sell_price"] = _positive_raw_int(
        position.get("actual_sell_price"), "actual_sell_price"
    )
    position["sell_date"] = _iso_date(position.get("sell_date"), "sell_date")
    if position["sell_date"] < position["buy_date"]:
        raise ValueError("sell date cannot be before BUY date")
    position["closed_at"] = _iso_timestamp(position.get("closed_at"), "closed_at")
    if not isinstance(position.get("sell_reason"), str) or not position["sell_reason"].strip():
        raise ValueError("sell_reason must be a non-empty string")
    position["sell_reason"] = position["sell_reason"].strip()
    return position


def _validated_history(value: object, ticker: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("manual position history must be a JSON object")
    if value.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported manual position history schema version")
    if value.get("ticker") != ticker:
        raise ValueError("manual position history ticker does not match request")
    history = value.get("history")
    if not isinstance(history, list):
        raise ValueError("manual position history must contain a history list")
    validated = [_validated_manual_position(item, ticker) for item in history]
    if len({item["id"] for item in validated}) != len(validated):
        raise ValueError("manual position history contains duplicate ids")
    return {"schema_version": _SCHEMA_VERSION, "ticker": ticker, "history": validated}


def load_manual_position_history(
    ticker: str,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Load one ticker's generic manual history without changing it."""

    normalized_ticker, target = _manual_path(ticker, positions_dir)
    if not target.exists():
        return _empty_history(normalized_ticker)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("manual position history is not valid JSON") from error
    return _validated_history(payload, normalized_ticker)


def _assert_no_open_signal_overlap(
    reference: Mapping[str, object],
    ticker: str,
    history: Mapping[str, object],
    positions_dir: str,
) -> None:
    requested = set(normalize_signal_reference(reference)["link_keys"])
    for position in history["history"]:
        if position["status"] == "open" and requested.intersection(position_signal_link_keys(position)):
            raise ValueError("saved signal set already has an OPEN position")
    for theme_variant, metric in reference_metric_pairs(reference):
        legacy = load_position_history(ticker, theme_variant, metric, positions_dir)
        if any(position["status"] == "open" for position in legacy["history"]):
            raise ValueError("saved signal set already has an OPEN position")


def _new_position(
    ticker: str,
    actual_buy_price: object,
    buy_date: object,
    actual_sell_price: object,
    sell_date: object,
    quantity: object,
    signal_reference: object,
    entry_context: object,
    risk_snapshot: object,
    origin: object,
) -> dict[str, object]:
    if not isinstance(origin, str) or not origin.strip():
        raise ValueError("origin must be a non-empty string")
    has_sell_price = actual_sell_price is not None
    has_sell_date = sell_date is not None
    if has_sell_price != has_sell_date:
        raise ValueError("SELL price and SELL date must be supplied together")
    normalized_reference = None
    certified_signal = None
    normalized_context = None
    normalized_risk = None
    if signal_reference is None:
        if entry_context is not None or risk_snapshot is not None:
            raise ValueError("P&L-only position cannot include saved signal context")
    else:
        if not isinstance(signal_reference, Mapping) or signal_reference.get("schema_version") != 5:
            raise ValueError("new signal-backed positions require a schema_version 5 reference")
        normalized_reference = normalize_signal_reference(signal_reference)
        if not normalized_reference["evidence_eligibility"]["eligible"]:
            raise ValueError("evidence-ineligible exploratory rulebook cannot create a BUY position")
        certified_signal, horizon = _reference_signal_and_horizon(normalized_reference)
        normalized_context = _validated_entry_context(entry_context)
        normalized_risk = _validated_risk_snapshot(
            risk_snapshot, horizon
        )
    position = {
        "id": uuid.uuid4().hex,
        "ticker": ticker,
        "status": "closed" if has_sell_price else "open",
        "origin": origin.strip(),
        "signal_reference": normalized_reference,
        "certified_signal": certified_signal,
        "entry_context": normalized_context,
        "risk_snapshot": normalized_risk,
        "actual_buy_price": _positive_raw_int(actual_buy_price, "actual_buy_price"),
        "quantity": _optional_quantity(quantity),
        "buy_date": _iso_date(buy_date, "buy_date"),
        "opened_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
        "actual_sell_price": None,
        "sell_date": None,
        "closed_at": None,
        "sell_reason": None,
    }
    if has_sell_price:
        normalized_sell_date = _iso_date(sell_date, "sell_date")
        if normalized_sell_date < position["buy_date"]:
            raise ValueError("sell date cannot be before BUY date")
        position.update(
            {
                "actual_sell_price": _positive_raw_int(actual_sell_price, "actual_sell_price"),
                "sell_date": normalized_sell_date,
                "closed_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
                "sell_reason": "manual",
            }
        )
    return position


def create_manual_position(
    ticker: str,
    actual_buy_price: object,
    buy_date: object,
    *,
    actual_sell_price: object = None,
    sell_date: object = None,
    quantity: object = None,
    signal_reference: object = None,
    entry_context: object = None,
    risk_snapshot: object = None,
    origin: str = "current_positions",
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Append one manual BUY-only or completed BUY/SELL position atomically."""

    normalized_ticker, target = _manual_path(ticker, positions_dir)
    history = load_manual_position_history(normalized_ticker, positions_dir)
    position = _new_position(
        normalized_ticker,
        actual_buy_price,
        buy_date,
        actual_sell_price,
        sell_date,
        quantity,
        signal_reference,
        entry_context,
        risk_snapshot,
        origin,
    )
    if position["signal_reference"] is not None and position["status"] == "open":
        _assert_no_open_signal_overlap(
            position["signal_reference"], normalized_ticker, history, positions_dir
        )
    history["history"].append(position)
    validated = _validated_history(history, normalized_ticker)
    _write_history(validated, target)
    return copy.deepcopy(position)


def _find_position(history: dict[str, object], position_id: object) -> dict[str, object]:
    if not isinstance(position_id, str) or not position_id.strip():
        raise ValueError("position_id must be a non-empty string")
    position = next((item for item in history["history"] if item["id"] == position_id), None)
    if position is None:
        raise ValueError("position_id was not found in this manual history")
    return position


def update_manual_position(
    ticker: str,
    position_id: str,
    updates: object,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Atomically overwrite permitted manual values without association changes."""

    normalized_ticker, target = _manual_path(ticker, positions_dir)
    history = load_manual_position_history(normalized_ticker, positions_dir)
    if not isinstance(updates, Mapping) or not updates:
        raise ValueError("updates must be a non-empty object")
    allowed = {
        "status",
        "actual_buy_price",
        "actual_sell_price",
        "buy_date",
        "sell_date",
        "quantity",
    }
    if set(updates) - allowed:
        raise ValueError("updates contain unsupported fields")
    position = _find_position(history, position_id)
    candidate = copy.deepcopy(position)
    candidate.update({field: updates[field] for field in allowed if field in updates})
    if candidate.get("status") not in ("open", "closed"):
        raise ValueError("position status must be open or closed")
    if (
        position["status"] == "open"
        and candidate["status"] == "open"
        and any(updates.get(field) is not None for field in ("actual_sell_price", "sell_date"))
    ):
        raise ValueError("OPEN position cannot edit SELL price")

    candidate["actual_buy_price"] = _positive_raw_int(
        candidate.get("actual_buy_price"), "actual_buy_price"
    )
    candidate["quantity"] = _optional_quantity(candidate.get("quantity"))
    candidate["buy_date"] = _iso_date(candidate.get("buy_date"), "buy_date")
    if candidate["status"] == "open":
        candidate.update(
            {
                "actual_sell_price": None,
                "sell_date": None,
                "closed_at": None,
                "sell_reason": None,
            }
        )
        if position["status"] == "closed" and isinstance(
            candidate.get("signal_reference"), Mapping
        ):
            _assert_no_open_signal_overlap(
                candidate["signal_reference"], normalized_ticker, history, positions_dir
            )
    else:
        candidate["actual_sell_price"] = _positive_raw_int(
            candidate.get("actual_sell_price"), "actual_sell_price"
        )
        candidate["sell_date"] = _iso_date(candidate.get("sell_date"), "sell_date")
        if candidate["sell_date"] < candidate["buy_date"]:
            raise ValueError("sell date cannot be before BUY date")
        if position["status"] == "open":
            candidate["closed_at"] = datetime.now(_MARKET_TIMEZONE).isoformat()
        candidate["sell_reason"] = "manual"

    if "actual_buy_price" in updates and isinstance(candidate.get("risk_snapshot"), Mapping):
        _representative, horizon = _reference_signal_and_horizon(candidate["signal_reference"])
        candidate["risk_snapshot"] = _risk_for_buy_price(
            candidate["risk_snapshot"], int(candidate["actual_buy_price"]), horizon
        )
    if (
        "actual_buy_price" in updates
        or "buy_date" in updates
        or (position["status"] == "closed" and candidate["status"] == "open")
    ):
        candidate.pop("risk_suggestion_text", None)
        position.pop("risk_suggestion_text", None)
    position.update(candidate)
    validated = _validated_history(history, normalized_ticker)
    _write_history(validated, target)
    return copy.deepcopy(position)


def update_manual_position_risk_suggestion(
    ticker: str,
    position_id: str,
    risk_suggestion_text: str,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Atomically replace one OPEN manual position's current risk text only."""

    if not isinstance(risk_suggestion_text, str) or not risk_suggestion_text.strip():
        raise ValueError("risk_suggestion_text must be a non-empty string")
    normalized_ticker, target = _manual_path(ticker, positions_dir)
    history = load_manual_position_history(normalized_ticker, positions_dir)
    position = _find_position(history, position_id)
    if position["status"] != "open":
        raise ValueError("risk suggestion can be written only for an open position")
    position["risk_suggestion_text"] = risk_suggestion_text.strip()
    validated = _validated_history(history, normalized_ticker)
    _write_history(validated, target)
    return copy.deepcopy(position)


def delete_manual_position(
    ticker: str,
    position_id: str,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Atomically remove exactly one generic position without an archive."""

    normalized_ticker, target = _manual_path(ticker, positions_dir)
    history = load_manual_position_history(normalized_ticker, positions_dir)
    position = _find_position(history, position_id)
    removed = copy.deepcopy(position)
    history["history"] = [item for item in history["history"] if item["id"] != position_id]
    validated = _validated_history(history, normalized_ticker)
    _write_history(validated, target)
    return removed


def close_manual_position(
    ticker: str,
    position_id: str,
    actual_sell_price: object,
    sell_date: object,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Record one manual SELL against one exact OPEN generic position."""

    normalized_ticker, target = _manual_path(ticker, positions_dir)
    history = load_manual_position_history(normalized_ticker, positions_dir)
    position = _find_position(history, position_id)
    if position["status"] != "open":
        raise ValueError("position_id is not an open position")
    normalized_sell_date = _iso_date(sell_date, "sell_date")
    if normalized_sell_date < position["buy_date"]:
        raise ValueError("sell date cannot be before BUY date")
    position.update(
        {
            "status": "closed",
            "actual_sell_price": _positive_raw_int(actual_sell_price, "actual_sell_price"),
            "sell_date": normalized_sell_date,
            "closed_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
            "sell_reason": "manual",
        }
    )
    validated = _validated_history(history, normalized_ticker)
    _write_history(validated, target)
    return copy.deepcopy(position)


__all__ = [
    "close_manual_position",
    "build_v5_risk_snapshot",
    "create_manual_position",
    "delete_manual_position",
    "load_manual_position_history",
    "update_manual_position",
    "update_manual_position_risk_suggestion",
]
