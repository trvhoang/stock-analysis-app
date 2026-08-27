"""Authoritative daily flat-to-flat execution for Flexible Rulebook."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from typing import Callable

import numpy as np

from .contracts import EvaluationPartition, RulebookDefinition, rulebook_id
from .features import FeatureStore


@dataclass(frozen=True)
class CompletedTrade:
    """One complete simulated long trade using native raw-price evidence."""

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
class ExecutionInterrupted:
    """Safe caller-visible stop; caller must leave candidate slot uncommitted."""

    reason: str = "deadline_or_cancellation"


@dataclass(frozen=True)
class EventExitPlan:
    """Identity-bound optional acceleration material.

    The executable fast path remains disabled until it clears its independent
    reference-parity benchmark.  Keeping every source input here prevents a
    future fast path from accidentally applying an event schedule to different
    bars, masks, or rulebook semantics.
    """

    source_fingerprint: str
    receipt_digest: str
    partition: EvaluationPartition
    rulebook_id: str
    entry_mask_digest: str
    technical_mask_digest: str | None


@dataclass(frozen=True)
class _OpenTrade:
    signal_ordinal: int
    entry_ordinal: int
    entry_price: int
    atr: float | None
    high_water: float


def _validate_partition(store: FeatureStore, partition: EvaluationPartition) -> None:
    if not isinstance(partition, EvaluationPartition):
        raise ValueError("execution requires an EvaluationPartition")
    if not 0 <= partition.start_ordinal <= partition.end_ordinal < len(store.dates):
        raise ValueError("partition ordinals are outside FeatureStore")
    if (
        store.dates[partition.start_ordinal] != partition.start
        or store.dates[partition.end_ordinal] != partition.end
    ):
        raise ValueError("partition dates do not match FeatureStore native bars")


def _boolean_mask(value: np.ndarray | None, size: int, name: str) -> np.ndarray | None:
    if value is None:
        return None
    mask = np.asarray(value)
    if mask.shape != (size,) or mask.dtype != np.dtype(bool):
        raise ValueError(f"{name} must be one Boolean value per native bar")
    return mask


def _mask_digest(value: np.ndarray | None) -> str | None:
    """Hash an exact Boolean mask; ``None`` is distinct from all-false."""

    if value is None:
        return None
    contiguous = np.ascontiguousarray(value, dtype=np.bool_)
    return hashlib.sha256(contiguous.tobytes(order="C")).hexdigest()


def _frozen_signal_atr(store: FeatureStore, definition: RulebookDefinition, ordinal: int) -> float | None:
    if definition.atr_primitive is None:
        return None
    value = float(store.array_for(definition.atr_primitive, "atr")[ordinal])
    if not np.isfinite(value) or value <= 0.0:
        return None
    return value


def _trade_id(store: FeatureStore, definition: RulebookDefinition, open_trade: _OpenTrade, exit_ordinal: int) -> str:
    material = "|".join((
        rulebook_id(definition),
        store.snapshot.ticker,
        str(open_trade.signal_ordinal),
        str(open_trade.entry_ordinal),
        str(exit_ordinal),
    ))
    return f"frt_{hashlib.sha256(material.encode('ascii')).hexdigest()}"


def _complete_trade(
    store: FeatureStore,
    definition: RulebookDefinition,
    open_trade: _OpenTrade,
    exit_ordinal: int,
    exit_price: float,
    exit_reason: str,
) -> CompletedTrade:
    return CompletedTrade(
        trade_id=_trade_id(store, definition, open_trade, exit_ordinal),
        signal_date=store.dates[open_trade.signal_ordinal],
        entry_date=store.dates[open_trade.entry_ordinal],
        exit_date=store.dates[exit_ordinal],
        signal_bar_ordinal=open_trade.signal_ordinal,
        entry_bar_ordinal=open_trade.entry_ordinal,
        exit_bar_ordinal=exit_ordinal,
        entry_price=open_trade.entry_price,
        exit_price=exit_price,
        exit_reason=exit_reason,
        return_pct=(exit_price / open_trade.entry_price - 1.0) * 100.0,
    )


def _price_exit(
    store: FeatureStore,
    definition: RulebookDefinition,
    open_trade: _OpenTrade,
    ordinal: int,
) -> tuple[float, str] | None:
    """Apply raw-open gaps then stop-first intrabar thresholds using prior high-water."""

    if open_trade.atr is None:
        return None
    stop_levels: list[float] = []
    if definition.atr_stop_multiplier is not None:
        stop_levels.append(open_trade.entry_price - float(definition.atr_stop_multiplier) * open_trade.atr)
    if definition.atr_trailing_multiplier is not None:
        stop_levels.append(open_trade.high_water - float(definition.atr_trailing_multiplier) * open_trade.atr)
    stop = max(stop_levels) if stop_levels else None
    target = (
        open_trade.entry_price + float(definition.atr_target_multiplier) * open_trade.atr
        if definition.atr_target_multiplier is not None
        else None
    )
    raw_open = float(store.open[ordinal])
    if stop is not None and raw_open <= stop:
        return raw_open, "stop_loss"
    if target is not None and raw_open >= target:
        return raw_open, "take_profit"
    if stop is not None and float(store.low[ordinal]) <= stop:
        return stop, "stop_loss"
    if target is not None and float(store.high[ordinal]) >= target:
        return target, "take_profit"
    return None


def execute_rulebook_reference(
    store: FeatureStore,
    entry_mask: np.ndarray,
    technical_exit_mask: np.ndarray | None,
    definition: RulebookDefinition,
    partition: EvaluationPartition,
    *,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[CompletedTrade, ...] | ExecutionInterrupted:
    """Execute one partition flat-to-flat with causal next-open daily semantics."""

    if not isinstance(store, FeatureStore) or not isinstance(definition, RulebookDefinition):
        raise ValueError("execution requires FeatureStore and RulebookDefinition")
    _validate_partition(store, partition)
    entries = _boolean_mask(entry_mask, len(store.dates), "entry_mask")
    technical = _boolean_mask(technical_exit_mask, len(store.dates), "technical_exit_mask")
    assert entries is not None

    completed: list[CompletedTrade] = []
    open_trade: _OpenTrade | None = None
    pending_entry_signal: int | None = None
    queued_technical_exit_ordinal: int | None = None
    for ordinal in range(partition.start_ordinal, partition.end_ordinal + 1):
        if should_stop is not None and should_stop():
            return ExecutionInterrupted()

        if open_trade is None and pending_entry_signal == ordinal - 1:
            atr = _frozen_signal_atr(store, definition, pending_entry_signal)
            if definition.atr_primitive is None or atr is not None:
                entry_price = int(store.open[ordinal])
                open_trade = _OpenTrade(
                    signal_ordinal=pending_entry_signal,
                    entry_ordinal=ordinal,
                    entry_price=entry_price,
                    atr=atr,
                    high_water=float(entry_price),
                )
            pending_entry_signal = None

        exited = False
        if open_trade is not None:
            earliest_exit = open_trade.entry_ordinal + definition.min_hold_bars
            deadline = open_trade.entry_ordinal + definition.max_hold_bars - 1
            if ordinal >= earliest_exit:
                if queued_technical_exit_ordinal == ordinal:
                    completed.append(_complete_trade(
                        store, definition, open_trade, ordinal, float(store.open[ordinal]), "technical_exit",
                    ))
                    open_trade = None
                    queued_technical_exit_ordinal = None
                    exited = True
                else:
                    price_exit = _price_exit(store, definition, open_trade, ordinal)
                    if price_exit is not None:
                        exit_price, reason = price_exit
                        completed.append(_complete_trade(store, definition, open_trade, ordinal, exit_price, reason))
                        open_trade = None
                        queued_technical_exit_ordinal = None
                        exited = True
                    elif ordinal == deadline:
                        completed.append(_complete_trade(
                            store, definition, open_trade, ordinal, float(store.close[ordinal]), "timeout",
                        ))
                        open_trade = None
                        queued_technical_exit_ordinal = None
                        exited = True
            if open_trade is not None:
                open_trade = _OpenTrade(
                    signal_ordinal=open_trade.signal_ordinal,
                    entry_ordinal=open_trade.entry_ordinal,
                    entry_price=open_trade.entry_price,
                    atr=open_trade.atr,
                    high_water=max(open_trade.high_water, float(store.high[ordinal])),
                )
                if technical is not None and technical[ordinal]:
                    fill_ordinal = ordinal + 1
                    deadline = open_trade.entry_ordinal + definition.max_hold_bars - 1
                    if (
                        fill_ordinal >= open_trade.entry_ordinal + definition.min_hold_bars
                        and fill_ordinal <= deadline
                        and fill_ordinal <= partition.end_ordinal
                    ):
                        queued_technical_exit_ordinal = fill_ordinal

        # A signal on an exit bar can queue tomorrow's entry; signals while still
        # open remain suppressed. A partition always starts flat, so no earlier
        # signal may cross its left boundary.
        if open_trade is None and entries[ordinal] and ordinal + 1 <= partition.end_ordinal:
            pending_entry_signal = ordinal
        elif exited:
            pending_entry_signal = None

    return tuple(completed)


def build_event_exit_plan(
    store: FeatureStore,
    entry_mask: np.ndarray,
    technical_exit_mask: np.ndarray | None,
    definition: RulebookDefinition,
    partition: EvaluationPartition,
    receipt_digest: str,
) -> EventExitPlan | None:
    """Bind a future event plan to one exact reference-executor input tuple."""

    if not isinstance(store, FeatureStore) or not isinstance(definition, RulebookDefinition):
        raise ValueError("event plan requires FeatureStore and RulebookDefinition")
    _validate_partition(store, partition)
    if not isinstance(receipt_digest, str) or not receipt_digest:
        raise ValueError("event plan requires non-empty receipt digest")
    entries = _boolean_mask(entry_mask, len(store.dates), "entry_mask")
    technical = _boolean_mask(technical_exit_mask, len(store.dates), "technical_exit_mask")
    assert entries is not None
    fingerprint = store.snapshot.fingerprint
    if fingerprint is None:
        return None
    # No event arrays are persisted or executed yet.  This immutable identity
    # record is deliberately inert until benchmarked fast execution exists.
    return EventExitPlan(
        source_fingerprint=fingerprint,
        receipt_digest=receipt_digest,
        partition=partition,
        rulebook_id=rulebook_id(definition),
        entry_mask_digest=_mask_digest(entries),
        technical_mask_digest=_mask_digest(technical),
    )


def event_plan_is_compatible(
    event_plan: EventExitPlan,
    store: FeatureStore,
    entry_mask: np.ndarray,
    technical_exit_mask: np.ndarray | None,
    definition: RulebookDefinition,
    partition: EvaluationPartition,
    receipt_digest: str | None,
) -> bool:
    """Require complete input identity before any future fast-path use."""

    return (
        receipt_digest is not None
        and event_plan.source_fingerprint == store.snapshot.fingerprint
        and event_plan.receipt_digest == receipt_digest
        and event_plan.partition == partition
        and event_plan.rulebook_id == rulebook_id(definition)
        and event_plan.entry_mask_digest == _mask_digest(entry_mask)
        and event_plan.technical_mask_digest == _mask_digest(technical_exit_mask)
    )


def execute_rulebook(
    store: FeatureStore,
    entry_mask: np.ndarray,
    technical_exit_mask: np.ndarray | None,
    definition: RulebookDefinition,
    partition: EvaluationPartition,
    *,
    event_plan: EventExitPlan | None = None,
    receipt_digest: str | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[CompletedTrade, ...] | ExecutionInterrupted:
    """Run only reference semantics until optional fast path clears parity gate."""

    if event_plan is not None and not event_plan_is_compatible(
        event_plan, store, entry_mask, technical_exit_mask, definition, partition, receipt_digest,
    ):
        # Mismatch is a safe cache miss: never apply a plan from another source
        # or feature receipt to these bars.
        event_plan = None
    del event_plan
    return execute_rulebook_reference(
        store,
        entry_mask,
        technical_exit_mask,
        definition,
        partition,
        should_stop=should_stop,
    )


__all__ = [
    "CompletedTrade",
    "EventExitPlan",
    "ExecutionInterrupted",
    "build_event_exit_plan",
    "event_plan_is_compatible",
    "execute_rulebook",
    "execute_rulebook_reference",
]
