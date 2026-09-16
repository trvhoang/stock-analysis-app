"""Reference flat-to-flat execution over v2 native bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math

import numpy as np

from .contracts import RulebookDefinitionV2, semantic_digest
from .history import NativeBar, NativePartition


@dataclass(frozen=True)
class CompletedTrade:
    """One completed gross long trade whose dates are actual source sessions."""

    trade_id: str
    signal_date: date
    entry_date: date
    exit_date: date
    signal_bar_ordinal: int
    entry_bar_ordinal: int
    exit_bar_ordinal: int
    entry_price: int
    exit_price: float
    exit_reason: str
    return_pct: float


@dataclass(frozen=True)
class _OpenTrade:
    signal_ordinal: int
    entry_ordinal: int
    entry_price: int
    frozen_atr: float | None
    high_water: float


def _boolean_mask(value: object, size: int, name: str, *, optional: bool = False) -> np.ndarray | None:
    if value is None:
        if optional:
            return None
        raise ValueError(f"{name} is required")
    mask = np.asarray(value)
    if mask.shape != (size,) or mask.dtype != np.dtype(bool):
        raise ValueError(f"{name} must be one Boolean value per native bar")
    return mask


def _atr_values(value: object, size: int, definition: RulebookDefinitionV2) -> np.ndarray | None:
    if definition.atr_exit is None:
        return None
    if value is None:
        raise ValueError("atr_values are required when ATR exits are enabled")
    values = np.asarray(value, dtype=float)
    if values.shape != (size,):
        raise ValueError("atr_values must be one numeric value per native bar")
    return values


def _validate_partition(bars: tuple[NativeBar, ...], partition: NativePartition) -> None:
    if not isinstance(partition, NativePartition):
        raise ValueError("execution requires NativePartition")
    if not 0 <= partition.start_ordinal <= partition.end_ordinal < len(bars):
        raise ValueError("partition ordinals are outside native bars")
    start, end = bars[partition.start_ordinal], bars[partition.end_ordinal]
    if (
        start.first_session != partition.start_session
        or end.last_session != partition.end_session
        or start.bucket_label != partition.start_bucket
        or end.bucket_label != partition.end_bucket
    ):
        raise ValueError("partition bounds do not match native bars")


def _exit_price(
    bar: NativeBar,
    definition: RulebookDefinitionV2,
    open_trade: _OpenTrade,
) -> tuple[float, str] | None:
    """Apply gaps then stop-first intrabar collisions against prior high-water."""

    if open_trade.frozen_atr is None or definition.atr_exit is None:
        return None
    atr_exit = definition.atr_exit
    stop_levels: list[float] = []
    if atr_exit.stop_multiplier is not None:
        stop_levels.append(open_trade.entry_price - float(atr_exit.stop_multiplier) * open_trade.frozen_atr)
    if atr_exit.trailing_multiplier is not None:
        stop_levels.append(open_trade.high_water - float(atr_exit.trailing_multiplier) * open_trade.frozen_atr)
    stop = max(stop_levels) if stop_levels else None
    target = (
        open_trade.entry_price + float(atr_exit.target_multiplier) * open_trade.frozen_atr
        if atr_exit.target_multiplier is not None else None
    )
    if stop is not None and bar.open <= stop:
        return float(bar.open), "stop_loss"
    if target is not None and bar.open >= target:
        return float(bar.open), "take_profit"
    if stop is not None and bar.low <= stop:
        return stop, "stop_loss"
    if target is not None and bar.high >= target:
        return target, "take_profit"
    return None


def _trade_id(definition: RulebookDefinitionV2, ticker: str, open_trade: _OpenTrade, exit_ordinal: int) -> str:
    return "frt2_" + semantic_digest({
        "rulebook": definition.semantic_digest,
        "ticker": ticker,
        "signal": open_trade.signal_ordinal,
        "entry": open_trade.entry_ordinal,
        "exit": exit_ordinal,
    })


def _complete_trade(
    bars: tuple[NativeBar, ...],
    definition: RulebookDefinitionV2,
    ticker: str,
    open_trade: _OpenTrade,
    exit_ordinal: int,
    exit_price: float,
    exit_reason: str,
) -> CompletedTrade:
    signal, entry, exit_bar = bars[open_trade.signal_ordinal], bars[open_trade.entry_ordinal], bars[exit_ordinal]
    return CompletedTrade(
        trade_id=_trade_id(definition, ticker, open_trade, exit_ordinal),
        signal_date=signal.last_session,
        entry_date=entry.first_session,
        exit_date=exit_bar.last_session if exit_reason == "timeout" else exit_bar.first_session,
        signal_bar_ordinal=open_trade.signal_ordinal,
        entry_bar_ordinal=open_trade.entry_ordinal,
        exit_bar_ordinal=exit_ordinal,
        entry_price=open_trade.entry_price,
        exit_price=exit_price,
        exit_reason=exit_reason,
        return_pct=(exit_price / open_trade.entry_price - 1.0) * 100.0,
    )


def execute_rulebook(
    bars: tuple[NativeBar, ...] | list[NativeBar],
    entry_mask: object,
    technical_exit_mask: object | None,
    definition: RulebookDefinitionV2,
    partition: NativePartition,
    *,
    atr_values: object | None = None,
    ticker: str = "UNKNOWN",
) -> tuple[CompletedTrade, ...]:
    """Simulate a partition from flat state using next-native-open execution only."""

    native = tuple(bars)
    if not native or any(not isinstance(bar, NativeBar) for bar in native):
        raise ValueError("bars must be a non-empty NativeBar sequence")
    if not isinstance(definition, RulebookDefinitionV2):
        raise ValueError("definition must be RulebookDefinitionV2")
    _validate_partition(native, partition)
    entries = _boolean_mask(entry_mask, len(native), "entry_mask")
    technical = _boolean_mask(technical_exit_mask, len(native), "technical_exit_mask", optional=True)
    if not definition.technical_exits:
        technical = None
    frozen_atr = _atr_values(atr_values, len(native), definition)
    assert entries is not None

    completed: list[CompletedTrade] = []
    open_trade: _OpenTrade | None = None
    pending_entry_signal: int | None = None
    queued_technical_exit: int | None = None
    for ordinal in range(partition.start_ordinal, partition.end_ordinal + 1):
        current = native[ordinal]
        if open_trade is None and pending_entry_signal == ordinal - 1:
            signal_atr = None if frozen_atr is None else float(frozen_atr[pending_entry_signal])
            if frozen_atr is None or (math.isfinite(signal_atr) and signal_atr > 0.0):
                open_trade = _OpenTrade(
                    signal_ordinal=pending_entry_signal,
                    entry_ordinal=ordinal,
                    entry_price=current.open,
                    frozen_atr=signal_atr,
                    high_water=float(current.open),
                )
            pending_entry_signal = None

        exited = False
        if open_trade is not None:
            earliest_exit = open_trade.entry_ordinal + definition.min_hold_bars
            deadline = open_trade.entry_ordinal + definition.max_hold_bars - 1
            if ordinal >= earliest_exit:
                if queued_technical_exit == ordinal:
                    completed.append(_complete_trade(native, definition, ticker, open_trade, ordinal, float(current.open), "technical_exit"))
                    open_trade = None
                    queued_technical_exit = None
                    exited = True
                else:
                    price_exit = _exit_price(current, definition, open_trade)
                    if price_exit is not None:
                        price, reason = price_exit
                        completed.append(_complete_trade(native, definition, ticker, open_trade, ordinal, price, reason))
                        open_trade = None
                        queued_technical_exit = None
                        exited = True
                    elif ordinal == deadline:
                        completed.append(_complete_trade(native, definition, ticker, open_trade, ordinal, float(current.close), "timeout"))
                        open_trade = None
                        queued_technical_exit = None
                        exited = True
            if open_trade is not None:
                open_trade = _OpenTrade(
                    signal_ordinal=open_trade.signal_ordinal,
                    entry_ordinal=open_trade.entry_ordinal,
                    entry_price=open_trade.entry_price,
                    frozen_atr=open_trade.frozen_atr,
                    high_water=max(open_trade.high_water, float(current.high)),
                )
                if technical is not None and technical[ordinal]:
                    fill_ordinal = ordinal + 1
                    if earliest_exit <= fill_ordinal <= deadline and fill_ordinal <= partition.end_ordinal:
                        queued_technical_exit = fill_ordinal

        # The partition starts flat. Signals while open are deliberately ignored;
        # a signal observed on an exit bar may still fill on the following open.
        if open_trade is None and bool(entries[ordinal]) and ordinal + 1 <= partition.end_ordinal:
            pending_entry_signal = ordinal
        elif exited:
            pending_entry_signal = None
    return tuple(completed)


__all__ = ["CompletedTrade", "execute_rulebook"]
