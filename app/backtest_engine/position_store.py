"""Atomic, append-only manual position histories for certified signal sets."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import uuid
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from numbers import Integral, Real
from pathlib import Path

import pytz

from .config import HORIZONS, THEME_VARIANTS, _normalize_ticker, rulebook_for

# Read-only legacy history support. New position writes use schema-4 references.
CERTIFICATION_METRICS = ("win_rate", "profit", "sharpe")


ATR_SL_MULTIPLIER = rulebook_for("swing").atr_sl_multiplier
ATR_TP_MULTIPLIER = rulebook_for("swing").atr_tp_multiplier
MIN_EXIT_OFFSET_SWING_BARS = rulebook_for("swing").min_exit_offset_bars
_METRICS = CERTIFICATION_METRICS


_SCHEMA_VERSION = 1
_MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")


def _position_path(
    ticker: str,
    theme_variant: str,
    metric: str,
    positions_dir: str,
) -> tuple[str, Path]:
    normalized_ticker = _normalize_ticker(ticker)
    if theme_variant not in THEME_VARIANTS:
        raise ValueError(f"theme_variant must be one of {THEME_VARIANTS}")
    if metric not in _METRICS:
        raise ValueError(f"metric must be one of {_METRICS}")
    target = (
        Path(positions_dir)
        / normalized_ticker
        / f"{normalized_ticker}_positions_{theme_variant}_{metric}.json"
    )
    return normalized_ticker, target


def _empty_history(ticker: str, theme_variant: str, metric: str) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "ticker": ticker,
        "theme_variant": theme_variant,
        "metric": metric,
        "history": [],
    }


def _iso_date(value: object, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO date") from error


def _iso_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.isoformat()


def _positive_raw_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{field} must be a positive raw integer")
    normalized = int(value)
    if normalized <= 0:
        raise ValueError(f"{field} must be positive")
    return normalized


def _optional_quantity(value: object) -> int | None:
    if value is None:
        return None
    return _positive_raw_int(value, "quantity")


def _json_snapshot(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    snapshot = copy.deepcopy(dict(value))
    try:
        json.dumps(snapshot, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be JSON serializable") from error
    return snapshot


def _validated_certified_signal(
    value: object,
    metric: str,
    theme_variant: str,
) -> tuple[dict[str, object], str]:
    signal = _json_snapshot(value, "certified_signal")
    stored_metric = signal.get("metric")
    if stored_metric is None:
        metrics = signal.get("metrics")
        expected_metrics = [
            name for name in _METRICS if isinstance(metrics, list) and name in metrics
        ]
        if (
            not isinstance(metrics, list)
            or metrics != expected_metrics
            or len(set(metrics)) != len(metrics)
            or metric not in metrics
        ):
            raise ValueError("certified signal metrics do not match position tuple")
    elif stored_metric != metric:
        raise ValueError("certified signal metric does not match position tuple")
    if signal.get("theme_variant") != theme_variant:
        raise ValueError("certified signal theme variant does not match position tuple")
    certified_at = _iso_timestamp(signal.get("certified_at"), "certified_at")
    combo = signal.get("combo")
    if not isinstance(combo, Mapping):
        raise ValueError("certified signal must include combo metadata")
    if signal.get("direction") != "long" or combo.get("direction") != "long":
        raise ValueError("manual positions support long direction only")
    if combo.get("horizon") not in HORIZONS:
        raise ValueError(f"combo horizon must be one of {HORIZONS}")
    if combo.get("theme_variant") != theme_variant:
        raise ValueError("certified combo theme variant does not match position tuple")
    return signal, certified_at


def _validated_entry_context(value: object) -> dict[str, object]:
    context = _json_snapshot(value, "entry_context")
    match_level = context.get("match_level")
    if isinstance(match_level, bool) or not isinstance(match_level, Real):
        raise ValueError("entry_context match_level must be numeric")
    if not 0 <= float(match_level) <= 100:
        raise ValueError("entry_context match_level must be between 0 and 100")
    context["current_price"] = _positive_raw_int(
        context.get("current_price"), "entry_context current_price"
    )
    return context


def _validated_risk_snapshot(value: object, horizon: str) -> dict[str, object]:
    risk = _json_snapshot(value, "risk_snapshot")
    for field in ("atr", "stop_loss", "take_profit", "max_hold_bars"):
        risk[field] = _positive_raw_int(risk.get(field), f"risk_snapshot {field}")
    if horizon == "swing" and risk["max_hold_bars"] < MIN_EXIT_OFFSET_SWING_BARS + 1:
        raise ValueError("swing max_hold_bars must be at least 4")
    if horizon == "midterm" and risk["max_hold_bars"] < 2:
        raise ValueError("midterm max_hold_bars must be at least 2")
    if horizon not in HORIZONS:
        raise ValueError(f"combo horizon must be one of {HORIZONS}")
    return risk


def _validated_position(
    value: object,
    ticker: str,
    theme_variant: str,
    metric: str,
) -> dict[str, object]:
    position = _json_snapshot(value, "position")
    if not isinstance(position.get("id"), str) or not position["id"].strip():
        raise ValueError("position id must be a non-empty string")
    if (
        position.get("ticker") != ticker
        or position.get("theme_variant") != theme_variant
        or position.get("metric") != metric
    ):
        raise ValueError("position tuple does not match its history file")
    status = position.get("status")
    if status not in ("open", "closed"):
        raise ValueError("position status must be open or closed")

    signal, certified_at = _validated_certified_signal(
        position.get("certified_signal"), metric, theme_variant
    )
    position["certified_signal"] = signal
    if position.get("certified_at") != certified_at:
        raise ValueError("position certification timestamp does not match snapshot")
    position["entry_context"] = _validated_entry_context(position.get("entry_context"))
    combo = signal["combo"]
    position["risk_snapshot"] = _validated_risk_snapshot(
        position.get("risk_snapshot"), str(combo["horizon"])
    )
    position["actual_buy_price"] = _positive_raw_int(
        position.get("actual_buy_price"), "actual_buy_price"
    )
    position["quantity"] = _optional_quantity(position.get("quantity"))
    position["buy_date"] = _iso_date(position.get("buy_date"), "buy_date")
    position["opened_at"] = _iso_timestamp(position.get("opened_at"), "opened_at")

    sell_fields = (
        "actual_sell_price",
        "sell_date",
        "closed_at",
        "sell_reason",
    )
    if status == "open":
        if any(position.get(field) is not None for field in sell_fields):
            raise ValueError("open position cannot contain manual sell data")
        return position

    position["actual_sell_price"] = _positive_raw_int(
        position.get("actual_sell_price"), "actual_sell_price"
    )
    position["sell_date"] = _iso_date(position.get("sell_date"), "sell_date")
    if position["sell_date"] < position["buy_date"]:
        raise ValueError("sell date cannot be before BUY date")
    position["closed_at"] = _iso_timestamp(position.get("closed_at"), "closed_at")
    reason = position.get("sell_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("sell_reason must be a non-empty string")
    position["sell_reason"] = reason.strip()
    return position


def _validated_history(
    value: object,
    ticker: str,
    theme_variant: str,
    metric: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("position history must be a JSON object")
    if value.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported position history schema version")
    if (
        value.get("ticker") != ticker
        or value.get("theme_variant") != theme_variant
        or value.get("metric") != metric
    ):
        raise ValueError("position history tuple does not match requested tuple")
    history = value.get("history")
    if not isinstance(history, list):
        raise ValueError("position history must contain a history list")

    validated = [
        _validated_position(position, ticker, theme_variant, metric)
        for position in history
    ]
    if len({position["id"] for position in validated}) != len(validated):
        raise ValueError("position history contains duplicate ids")
    if sum(position["status"] == "open" for position in validated) > 1:
        raise ValueError("position history contains more than one open position")
    return {
        "schema_version": _SCHEMA_VERSION,
        "ticker": ticker,
        "theme_variant": theme_variant,
        "metric": metric,
        "history": validated,
    }


def _write_history(history: dict[str, object], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # ponytail: os.replace prevents torn files, not concurrent-writer lost updates.
    # Add a cross-process lock before this store has multiple simultaneous writers.
    content = json.dumps(history, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def load_position_history(
    ticker: str,
    theme_variant: str,
    metric: str,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Load one tuple's history without creating or changing a file."""

    normalized_ticker, target = _position_path(
        ticker, theme_variant, metric, positions_dir
    )
    if not target.exists():
        return _empty_history(normalized_ticker, theme_variant, metric)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("position history is not valid JSON") from error
    return _validated_history(payload, normalized_ticker, theme_variant, metric)


