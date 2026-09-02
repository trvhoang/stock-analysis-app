"""Read-only current-position records and derived P&L for Backtest Lab."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .config import THEME_VARIANTS
from .manual_position_store import load_manual_position_history
from .position_store import load_position_history


# Existing per-metric files are historical records only.
CERTIFICATION_METRICS = ("win_rate", "profit", "sharpe")
_HORIZON_LABELS = {"swing": "Swing", "midterm": "Mid-term"}


def load_all_positions(
    positions_dir: str = "backtest-positions",
) -> tuple[tuple[dict[str, object], ...], tuple[str, ...]]:
    """Load all valid saved records while isolating malformed tuple histories."""

    root = Path(positions_dir)
    if not root.exists():
        return (), ()

    records: list[dict[str, object]] = []
    errors: list[str] = []
    for ticker_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        ticker = ticker_dir.name.strip().upper()
        for theme_variant in THEME_VARIANTS:
            for metric in CERTIFICATION_METRICS:
                try:
                    history = load_position_history(
                        ticker, theme_variant, metric, str(root)
                    )
                except (OSError, ValueError) as error:
                    errors.append(f"{ticker}/{theme_variant}/{metric}: {error}")
                    continue
                records.extend(
                    _with_locator(position, "legacy")
                    for position in history["history"]
                    if isinstance(position, Mapping)
                )
        try:
            generic = load_manual_position_history(ticker, str(root))
        except (OSError, ValueError) as error:
            errors.append(f"{ticker}/manual: {error}")
        else:
            records.extend(
                _with_locator(position, "manual")
                for position in generic["history"]
                if isinstance(position, Mapping)
            )
    return tuple(records), tuple(errors)


def _with_locator(position: Mapping[str, object], record_source: str) -> dict[str, object]:
    record = dict(position)
    locator = {
        "record_source": record_source,
        "ticker": record.get("ticker"),
        "id": record.get("id"),
    }
    if record_source == "legacy":
        locator.update(
            {
                "theme_variant": record.get("theme_variant"),
                "metric": record.get("metric"),
            }
        )
    record["record_source"] = record_source
    record["position_locator"] = locator
    return record


def load_latest_close_prices(
    tickers: Iterable[object],
    engine,
) -> dict[str, dict[str, object]]:
    """Read each requested ticker's latest raw close in one bound query."""

    normalized = list(
        dict.fromkeys(
            str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()
        )
    )
    if not normalized:
        return {}

    query = text(
        """
        SELECT DISTINCT ON (ticker) ticker, date, close
        FROM trading_data
        WHERE ticker = ANY(%(tickers)s)
        ORDER BY ticker, date DESC
        """
    )
    connection = engine.raw_connection()
    try:
        frame = pd.read_sql(query.text, connection, params={"tickers": normalized})
    finally:
        connection.close()

    prices: dict[str, dict[str, object]] = {}
    for row in frame.to_dict("records"):
        ticker = str(row.get("ticker", "")).strip().upper()
        close = row.get("close")
        price_date = pd.to_datetime(row.get("date"), errors="coerce")
        if not ticker or isinstance(close, bool):
            continue
        try:
            raw_close = int(close)
        except (TypeError, ValueError):
            continue
        if raw_close <= 0 or pd.isna(price_date):
            continue
        prices[ticker] = {
            "close": raw_close,
            "date": price_date.date().isoformat(),
        }
    return prices


