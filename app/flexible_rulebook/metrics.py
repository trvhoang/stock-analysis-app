"""Exact gross partition metrics and threshold qualification."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .contracts import PartitionMetrics, SelectionPolicy, canonical_json
from .execution import CompletedTrade


@dataclass(frozen=True)
class PairwiseTimingEvidence:
    left_rulebook_id: str
    right_rulebook_id: str
    partition: Literal["training", "test"]
    paired_count: int
    left_earlier_count: int
    right_earlier_count: int
    tie_count: int
    unmatched_left_count: int
    unmatched_right_count: int
    median_native_bar_lead: float | None
    overlap_numerator: int
    overlap_denominator: int


@dataclass(frozen=True)
class SelectionResult:
    selected: tuple[object, ...]
    rejected: tuple[object, ...]
    blockers: tuple[tuple[str, str, PairwiseTimingEvidence], ...]


def _scope(evaluation: object) -> tuple[object, object, object, object]:
    snapshot = getattr(evaluation, "source_snapshot", None)
    source = getattr(snapshot, "raw_history_fingerprint", getattr(evaluation, "source_fingerprint", None))
    split = getattr(evaluation, "split", None)
    split_key = canonical_json(split.to_identity_dict()) if hasattr(split, "to_identity_dict") else split
    contract = getattr(evaluation, "execution_contract", None)
    revision = getattr(contract, "execution_revision", getattr(evaluation, "execution_revision", None))
    return getattr(evaluation, "ticker", None), source, split_key, revision


def _validate_scope(evaluations: Sequence[object]) -> None:
    if evaluations and (any(not isinstance(getattr(item, "rulebook_id", None), str) for item in evaluations) or len({_scope(item) for item in evaluations}) != 1):
        raise ValueError("evaluations must share one selection scope")


def _trades(evaluation: object, partition: Literal["training", "test"]) -> tuple[CompletedTrade, ...]:
    value = getattr(evaluation, f"{partition}_trades", None)
    if not isinstance(value, tuple) or any(not isinstance(trade, CompletedTrade) for trade in value):
        raise ValueError("timing comparison requires typed completed-trade evidence")
    return tuple(sorted(value, key=lambda trade: (trade.entry_bar_ordinal, trade.exit_bar_ordinal, trade.trade_id)))


def partition_metrics(trades: tuple[CompletedTrade, ...]) -> PartitionMetrics:
    """Return unrounded gross per-trade metrics; costs and certification excluded."""

    if not isinstance(trades, tuple) or any(not isinstance(trade, CompletedTrade) for trade in trades):
        raise ValueError("trades must be an immutable CompletedTrade tuple")
    returns = tuple(float(trade.return_pct) for trade in trades)
    if not all(math.isfinite(value) for value in returns):
        raise ValueError("completed trade returns must be finite")
    if not returns:
        return PartitionMetrics(0, None, 0.0, None, None)
    total = math.fsum(returns)
    mean = total / len(returns)
    wins = sum(value > 0.0 for value in returns)
    sharpe: float | None = None
    if len(returns) >= 2:
        variance = math.fsum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        if variance > 0.0 and math.isfinite(variance):
            sharpe = mean / math.sqrt(variance)
    return PartitionMetrics(len(returns), wins / len(returns) * 100.0, total, mean, sharpe)


def qualifies(training: PartitionMetrics, test: PartitionMetrics) -> bool:
    """Require observation, win-rate, and mean-gross-return thresholds in both splits."""

    if not isinstance(training, PartitionMetrics) or not isinstance(test, PartitionMetrics):
        raise ValueError("qualification requires PartitionMetrics for training and test")
    return all(
        metrics.n >= 12
        and metrics.win_rate is not None
        and metrics.mean_return_pct is not None
        and metrics.win_rate >= 65.0
        and metrics.mean_return_pct >= 15.0
        for metrics in (training, test)
    )


def rank_qualified(evaluations: Sequence[object]) -> tuple[object, ...]:
    """Rank threshold-qualified evidence by training metrics only, then lexical ID."""

    _validate_scope(evaluations)
    qualified = []
    for evaluation in evaluations:
        training = getattr(evaluation, "training_metrics", None)
        test = getattr(evaluation, "test_metrics", None)
        identifier = getattr(evaluation, "rulebook_id", None)
        if not isinstance(identifier, str) or not isinstance(training, PartitionMetrics) or not isinstance(test, PartitionMetrics):
            raise ValueError("ranking requires evaluation evidence with rulebook ID and partition metrics")
        if qualifies(training, test):
            qualified.append(evaluation)

    def rank_key(evaluation: object) -> tuple[float, float, int, float, str]:
        training = getattr(evaluation, "training_metrics")
        sharpe = training.sharpe
        return (
            -float(training.win_rate),
            -float(training.mean_return_pct),
            1 if sharpe is None else 0,
            -float(sharpe) if sharpe is not None else 0.0,
            getattr(evaluation, "rulebook_id"),
        )

    return tuple(sorted(qualified, key=rank_key))


def compare_entry_timing(left: object, right: object, partition: Literal["training", "test"]) -> PairwiseTimingEvidence:
    """Pair first inclusive interval overlaps after lexical rulebook canonicalization."""

    if partition not in ("training", "test") or left is right or getattr(left, "rulebook_id", None) == getattr(right, "rulebook_id", None):
        raise ValueError("timing comparison requires two distinct rulebooks")
    _validate_scope((left, right))
    lexical_left, lexical_right = sorted((left, right), key=lambda item: item.rulebook_id)
    left_trades, right_trades = _trades(lexical_left, partition), _trades(lexical_right, partition)
    left_index = right_index = 0
    paired = left_earlier = right_earlier = ties = unmatched_left = unmatched_right = 0
    leads: list[int] = []
    while left_index < len(left_trades) and right_index < len(right_trades):
        first, second = left_trades[left_index], right_trades[right_index]
        if first.exit_bar_ordinal < second.entry_bar_ordinal:
            unmatched_left += 1; left_index += 1
        elif second.exit_bar_ordinal < first.entry_bar_ordinal:
            unmatched_right += 1; right_index += 1
        else:
            paired += 1
            lead = first.signal_bar_ordinal - second.signal_bar_ordinal
            if lead < 0: left_earlier += 1; leads.append(abs(lead))
            elif lead > 0: right_earlier += 1; leads.append(abs(lead))
            else: ties += 1
            left_index += 1; right_index += 1
    unmatched_left += len(left_trades) - left_index
    unmatched_right += len(right_trades) - right_index
    denominator = min(len(left_trades), len(right_trades))
    return PairwiseTimingEvidence(lexical_left.rulebook_id, lexical_right.rulebook_id, partition, paired, left_earlier, right_earlier, ties, unmatched_left, unmatched_right, float(statistics.median(leads)) if leads else None, paired, denominator)


def select_timing_distinct_top_three(
    ranked: Sequence[object],
    policy: SelectionPolicy | None = None,
) -> SelectionResult:
    """Greedily retain only training-timing-distinct qualified representatives."""

    if policy is None:
        policy = SelectionPolicy()
    if not isinstance(policy, SelectionPolicy):
        raise ValueError("selection requires SelectionPolicy")
    ordered = rank_qualified(ranked)
    selected: list[object] = []
    rejected: list[object] = []
    blockers: list[tuple[str, str, PairwiseTimingEvidence]] = []
    for candidate in ordered:
        matches = [
            (representative, compare_entry_timing(candidate, representative, "training"))
            for representative in selected
        ]
        duplicates = [
            (item, evidence)
            for item, evidence in matches
            if evidence.overlap_denominator > 0
            and 4 * evidence.overlap_numerator >= 3 * evidence.overlap_denominator
        ]
        if duplicates:
            representative, evidence = sorted(duplicates, key=lambda item: (-item[1].overlap_numerator / item[1].overlap_denominator, ordered.index(item[0]), item[0].rulebook_id))[0]
            rejected.append(candidate); blockers.append((candidate.rulebook_id, representative.rulebook_id, evidence)); continue
        selected.append(candidate)
        if len(selected) == 3: break
    return SelectionResult(tuple(selected), tuple(rejected), tuple(blockers))


__all__ = ["PairwiseTimingEvidence", "SelectionResult", "compare_entry_timing", "partition_metrics", "qualifies", "rank_qualified", "select_timing_distinct_top_three"]
