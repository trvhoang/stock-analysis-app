"""Read-only native-horizon monitoring for manually confirmed positions."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Integral

import pandas as pd

from .config import HORIZONS, rulebook_for
from .data_quality import validate_ohlcv
from .timeframes import to_weekly_ohlcv


MIN_EXIT_OFFSET_SWING_BARS = rulebook_for("swing").min_exit_offset_bars


def _position_value(position: Mapping[str, object], key: str) -> object:
    value = position.get(key)
    if value is None:
        raise ValueError(f"position is missing {key}")
    return value


def _positive_raw_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{field} must be a positive raw integer")
    normalized = int(value)
    if normalized <= 0:
        raise ValueError(f"{field} must be positive")
    return normalized


def _position_contract(position: Mapping[str, object]) -> tuple[str, pd.Timestamp, dict[str, int]]:
    if position.get("status") != "open":
        raise ValueError("position must be open to monitor")
    signal = _position_value(position, "certified_signal")
    if not isinstance(signal, Mapping):
        raise ValueError("position certified_signal must be an object")
    combo = signal.get("combo")
    if isinstance(combo, Mapping):
        if combo.get("direction") != "long":
            raise ValueError("position must contain a long certified combo")
        horizon = combo.get("horizon")
    else:
        # V3 stores the frozen all-metrics rulebook snapshot directly.
        horizon = signal.get("horizon")
    if horizon not in HORIZONS:
        raise ValueError(f"position horizon must be one of {HORIZONS}")

    buy_date = pd.to_datetime(_position_value(position, "buy_date"), errors="coerce")
    if pd.isna(buy_date):
        raise ValueError("position buy_date must be an ISO date")
    risk = _position_value(position, "risk_snapshot")
    if not isinstance(risk, Mapping):
        raise ValueError("position risk_snapshot must be an object")
    values = {
        field: _positive_raw_int(risk.get(field), f"risk_snapshot {field}")
        for field in ("atr", "stop_loss", "take_profit", "max_hold_bars")
    }
    return str(horizon), buy_date.normalize(), values


def _as_of_slice(raw_history: pd.DataFrame, as_of_date: object) -> tuple[pd.DataFrame, pd.Timestamp]:
    quality = validate_ohlcv(raw_history)
    if not quality.is_valid or quality.valid_frame is None:
        raise ValueError("invalid position history data: " + "; ".join(quality.errors))
    as_of = pd.to_datetime(as_of_date, errors="coerce")
    if pd.isna(as_of):
        raise ValueError("as_of_date must be a valid date")
    source = quality.valid_frame.copy(deep=True)
    source["date"] = pd.to_datetime(source["date"])
    source = source[source["date"] <= as_of].copy()
    if source.empty:
        raise ValueError("position history has no source rows on or before as_of_date")
    return source, as_of.normalize()


def _native_position_rows(
    source: pd.DataFrame,
    buy_date: pd.Timestamp,
    horizon: str,
) -> tuple[int, int]:
    source_dates = pd.to_datetime(source["date"])
    entry_rows = source[source_dates >= buy_date]
    if entry_rows.empty:
        raise ValueError("position buy_date has no ticker trading session on or after it")
    entry_date = pd.Timestamp(entry_rows.iloc[0]["date"]).normalize()

    if horizon == "swing":
        holding_rows = source[source_dates >= entry_date]
        return len(holding_rows), _positive_raw_int(holding_rows.iloc[-1]["close"], "latest_close")

    source = source.assign(_period=source_dates.dt.to_period("W-SUN"))
    buy_period = entry_date.to_period("W-SUN")
    holding_periods = source.loc[source["_period"] >= buy_period, "_period"].drop_duplicates()
    weekly = to_weekly_ohlcv(source.drop(columns="_period"))
    return len(holding_periods), _positive_raw_int(weekly.iloc[-1]["close"], "latest_close")


def monitor_position(
    position: dict[str, object],
    raw_history: pd.DataFrame,
    as_of_date: object,
) -> dict[str, object]:
    """Return native-clock SELL eligibility without mutating position storage."""

    if not isinstance(position, Mapping):
        raise ValueError("position must be an object")
    horizon, buy_date, risk = _position_contract(position)
    source, as_of = _as_of_slice(raw_history, as_of_date)
    holding_bars, latest_close = _native_position_rows(source, buy_date, horizon)
    suggested_holding_bars = risk["max_hold_bars"]
    holding_period_exceeded = holding_bars * 100 > suggested_holding_bars * 60
    exit_eligible = (
        holding_bars >= MIN_EXIT_OFFSET_SWING_BARS + 1
        if horizon == "swing"
        else holding_bars >= 2
    )
    stop_loss_near = latest_close * 100 <= risk["stop_loss"] * 105
    take_profit_near = latest_close * 100 >= risk["take_profit"] * 95
    reasons: list[str] = []
    if holding_period_exceeded:
        reasons.append("holding_period_exceeds_sixty_percent")
    if stop_loss_near:
        reasons.append("near_stop_loss")
    if take_profit_near:
        reasons.append("near_take_profit")
    if not exit_eligible:
        reasons.append("minimum_native_holding_period_not_reached")

    return {
        "horizon": horizon,
        "as_of_date": source["date"].iloc[-1].date().isoformat(),
        "latest_close": latest_close,
        "holding_bars": holding_bars,
        "suggested_holding_bars": suggested_holding_bars,
        "holding_ratio": round(holding_bars / suggested_holding_bars, 4),
        "holding_period_exceeded": holding_period_exceeded,
        "exit_eligible": exit_eligible,
        "stop_loss_near": stop_loss_near,
        "take_profit_near": take_profit_near,
        "timeout_reached": holding_bars >= suggested_holding_bars,
        "sell_allowed": exit_eligible
        and (holding_period_exceeded or stop_loss_near or take_profit_near),
        "reasons": reasons,
    }


__all__ = ["monitor_position"]