def load_completed_trading_sessions(
    records: Iterable[Mapping[str, object]],
    latest_prices: Mapping[str, Mapping[str, object]],
    engine,
) -> dict[str, list[str]]:
    """Load all required ticker sessions once for completed hold-time counts."""

    ranges: dict[str, tuple[str, str]] = {}
    for position in records:
        ticker = str(position.get("ticker", "")).strip().upper()
        buy_date = pd.to_datetime(position.get("buy_date"), errors="coerce")
        is_open = str(position.get("status", "")).lower() == "open"
        reference = (
            latest_prices.get(ticker, {}).get("date")
            if is_open and isinstance(latest_prices.get(ticker), Mapping)
            else position.get("sell_date")
        )
        reference_date = pd.to_datetime(reference, errors="coerce")
        if not ticker or pd.isna(buy_date) or pd.isna(reference_date) or reference_date < buy_date:
            continue
        start = buy_date.date().isoformat()
        end = reference_date.date().isoformat()
        previous = ranges.get(ticker)
        ranges[ticker] = (
            min(start, previous[0]) if previous else start,
            max(end, previous[1]) if previous else end,
        )
    if not ranges:
        return {}

    tickers = sorted(ranges)
    query = text(
        """
        WITH requested AS (
            SELECT *
            FROM unnest(
                %(tickers)s::text[],
                %(start_dates)s::date[],
                %(end_dates)s::date[]
            ) AS request(ticker, start_date, end_date)
        )
        SELECT data.ticker, data.date
        FROM trading_data AS data
        JOIN requested
          ON requested.ticker = data.ticker
         AND data.date > requested.start_date
         AND data.date <= requested.end_date
        ORDER BY data.ticker, data.date
        """
    )
    params = {
        "tickers": tickers,
        "start_dates": [ranges[ticker][0] for ticker in tickers],
        "end_dates": [ranges[ticker][1] for ticker in tickers],
    }
    connection = engine.raw_connection()
    try:
        frame = pd.read_sql(query.text, connection, params=params)
    finally:
        connection.close()

    sessions = {ticker: [] for ticker in tickers}
    for row in frame.to_dict("records"):
        ticker = str(row.get("ticker", "")).strip().upper()
        session_date = pd.to_datetime(row.get("date"), errors="coerce")
        if ticker in sessions and not pd.isna(session_date):
            sessions[ticker].append(session_date.date().isoformat())
    return sessions


def _profit_values(
    buy_price: object,
    reference_price: object,
    quantity: object,
) -> tuple[int | None, float | None]:
    try:
        buy = Decimal(int(buy_price))
        reference = Decimal(int(reference_price))
    except (InvalidOperation, TypeError, ValueError):
        return None, None
    if buy <= 0 or reference <= 0:
        return None, None
    difference = reference - buy
    multiplier = Decimal(1)
    if quantity is not None:
        if isinstance(quantity, bool):
            return None, None
        try:
            numeric_quantity = int(quantity)
        except (TypeError, ValueError):
            return None, None
        if numeric_quantity <= 0:
            return None, None
        multiplier = Decimal(numeric_quantity)
    return int(difference * multiplier), round(float(difference / buy * 100), 2)


def _signal_set(position: Mapping[str, object]) -> str:
    reference = position.get("signal_reference")
    if isinstance(reference, Mapping):
        horizon = reference.get("horizon")
        if reference.get("schema_version") == 5 and horizon in _HORIZON_LABELS:
            return (
                f"{_HORIZON_LABELS[horizon]} — {reference.get('rulebook_id')} "
                f"— {reference.get('preferred_variant')}"
            )
        metrics = reference.get("metrics")
        labels = ", ".join(str(metric) for metric in metrics) if isinstance(metrics, list) else "Unknown"
        signal = position.get("certified_signal")
        combo = signal.get("combo") if isinstance(signal, Mapping) else None
        strategy = combo.get("strategy_id") if isinstance(combo, Mapping) else None
        return f"{labels}: {strategy or 'saved strategy'}"
    signal = position.get("certified_signal")
    if not isinstance(signal, Mapping):
        return "-"
    combo = signal.get("combo")
    strategy = combo.get("strategy_id") if isinstance(combo, Mapping) else None
    metric = signal.get("metric", position.get("metric", "Unknown"))
    return f"{metric}: {strategy or 'legacy strategy'}"


def _risk_suggestion_text(position: Mapping[str, object], record_source: object) -> str:
    if record_source != "manual":
        return "N/A"
    value = position.get("risk_suggestion_text")
    return value.strip() if isinstance(value, str) and value.strip() else "N/A"