def open_position(
    ticker: str,
    theme_variant: str,
    metric: str,
    certified_signal: object,
    entry_context: object,
    risk_snapshot: object,
    actual_buy_price: object,
    buy_date: object,
    positions_dir: str = "backtest-positions",
    quantity: object = None,
) -> dict[str, object]:
    """Append one explicitly confirmed long BUY position for a signal tuple."""

    normalized_ticker, target = _position_path(
        ticker, theme_variant, metric, positions_dir
    )
    history = load_position_history(
        normalized_ticker, theme_variant, metric, positions_dir
    )
    if any(position["status"] == "open" for position in history["history"]):
        raise ValueError("position tuple already has an open position")

    signal, certified_at = _validated_certified_signal(
        certified_signal, metric, theme_variant
    )
    position = {
        "id": uuid.uuid4().hex,
        "ticker": normalized_ticker,
        "theme_variant": theme_variant,
        "metric": metric,
        "status": "open",
        "certified_signal": signal,
        "certified_at": certified_at,
        "entry_context": _validated_entry_context(entry_context),
        "risk_snapshot": _validated_risk_snapshot(
            risk_snapshot, str(signal["combo"]["horizon"])
        ),
        "actual_buy_price": _positive_raw_int(actual_buy_price, "actual_buy_price"),
        "quantity": _optional_quantity(quantity),
        "buy_date": _iso_date(buy_date, "buy_date"),
        "opened_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
        "actual_sell_price": None,
        "sell_date": None,
        "closed_at": None,
        "sell_reason": None,
    }
    history["history"].append(position)
    validated = _validated_history(history, normalized_ticker, theme_variant, metric)
    _write_history(validated, target)
    return copy.deepcopy(position)


