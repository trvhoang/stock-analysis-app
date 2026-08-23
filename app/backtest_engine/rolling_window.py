"""Chronological flat-to-flat execution for one V3 rulebook treatment."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import RulebookExecution, TradeEvent


@dataclass(frozen=True)
class Window:
    """A read-only reporting partition retained for diagnostic consumers."""

    start_date: pd.Timestamp
    end_date: pd.Timestamp


def _as_trade_price(value: float):
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric


def _trade_levels(
    entry_price: float,
    signal_atr: float,
    execution: RulebookExecution,
) -> tuple[float, float]:
    rulebook = execution.rulebook
    return (
        entry_price - signal_atr * rulebook.atr_sl_multiplier,
        entry_price + signal_atr * rulebook.atr_tp_multiplier,
    )


def _first_exit(
    candidates: pd.DataFrame,
    stop_loss: float,
    take_profit: float,
) -> tuple[pd.Series | None, str | None]:
    """Return the first price exit, resolving a shared hit stop-first."""

    if candidates.empty:
        return None, None
    low_hits = candidates["low"].to_numpy() <= stop_loss
    high_hits = candidates["high"].to_numpy() >= take_profit
    positions = np.flatnonzero(low_hits | high_hits)
    if not len(positions):
        return None, None
    position = int(positions[0])
    return candidates.iloc[position], "stop_loss" if low_hits[position] else "take_profit"


def _entry_series(entry_signal, index: pd.Index) -> pd.Series:
    """Normalize one Boolean V3 entry signal without fabricating missing rows."""

    if isinstance(entry_signal, pd.Series):
        return entry_signal.reindex(index, fill_value=False).fillna(False).astype(bool)
    return pd.Series(entry_signal, index=index).fillna(False).astype(bool)


def run_rulebook_trade_sequence(
    frame: pd.DataFrame,
    execution: RulebookExecution,
    entry_signal,
) -> list[TradeEvent]:
    """Execute one non-overlapping long-only rulebook sequence on native bars."""

    if not isinstance(execution, RulebookExecution):
        raise ValueError("execution must be a RulebookExecution")
    if frame.empty or "date" not in frame.columns:
        return []
    required_columns = {"open", "high", "low", "close", "ATR_14"}
    if missing := required_columns.difference(frame.columns):
        raise ValueError(f"frame missing trade columns: {', '.join(sorted(missing))}")

    working = frame.copy(deep=True).reset_index(drop=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if working["date"].isna().any() or not working["date"].is_monotonic_increasing:
        raise ValueError("frame dates must be sorted in ascending order")
    entries = _entry_series(entry_signal, working.index)
    rulebook = execution.rulebook
    events: list[TradeEvent] = []
    cursor = 0

    while cursor < len(working):
        later_entries = entries.iloc[cursor:]
        if not later_entries.any():
            break
        signal_position = int(later_entries[later_entries].index[0])
        entry_position = signal_position + 1
        if entry_position >= len(working):
            break

        signal_atr = pd.to_numeric(
            working.loc[signal_position, "ATR_14"],
            errors="coerce",
        )
        entry_price = pd.to_numeric(
            working.loc[entry_position, "open"],
            errors="coerce",
        )
        if (
            pd.isna(signal_atr)
            or float(signal_atr) <= 0
            or pd.isna(entry_price)
            or float(entry_price) <= 0
        ):
            cursor = signal_position + 1
            continue

        timeout_position = entry_position + rulebook.max_hold_bars - 1
        if timeout_position >= len(working):
            # The entry is open, so later entry signals are intentionally skipped.
            break
        entry_value = float(entry_price)
        atr_value = float(signal_atr)
        stop_loss, take_profit = _trade_levels(entry_value, atr_value, execution)
        eligible_exit_rows = working.iloc[
            entry_position + rulebook.min_exit_offset_bars : timeout_position + 1
        ]
        exit_row, exit_reason = _first_exit(
            eligible_exit_rows,
            stop_loss,
            take_profit,
        )
        if exit_row is None:
            exit_row = working.iloc[timeout_position]
            exit_reason = "timeout"
            exit_price = float(exit_row["close"])
        elif exit_reason == "stop_loss":
            exit_price = stop_loss
        else:
            exit_price = take_profit

        exit_position = int(exit_row.name)
        events.append(
            TradeEvent(
                signal_date=working.loc[signal_position, "date"],
                entry_date=working.loc[entry_position, "date"],
                entry_price=_as_trade_price(entry_value),
                atr=_as_trade_price(atr_value),
                stop_loss=_as_trade_price(stop_loss),
                take_profit=_as_trade_price(take_profit),
                exit_date=exit_row["date"],
                exit_price=_as_trade_price(exit_price),
                exit_reason=exit_reason,
                return_pct=(exit_price - entry_value) / entry_value * 100.0,
                source_window=(working.iloc[0]["date"], working.iloc[-1]["date"]),
            )
        )
        # A signal on the exit bar may open at the following native-bar open.
        cursor = exit_position

    return events


def partition_completed_events(events, window: Window) -> list:
    """Return only events fully contained in one reporting partition."""

    return [
        event
        for event in events
        if window.start_date <= pd.Timestamp(event.signal_date) <= window.end_date
        and window.start_date <= pd.Timestamp(event.entry_date) <= window.end_date
        and window.start_date <= pd.Timestamp(event.exit_date) <= window.end_date
    ]


__all__ = ["Window", "partition_completed_events", "run_rulebook_trade_sequence"]