def build_position_trade_rows(
    row: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Project an overview row into immutable raw BUY and SELL display records."""

    position = row.get("position")
    position = position if isinstance(position, Mapping) else {}
    risk = position.get("risk_snapshot")
    risk = risk if isinstance(risk, Mapping) else {}
    risk_text = _risk_suggestion_text(position, row.get("record_source"))
    is_closed = str(row.get("status", "")).lower() == "closed"
    shared = {
        "position_id": row.get("id"),
        "ticker": row.get("ticker"),
        "status": row.get("status"),
    }
    return (
        {
            **shared,
            "trade": "BUY",
            "actual_buy_price": row.get("actual_buy_price"),
            "buy_date": row.get("buy_date"),
            "quantity": row.get("quantity"),
            "signal_set": row.get("signal_set"),
            "current_price": row.get("current_price"),
            "profit_raw": row.get("profit_raw"),
            "profit_pct": row.get("profit_pct"),
            "holding_sessions": row.get("holding_sessions"),
            "opened_at": row.get("opened_at"),
            "closed_at": row.get("closed_at"),
            "risk_suggestion_text": risk_text,
            "risk_struck": is_closed and risk_text != "N/A",
        },
        {
            **shared,
            "trade": "SELL",
            "actual_sell_price": row.get("actual_sell_price"),
            "sell_date": row.get("sell_date"),
            "suggestion": {
                "projected_exit": None,
                "suggested_holding_bars": risk.get("max_hold_bars"),
                "stop_loss": risk.get("stop_loss"),
                "take_profit": risk.get("take_profit"),
            },
        },
    )


def summarize_positions(
    records: Iterable[Mapping[str, object]],
    latest_prices: Mapping[str, Mapping[str, object]],
    sessions_by_ticker: Mapping[str, Iterable[str]] | None = None,
) -> list[dict[str, object]]:
    """Build oldest-first display rows without modifying saved positions."""

    rows: list[dict[str, object]] = []
    sessions_by_ticker = sessions_by_ticker or {}
    for position in records:
        ticker = str(position.get("ticker", "")).strip().upper()
        status = str(position.get("status", "")).lower()
        is_open = status == "open"
        latest = latest_prices.get(ticker, {}) if is_open else {}
        current_price = latest.get("close") if isinstance(latest, Mapping) else None
        reference_price = current_price if is_open else position.get("actual_sell_price")
        reference_date = latest.get("date") if is_open and isinstance(latest, Mapping) else position.get("sell_date")
        buy_date = position.get("buy_date")
        holding_sessions = None
        if isinstance(buy_date, str) and isinstance(reference_date, str):
            holding_sessions = sum(
                buy_date < session_date <= reference_date
                for session_date in sessions_by_ticker.get(ticker, ())
            )
        profit_raw, profit_pct = _profit_values(
            position.get("actual_buy_price"), reference_price, position.get("quantity")
        )
        rows.append(
            {
                "id": position.get("id"),
                "ticker": ticker,
                "theme_variant": position.get("theme_variant"),
                "metric": position.get("metric"),
                "status": status,
                "actual_buy_price": position.get("actual_buy_price"),
                "actual_sell_price": position.get("actual_sell_price"),
                "quantity": position.get("quantity"),
                "current_price": current_price,
                "current_price_date": latest.get("date") if isinstance(latest, Mapping) else None,
                "profit_raw": profit_raw,
                "profit_pct": profit_pct,
                "opened_at": position.get("opened_at"),
                "closed_at": position.get("closed_at"),
                "buy_date": position.get("buy_date"),
                "sell_date": position.get("sell_date"),
                "holding_sessions": holding_sessions,
                "signal_set": _signal_set(position),
                "record_source": position.get("record_source"),
                "position_locator": position.get("position_locator"),
                "position": dict(position),
            }
        )
    return sorted(rows, key=lambda row: str(row.get("opened_at", "")))


__all__ = [
    "build_position_trade_rows",
    "load_all_positions",
    "load_completed_trading_sessions",
    "load_latest_close_prices",
    "summarize_positions",
]