def _risk_for_buy_price(
    risk_snapshot: Mapping[str, object], buy_price: int, horizon: str = "swing"
) -> dict[str, object]:
    rulebook = rulebook_for(horizon)
    risk = copy.deepcopy(dict(risk_snapshot))
    atr = _positive_raw_int(risk.get("atr"), "risk_snapshot atr")
    price = Decimal(buy_price)
    atr_value = Decimal(atr)
    stop_loss = int(
        (price - atr_value * Decimal(str(rulebook.atr_sl_multiplier))).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    take_profit = int(
        (price + atr_value * Decimal(str(rulebook.atr_tp_multiplier))).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    if stop_loss <= 0 or take_profit <= 0:
        raise ValueError("BUY price and frozen ATR cannot produce valid exit levels")
    risk["stop_loss"] = stop_loss
    risk["take_profit"] = take_profit
    return risk


def _find_position(history: dict[str, object], position_id: object) -> dict[str, object]:
    if not isinstance(position_id, str) or not position_id.strip():
        raise ValueError("position_id must be a non-empty string")
    position = next(
        (item for item in history["history"] if item["id"] == position_id),
        None,
    )
    if position is None:
        raise ValueError("position_id was not found in this tuple history")
    return position


def _assert_legacy_reopen_has_no_overlap(
    position: Mapping[str, object],
    history: Mapping[str, object],
    ticker: str,
    theme_variant: str,
    metric: str,
    positions_dir: str,
) -> None:
    """Reject reopening when this immutable set is already OPEN elsewhere."""

    position_id = position.get("id")
    if any(
        item.get("id") != position_id and item.get("status") == "open"
        for item in history["history"]
    ):
        raise ValueError("saved signal set already has an OPEN position")

    # Lazy imports avoid the existing manual-store -> legacy-store import cycle.
    from .manual_position_store import load_manual_position_history
    from .position_identity import position_signal_link_keys, signal_link_key

    requested = signal_link_key(
        theme_variant, metric, position["certified_signal"]
    )
    generic = load_manual_position_history(ticker, positions_dir)
    if any(
        item.get("status") == "open"
        and requested in position_signal_link_keys(item)
        for item in generic["history"]
    ):
        raise ValueError("saved signal set already has an OPEN position")


def update_position(
    ticker: str,
    theme_variant: str,
    metric: str,
    position_id: str,
    updates: object,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Atomically overwrite permitted values without changing identity fields."""

    normalized_ticker, target = _position_path(
        ticker, theme_variant, metric, positions_dir
    )
    history = load_position_history(
        normalized_ticker, theme_variant, metric, positions_dir
    )
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
    unknown = set(updates) - allowed
    if unknown:
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
        if position["status"] == "closed":
            _assert_legacy_reopen_has_no_overlap(
                candidate,
                history,
                normalized_ticker,
                theme_variant,
                metric,
                positions_dir,
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

    if "actual_buy_price" in updates:
        risk = candidate["risk_snapshot"]
        if not isinstance(risk, Mapping):
            raise ValueError("position risk_snapshot must be an object")
        candidate["risk_snapshot"] = _risk_for_buy_price(
            risk,
            int(candidate["actual_buy_price"]),
            str(candidate["certified_signal"]["combo"]["horizon"]),
        )

    position.update(candidate)
    validated = _validated_history(history, normalized_ticker, theme_variant, metric)
    _write_history(validated, target)
    return copy.deepcopy(position)


def delete_position(
    ticker: str,
    theme_variant: str,
    metric: str,
    position_id: str,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Atomically remove exactly one legacy position without an archive."""

    normalized_ticker, target = _position_path(
        ticker, theme_variant, metric, positions_dir
    )
    history = load_position_history(
        normalized_ticker, theme_variant, metric, positions_dir
    )
    position = _find_position(history, position_id)
    removed = copy.deepcopy(position)
    history["history"] = [item for item in history["history"] if item["id"] != position_id]
    validated = _validated_history(history, normalized_ticker, theme_variant, metric)
    _write_history(validated, target)
    return removed


def close_position(
    ticker: str,
    theme_variant: str,
    metric: str,
    position_id: str,
    actual_sell_price: object,
    sell_date: object,
    sell_reason: str,
    positions_dir: str = "backtest-positions",
) -> dict[str, object]:
    """Record an explicit manual SELL fill for the named open position only."""

    normalized_ticker, target = _position_path(
        ticker, theme_variant, metric, positions_dir
    )
    history = load_position_history(
        normalized_ticker, theme_variant, metric, positions_dir
    )
    if not isinstance(position_id, str) or not position_id.strip():
        raise ValueError("position_id must be a non-empty string")

    position = next(
        (item for item in history["history"] if item["id"] == position_id),
        None,
    )
    if position is None:
        raise ValueError("position_id was not found in this tuple history")
    if position["status"] != "open":
        raise ValueError("position_id is not an open position")

    normalized_sell_date = _iso_date(sell_date, "sell_date")
    if normalized_sell_date < position["buy_date"]:
        raise ValueError("sell date cannot be before BUY date")
    if not isinstance(sell_reason, str) or not sell_reason.strip():
        raise ValueError("sell_reason must be a non-empty string")
    position.update(
        {
            "status": "closed",
            "actual_sell_price": _positive_raw_int(
                actual_sell_price, "actual_sell_price"
            ),
            "sell_date": normalized_sell_date,
            "closed_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
            "sell_reason": sell_reason.strip(),
        }
    )
    validated = _validated_history(history, normalized_ticker, theme_variant, metric)
    _write_history(validated, target)
    return copy.deepcopy(position)


__all__ = [
    "close_position",
    "delete_position",
    "load_position_history",
    "open_position",
    "update_position",
]
